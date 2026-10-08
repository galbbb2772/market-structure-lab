#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,statistics,math
from collections import defaultdict
from datetime import date
from pathlib import Path
import pandas as pd
import research_pure_box_core_geometry_simplicity_v13 as v13
import research_pure_box_capital_architecture_v22 as v22

ENTRY_COST=v13.ENTRY_COST; EXIT_COST=v13.EXIT_COST
RB=.0125; CAP=.50; MAX_HOLD=15

def mdd(vals):
    p=vals[0];d=0.0
    for x in vals:
        p=max(p,x)
        if p>0:d=min(d,x/p-1)
    return d

def sharpe(vals):
    rs=[vals[i]/vals[i-1]-1 for i in range(1,len(vals)) if vals[i-1]>0]
    if len(rs)<2:return None
    sd=statistics.stdev(rs)
    return None if sd==0 else statistics.mean(rs)/sd*math.sqrt(252)

def pf(rs):
    w=sum(x for x in rs if x>0);l=-sum(x for x in rs if x<0)
    return w/l if l>0 else None

def order_candidates(policy,items):
    if policy=="LOW_ENTRY_FRACTION_FIRST":
        return sorted(items,key=lambda x:(x["entry_fraction"],x["liquidity_rank"],x["symbol"]))
    if policy=="WIDER_BOX_FIRST":
        return sorted(items,key=lambda x:(-x["box_width_pct"],x["entry_fraction"],x["liquidity_rank"],x["symbol"]))
    if policy=="LOWER_STOP_RISK_FIRST":
        return sorted(items,key=lambda x:(x["risk_per_dollar"],x["entry_fraction"],x["liquidity_rank"],x["symbol"]))
    if policy=="LARGE_SCALE_FIRST":
        return sorted(items,key=lambda x:(0 if x["scale"]=="large" else 1,x["entry_fraction"],x["liquidity_rank"],x["symbol"]))
    if policy=="LIQUIDITY_FIRST":
        return sorted(items,key=lambda x:(x["liquidity_rank"],x["entry_fraction"],x["symbol"]))
    return list(items)

def run(cands,calendar,bm,policy):
    cidx={d:i for i,d in enumerate(calendar)}
    by=defaultdict(list)
    for c in cands:
        d=str(c["direct_entry_date"])
        if v13.VAL_START<=d<=v13.VAL_END and d in cidx:by[d].append(c)
    days=[d for d in calendar if v13.VAL_START<=d<=v13.VAL_END]
    cash=1.0;pos={};eq=[];expo=[];trs=[]
    blocked=0;partial=0;entries=0;requested_risk=0.0;realized_risk=0.0
    sel_ef=[];sel_width=[];sel_risk=[]
    for d in days:
        # gap exits
        for s in list(pos):
            b=bm.get(s,{}).get(d)
            if b is None:continue
            p=pos[s];p["hold_sessions"]+=1
            op=float(b["open"]);px=None;reason=None
            if op<=p["lower"]:px=op;reason="stop_gap"
            elif op>=p["target"]:px=op;reason="target_gap"
            if px is not None:
                proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                trs.append(proceeds/p["cost_basis"]-1);del pos[s]

        eqo=cash;inv_open=0.0
        for s,p in pos.items():
            b=bm.get(s,{}).get(d);v=p["shares"]*(float(b["open"]) if b is not None else p["last"])
            eqo+=v;inv_open+=v

        raw=[];seen=set()
        for c in sorted(by.get(d,[]),key=lambda x:(str(x["symbol"]),str(x["signal_date"]))):
            s=str(c["symbol"])
            if s in seen or s in pos:continue
            seen.add(s)
            b=bm.get(s,{}).get(d)
            if b is None:continue
            op=float(b["open"]);lo=float(c["lower"]);hi=float(c["upper"]);target=lo+.60*(hi-lo)
            if not(lo<op<target):continue
            ef=(op-lo)/(hi-lo)
            if ef>.20:continue
            riskpd=1-(lo*(1-EXIT_COST))/(op*(1+ENTRY_COST))
            if riskpd<=0:continue
            width=(hi-lo)/op
            rq=min(RB*eqo/riskpd,CAP*eqo)
            requested_risk+=RB*eqo
            raw.append({**c,"symbol":s,"entry_price":op,"lower":lo,"upper":hi,"target":target,
                        "entry_fraction":ef,"risk_per_dollar":riskpd,"box_width_pct":width,"request":rq})

        if policy=="PRO_RATA":
            total=sum(x["request"] for x in raw)
            sc=min(1.0,cash/total) if total>0 else 0.0
            allocs=[x["request"]*sc for x in raw]
            if sc<1-1e-12:
                partial+=len(raw)
        else:
            raw=order_candidates(policy,raw)
            rem=cash;allocs=[]
            for x in raw:
                if rem<=1e-12:
                    allocs.append(0.0);blocked+=1;continue
                amt=min(x["request"],rem)
                allocs.append(amt)
                if amt+1e-12<x["request"]:partial+=1
                rem-=amt

        for x,amt in zip(raw,allocs):
            if amt<=1e-12:continue
            invest=amt*(1-ENTRY_COST);cash-=amt
            pos[x["symbol"]]={**x,"shares":invest/x["entry_price"],"cost_basis":amt,
                              "hold_sessions":1,"last":x["entry_price"]}
            realized_risk+=amt*x["risk_per_dollar"];entries+=1
            sel_ef.append(x["entry_fraction"]);sel_width.append(x["box_width_pct"]);sel_risk.append(x["risk_per_dollar"])

        # intraday exits
        for s in list(pos):
            p=pos[s];b=bm.get(s,{}).get(d)
            if b is None:continue
            lo=float(b["low"]);hi=float(b["high"]);cl=float(b["close"]);px=None
            if lo<=p["lower"]:px=p["lower"]
            elif hi>=p["target"]:px=p["target"]
            elif p["hold_sessions"]>=MAX_HOLD:px=cl
            if px is not None:
                proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                trs.append(proceeds/p["cost_basis"]-1);del pos[s]
            else:p["last"]=cl

        val=cash;inv=0.0
        for s,p in pos.items():
            b=bm.get(s,{}).get(d);px=float(b["close"]) if b is not None else p["last"];p["last"]=px
            v=p["shares"]*px;val+=v;inv+=v
        eq.append((d,val));expo.append(inv/val if val>0 else 0.0)

    vals=[v for _,v in eq]
    edf=pd.DataFrame(eq,columns=["date","equity"]);edf["year"]=edf.date.str[:4]
    roll=[]
    for i in range(251,len(edf)):
        g=edf.iloc[i-251:i+1];roll.append(float(g.equity.iloc[-1]/g.equity.iloc[0]-1))
    yrs=max((date.fromisoformat(days[-1])-date.fromisoformat(days[0])).days/365.2425,1/365)
    return {
      "total_return":vals[-1]/vals[0]-1,
      "cagr":(vals[-1]/vals[0])**(1/yrs)-1,
      "max_drawdown":mdd(vals),"daily_sharpe":sharpe(vals),
      "avg_exposure":statistics.mean(expo),"idle_day_share":sum(x<.10 for x in expo)/len(expo),
      "completed_trades":len(trs),"profit_factor":pf(trs),
      "mean_trade":statistics.mean(trs) if trs else None,
      "win_rate":sum(x>0 for x in trs)/len(trs) if trs else None,
      "entries":entries,"blocked_entries":blocked,"partial_entries":partial,
      "risk_realization_ratio":realized_risk/requested_risk if requested_risk else None,
      "selected_entry_fraction_mean":statistics.mean(sel_ef) if sel_ef else None,
      "selected_box_width_mean":statistics.mean(sel_width) if sel_width else None,
      "selected_stop_risk_mean":statistics.mean(sel_risk) if sel_risk else None,
      "yearly_return":{y:float(g.equity.iloc[-1]/g.equity.iloc[0]-1) for y,g in edf.groupby("year")},
      "rolling_12m_min_return":min(roll) if roll else None,
      "rolling_12m_positive_share":sum(x>0 for x in roll)/len(roll) if roll else None,
      "rolling_12m_median_return":statistics.median(roll) if roll else None
    }

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=v13.load(a.indir)
    policies=("PRO_RATA","LOW_ENTRY_FRACTION_FIRST","WIDER_BOX_FIRST","LOWER_STOP_RISK_FIRST","LARGE_SCALE_FIRST","LIQUIDITY_FIRST")
    rows=[];summary={"schema":"PURE-BOX-SIMPLE-CORE-CAPITAL-PRIORITY-V26","results":{}}
    for cap in (300,500):
        cs=v22.bottom20(v13.strict_signals(sig,cap,cal,idx,nxt,bm))
        for pol in policies:
            r=run(cs,cal,bm,pol)
            row={**r,"rank_cap":cap,"policy":pol,"candidate_n":len(cs)}
            summary["results"][f"top{cap}__{pol}"]=row;rows.append(row)
    pd.DataFrame(rows).to_csv(out/"results.csv",index=False)
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(pd.DataFrame(rows).to_string(index=False))
if __name__=="__main__":main()
