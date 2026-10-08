#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,statistics,math
from collections import defaultdict
from datetime import date
from pathlib import Path
import pandas as pd
import research_pure_box_core_geometry_simplicity_v13 as v13
import research_pure_box_capital_architecture_v22 as v22

EC=v13.ENTRY_COST;XC=v13.EXIT_COST
RB=.0125;CAP=.50;H=15

def mdd(vals):
    p=vals[0];d=0.
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

def progress_at_open(p,op):
    rng=max(p["target"]-p["entry_price"],1e-12)
    return (op-p["entry_price"])/rng

def replaceable(policy,pos,bm,d,new_liq):
    cand=[]
    for s,p in pos.items():
        b=bm.get(s,{}).get(d)
        if b is None:continue
        if int(p["liquidity_rank"])<=int(new_liq):continue
        age=int(p["hold"])
        op=float(b["open"])
        prog=progress_at_open(p,op)
        ok=False
        if policy=="LIQUIDITY_RANK_REPLACE":ok=True
        elif policy=="AGE10_LIQUIDITY_REPLACE":ok=age>=10
        elif policy=="AGE5_STALE_REPLACE":ok=age>=5 and prog<.25
        elif policy=="AGE10_STALE_REPLACE":ok=age>=10 and prog<.25
        if ok:cand.append((int(p["liquidity_rank"]),s,op,prog))
    cand.sort(reverse=True)
    return cand

def run(cands,calendar,bm,policy):
    cidx={d:i for i,d in enumerate(calendar)}
    by=defaultdict(list)
    for c in cands:
        d=str(c["direct_entry_date"])
        if v13.VAL_START<=d<=v13.VAL_END and d in cidx:by[d].append(c)
    days=[d for d in calendar if v13.VAL_START<=d<=v13.VAL_END]
    cash=1.;pos={};eq=[];expo=[];trs=[];funded=defaultdict(float)
    blocked=partial=entries=0;repl_count=0;repl_returns=[];turnover=0.
    for d in days:
        # age + gap exits
        for s in list(pos):
            b=bm.get(s,{}).get(d)
            if b is None:continue
            p=pos[s];p["hold"]+=1;o=float(b["open"]);px=None
            if o<=p["lower"]:px=o
            elif o>=p["target"]:px=o
            if px is not None:
                proceeds=p["shares"]*px*(1-XC);cash+=proceeds;turnover+=proceeds
                r=proceeds/p["cost_basis"]-1;trs.append(r);funded[s]+=p["cost_basis"]*r;del pos[s]

        eqo=cash
        for s,p in pos.items():
            b=bm.get(s,{}).get(d);eqo+=p["shares"]*(float(b["open"]) if b is not None else p["last"])

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
            riskpd=1-(lo*(1-XC))/(op*(1+EC))
            if riskpd<=0:continue
            rq=min(RB*eqo/riskpd,CAP*eqo)
            raw.append({**c,"symbol":s,"entry_price":op,"lower":lo,"upper":hi,"target":target,
                        "entry_fraction":ef,"risk_per_dollar":riskpd,"request":rq})
        raw.sort(key=lambda x:(x["liquidity_rank"],x["entry_fraction"],x["symbol"]))

        for x in raw:
            need=x["request"]
            if cash+1e-12<need and policy!="NO_DISPLACEMENT":
                for liq,s,op,prog in replaceable(policy,pos,bm,d,x["liquidity_rank"]):
                    if cash+1e-12>=need:break
                    p=pos[s]
                    full_val=p["shares"]*op*(1-XC)
                    short=need-cash
                    # sell only enough to cover short, unless negligible residual
                    frac=min(1.0,short/max(full_val,1e-12))
                    shares_to_sell=p["shares"]*frac
                    proceeds=shares_to_sell*op*(1-XC)
                    basis=p["cost_basis"]*frac
                    cash+=proceeds;turnover+=proceeds
                    r=proceeds/basis-1 if basis>0 else 0.
                    repl_returns.append(r);repl_count+=1
                    p["shares"]-=shares_to_sell;p["cost_basis"]-=basis
                    if p["shares"]<=1e-10 or p["cost_basis"]<=1e-10:del pos[s]
            amt=min(need,cash)
            if amt<=1e-12:
                blocked+=1;continue
            if amt+1e-12<need:partial+=1
            invest=amt*(1-EC);cash-=amt;turnover+=amt
            pos[x["symbol"]]={**x,"shares":invest/x["entry_price"],"cost_basis":amt,"hold":1,"last":x["entry_price"]}
            entries+=1

        # intraday exits
        for s in list(pos):
            p=pos[s];b=bm.get(s,{}).get(d)
            if b is None:continue
            lo=float(b["low"]);hi=float(b["high"]);cl=float(b["close"]);px=None
            if lo<=p["lower"]:px=p["lower"]
            elif hi>=p["target"]:px=p["target"]
            elif p["hold"]>=H:px=cl
            if px is not None:
                proceeds=p["shares"]*px*(1-XC);cash+=proceeds;turnover+=proceeds
                r=proceeds/p["cost_basis"]-1;trs.append(r);funded[s]+=p["cost_basis"]*r;del pos[s]
            else:p["last"]=cl

        val=cash;inv=0.
        for s,p in pos.items():
            b=bm.get(s,{}).get(d);px=float(b["close"]) if b is not None else p["last"];p["last"]=px
            v=p["shares"]*px;val+=v;inv+=v
        eq.append((d,val));expo.append(inv/val if val>0 else 0.)

    vals=[v for _,v in eq]
    edf=pd.DataFrame(eq,columns=["date","equity"]);edf["year"]=edf.date.str[:4]
    roll=[]
    for i in range(251,len(edf)):
        g=edf.iloc[i-251:i+1];roll.append(float(g.equity.iloc[-1]/g.equity.iloc[0]-1))
    yrs=max((date.fromisoformat(days[-1])-date.fromisoformat(days[0])).days/365.2425,1/365)
    absvals=sorted((abs(v) for v in funded.values()),reverse=True);tot=sum(absvals)
    return {
      "total_return":vals[-1]/vals[0]-1,"cagr":(vals[-1]/vals[0])**(1/yrs)-1,
      "max_drawdown":mdd(vals),"daily_sharpe":sharpe(vals),
      "avg_exposure":statistics.mean(expo),"idle_day_share":sum(x<.10 for x in expo)/len(expo),
      "completed_trades":len(trs),"profit_factor":pf(trs),"mean_trade":statistics.mean(trs) if trs else None,
      "entries":entries,"blocked_entries":blocked,"partial_entries":partial,
      "replacement_count":repl_count,
      "mean_displaced_realized_return":statistics.mean(repl_returns) if repl_returns else None,
      "turnover_proxy":turnover,
      "top5_abs_funded_pnl_share":sum(absvals[:5])/tot if tot else None,
      "top10_abs_funded_pnl_share":sum(absvals[:10])/tot if tot else None,
      "yearly_return":{y:float(g.equity.iloc[-1]/g.equity.iloc[0]-1) for y,g in edf.groupby("year")},
      "rolling_12m_min_return":min(roll) if roll else None,
      "rolling_12m_positive_share":sum(x>0 for x in roll)/len(roll) if roll else None,
      "rolling_12m_median_return":statistics.median(roll) if roll else None
    }

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=v13.load(a.indir)
    cs=v22.bottom20(v13.strict_signals(sig,500,cal,idx,nxt,bm))
    policies=("NO_DISPLACEMENT","LIQUIDITY_RANK_REPLACE","AGE10_LIQUIDITY_REPLACE","AGE5_STALE_REPLACE","AGE10_STALE_REPLACE")
    rows=[];summary={"schema":"PURE-BOX-SIMPLE-CORE-CAPITAL-DISPLACEMENT-V35","results":{}}
    for p in policies:
        r=run(cs,cal,bm,p);summary["results"][p]=r;rows.append({"policy":p,**r})
    pd.DataFrame(rows).to_csv(out/"results.csv",index=False)
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(pd.DataFrame(rows)[["policy","total_return","cagr","max_drawdown","daily_sharpe","replacement_count","mean_displaced_realized_return","rolling_12m_min_return","turnover_proxy"]].to_string(index=False))
if __name__=="__main__":main()
