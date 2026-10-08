#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,statistics,math
from collections import defaultdict
from datetime import date
from pathlib import Path
import pandas as pd
import research_pure_box_core_geometry_simplicity_v13 as v13
import research_pure_box_capital_architecture_v22 as v22

CAP=.50; MAX_HOLD=15

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

def risk_budget(mode,opening_exposure):
    if mode=="R125":return .0125
    if opening_exposure<.25:return .015
    if opening_exposure>.60:return .01
    return .0125

def order_items(policy,items):
    if policy=="PRO_RATA":return items
    if policy=="LIQUIDITY_FIRST":
        return sorted(items,key=lambda x:(x["liquidity_rank"],x["entry_fraction"],x["symbol"]))
    if policy=="LOW_ENTRY_FIRST":
        return sorted(items,key=lambda x:(x["entry_fraction"],x["liquidity_rank"],x["symbol"]))
    raise ValueError(policy)

def replay(cands,calendar,bm,risk_mode,alloc_policy,cost_bps=5,delay=0):
    ec=cost_bps/10000; xc=cost_bps/10000
    cidx={d:i for i,d in enumerate(calendar)}
    by=defaultdict(list)
    for c in cands:
        sd=str(c["direct_entry_date"])
        if sd not in cidx:continue
        ei=cidx[sd]+delay
        if ei>=len(calendar):continue
        ed=calendar[ei]
        if v13.VAL_START<=ed<=v13.VAL_END:
            z=dict(c);z["_exec_date"]=ed;by[ed].append(z)
    days=[d for d in calendar if v13.VAL_START<=d<=v13.VAL_END]
    cash=1.;pos={};eq=[];expo=[];trades=[];blocked=0;partial=0
    for d in days:
        # gap exits + age increment
        for s in list(pos):
            b=bm.get(s,{}).get(d)
            if b is None:continue
            p=pos[s]
            if p["entry_date"]!=d:p["hold_sessions"]+=1
            o=float(b["open"]);px=None;reason=None
            if o<=p["lower"]:px=o;reason="stop_gap"
            elif o>=p["target"]:px=o;reason="target_gap"
            if px is not None:
                proceeds=p["shares"]*px*(1-xc);cash+=proceeds
                pnl=proceeds-p["cost_basis"]
                trades.append({**p,"exit_date":d,"exit_reason":reason,"net_return":proceeds/p["cost_basis"]-1,"pnl":pnl})
                del pos[s]

        eqo=cash;inv_open=0.
        for s,p in pos.items():
            b=bm.get(s,{}).get(d);v=p["shares"]*(float(b["open"]) if b is not None else p["last"])
            eqo+=v;inv_open+=v
        opening_exposure=inv_open/eqo if eqo>0 else 0.
        rb=risk_budget(risk_mode,opening_exposure)

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
            riskpd=1-(lo*(1-xc))/(op*(1+ec))
            if riskpd<=0:continue
            rq=min(rb*eqo/riskpd,CAP*eqo)
            raw.append({**c,"symbol":s,"entry_price":op,"entry_date":d,"lower":lo,"upper":hi,"target":target,
                        "entry_fraction":ef,"risk_per_dollar":riskpd,"request":rq})
        if alloc_policy=="PRO_RATA":
            total=sum(x["request"] for x in raw);sc=min(1.,cash/total) if total>0 else 0.
            allocs=[x["request"]*sc for x in raw]
            if sc<1-1e-12:partial+=len(raw)
        else:
            raw=order_items(alloc_policy,raw);rem=cash;allocs=[]
            for x in raw:
                if rem<=1e-12:allocs.append(0.);blocked+=1;continue
                amt=min(x["request"],rem);allocs.append(amt)
                if amt+1e-12<x["request"]:partial+=1
                rem-=amt
        for x,amt in zip(raw,allocs):
            if amt<=1e-12:continue
            invest=amt*(1-ec);cash-=amt
            pos[x["symbol"]]={**x,"shares":invest/x["entry_price"],"cost_basis":amt,"hold_sessions":1,"last":x["entry_price"]}

        # intraday exits
        for s in list(pos):
            p=pos[s];b=bm.get(s,{}).get(d)
            if b is None:continue
            lo=float(b["low"]);hi=float(b["high"]);cl=float(b["close"]);px=None;reason=None
            if lo<=p["lower"]:px=p["lower"];reason="stop"
            elif hi>=p["target"]:px=p["target"];reason="target60"
            elif p["hold_sessions"]>=MAX_HOLD:px=cl;reason="time_h15"
            if px is not None:
                proceeds=p["shares"]*px*(1-xc);cash+=proceeds
                pnl=proceeds-p["cost_basis"]
                trades.append({**p,"exit_date":d,"exit_reason":reason,"net_return":proceeds/p["cost_basis"]-1,"pnl":pnl})
                del pos[s]
            else:p["last"]=cl

        val=cash;inv=0.
        for s,p in pos.items():
            b=bm.get(s,{}).get(d);px=float(b["close"]) if b is not None else p["last"];p["last"]=px
            v=p["shares"]*px;val+=v;inv+=v
        eq.append((d,val));expo.append(inv/val if val>0 else 0.)

    vals=[v for _,v in eq];edf=pd.DataFrame(eq,columns=["date","equity"]);edf["year"]=edf.date.str[:4]
    roll=[]
    for i in range(251,len(edf)):
        g=edf.iloc[i-251:i+1];roll.append(float(g.equity.iloc[-1]/g.equity.iloc[0]-1))
    yrs=max((date.fromisoformat(days[-1])-date.fromisoformat(days[0])).days/365.2425,1/365)
    tdf=pd.DataFrame(trades)
    if len(tdf):
        bysym=tdf.groupby("symbol").pnl.sum().abs().sort_values(ascending=False);tot=float(bysym.sum())
        top5=float(bysym.head(5).sum()/tot) if tot else None;top10=float(bysym.head(10).sum()/tot) if tot else None
        rs=tdf.net_return.tolist()
    else: top5=top10=None;rs=[]
    return {
      "total_return":vals[-1]/vals[0]-1,
      "cagr":(vals[-1]/vals[0])**(1/yrs)-1,
      "max_drawdown":mdd(vals),"daily_sharpe":sharpe(vals),
      "avg_exposure":statistics.mean(expo),"idle_day_share":sum(x<.10 for x in expo)/len(expo),
      "completed_trades":len(rs),"profit_factor":pf(rs) if rs else None,
      "mean_trade":statistics.mean(rs) if rs else None,
      "win_rate":sum(x>0 for x in rs)/len(rs) if rs else None,
      "blocked_entries":blocked,"partial_entries":partial,
      "top5_abs_funded_pnl_share":top5,"top10_abs_funded_pnl_share":top10,
      "yearly_return":{y:float(g.equity.iloc[-1]/g.equity.iloc[0]-1) for y,g in edf.groupby("year")},
      "rolling_12m_min_return":min(roll) if roll else None,
      "rolling_12m_positive_share":sum(x>0 for x in roll)/len(roll) if roll else None,
      "rolling_12m_median_return":statistics.median(roll) if roll else None
    }

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=v13.load(a.indir)
    cfg={
      300:[("BASE","R125","PRO_RATA"),("CANDIDATE","EA","LOW_ENTRY_FIRST")],
      500:[("BASE","R125","PRO_RATA"),("CANDIDATE","R125","LIQUIDITY_FIRST")]
    }
    rows=[];summary={"schema":"PURE-BOX-SIMPLE-CORE-PORTFOLIO-LEVEL-STRESS-V31","results":{}}
    for cap,lanes in cfg.items():
        cs=v22.bottom20(v13.strict_signals(sig,cap,cal,idx,nxt,bm));cres={}
        for name,rm,apol in lanes:
            rr={}
            for bps in (5,10,20):
                for delay in (0,1):
                    k=f"{bps}bps__delay{delay}"
                    rr[k]=replay(cs,cal,bm,rm,apol,bps,delay)
                    rows.append({"rank_cap":cap,"lane":name,"risk_mode":rm,"allocation_policy":apol,
                                 "cost_bps_side":bps,"delay_sessions":delay,**rr[k]})
            cres[name]=rr
        summary["results"][f"top{cap}"]=cres
    pd.DataFrame(rows).to_csv(out/"results.csv",index=False)
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(pd.DataFrame(rows)[["rank_cap","lane","cost_bps_side","delay_sessions","total_return","max_drawdown","daily_sharpe","rolling_12m_min_return","top5_abs_funded_pnl_share"]].to_string(index=False))
if __name__=="__main__":main()
