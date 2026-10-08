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

def redistribute(requests,weights,cash):
    n=len(requests);alloc=[0.]*n;active=set(i for i,r in enumerate(requests) if r>0)
    rem=cash
    while active and rem>1e-12:
        den=sum(weights[i]*requests[i] for i in active)
        if den<=0:break
        used=0.;done=[]
        tentative={}
        for i in active:
            tentative[i]=rem*(weights[i]*requests[i])/den
        for i in list(active):
            room=requests[i]-alloc[i]
            add=min(room,tentative[i])
            alloc[i]+=add;used+=add
            if alloc[i]>=requests[i]-1e-12:done.append(i)
        rem-=used
        for i in done:active.discard(i)
        if used<=1e-12:break
    return alloc

def allocate(policy,raw,cash):
    if not raw:return []
    if policy=="LIQUIDITY_FIRST_SEQUENTIAL":
        raw.sort(key=lambda x:(x["liquidity_rank"],x["entry_fraction"],x["symbol"]))
        rem=cash;out=[]
        for x in raw:
            amt=min(x["request"],rem) if rem>0 else 0.;out.append(amt);rem-=amt
        return out
    if policy=="PRO_RATA":
        total=sum(x["request"] for x in raw)
        sc=min(1.,cash/total) if total>0 else 0.
        return [x["request"]*sc for x in raw]
    raw.sort(key=lambda x:(x["liquidity_rank"],x["entry_fraction"],x["symbol"]))
    n=len(raw)
    if policy=="LIQUIDITY_WEIGHTED_LINEAR":
        w=[n-i for i in range(n)]
    elif policy=="LIQUIDITY_WEIGHTED_INVERSE_RANK":
        w=[1/(i+1) for i in range(n)]
    elif policy=="LIQUIDITY_WEIGHTED_INVERSE_SQRT":
        w=[1/math.sqrt(i+1) for i in range(n)]
    elif policy=="TWO_TIER_LIQUIDITY":
        cut=(n+1)//2;w=[2 if i<cut else 1 for i in range(n)]
    else:raise ValueError(policy)
    return redistribute([x["request"] for x in raw],w,cash)

def run(cands,calendar,bm,policy):
    cidx={d:i for i,d in enumerate(calendar)}
    by=defaultdict(list)
    for c in cands:
        d=str(c["direct_entry_date"])
        if v13.VAL_START<=d<=v13.VAL_END and d in cidx:by[d].append(c)
    days=[d for d in calendar if v13.VAL_START<=d<=v13.VAL_END]
    cash=1.;pos={};eq=[];expo=[];trs=[];funded=defaultdict(float)
    reqrisk=realrisk=0.;entries=blocked=partial=eligible=0;funded_nonzero=0
    for d in days:
        for s in list(pos):
            b=bm.get(s,{}).get(d)
            if b is None:continue
            p=pos[s];p["hold"]+=1;o=float(b["open"]);px=None
            if o<=p["lower"]:px=o
            elif o>=p["target"]:px=o
            if px is not None:
                proceeds=p["shares"]*px*(1-XC);cash+=proceeds
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
            reqrisk+=RB*eqo;eligible+=1
            raw.append({**c,"symbol":s,"entry_price":op,"lower":lo,"upper":hi,"target":target,
                        "entry_fraction":ef,"risk_per_dollar":riskpd,"request":rq})
        allocs=allocate(policy,raw,cash)
        for x,amt in zip(raw,allocs):
            if amt<=1e-12:blocked+=1;continue
            funded_nonzero+=1
            if amt+1e-12<x["request"]:partial+=1
            invest=amt*(1-EC);cash-=amt
            pos[x["symbol"]]={**x,"shares":invest/x["entry_price"],"cost_basis":amt,"hold":1,"last":x["entry_price"]}
            realrisk+=amt*x["risk_per_dollar"];entries+=1

        for s in list(pos):
            p=pos[s];b=bm.get(s,{}).get(d)
            if b is None:continue
            lo=float(b["low"]);hi=float(b["high"]);cl=float(b["close"]);px=None
            if lo<=p["lower"]:px=p["lower"]
            elif hi>=p["target"]:px=p["target"]
            elif p["hold"]>=H:px=cl
            if px is not None:
                proceeds=p["shares"]*px*(1-XC);cash+=proceeds
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
      "eligible_entries":eligible,"entries":entries,"blocked_entries":blocked,"partial_entries":partial,
      "funded_nonzero_share":funded_nonzero/eligible if eligible else None,
      "risk_realization_ratio":realrisk/reqrisk if reqrisk else None,
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
    policies=("LIQUIDITY_FIRST_SEQUENTIAL","PRO_RATA","LIQUIDITY_WEIGHTED_LINEAR","LIQUIDITY_WEIGHTED_INVERSE_RANK","LIQUIDITY_WEIGHTED_INVERSE_SQRT","TWO_TIER_LIQUIDITY")
    rows=[];summary={"schema":"PURE-BOX-SIMPLE-CORE-SMOOTH-CAPITAL-ALLOCATION-V34","results":{}}
    for p in policies:
        r=run(cs,cal,bm,p);summary["results"][p]=r;rows.append({"policy":p,**r})
    pd.DataFrame(rows).to_csv(out/"results.csv",index=False)
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(pd.DataFrame(rows)[["policy","total_return","cagr","max_drawdown","daily_sharpe","rolling_12m_min_return","funded_nonzero_share","top5_abs_funded_pnl_share"]].to_string(index=False))
if __name__=="__main__":main()
