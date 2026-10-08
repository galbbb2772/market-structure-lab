#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,statistics,math
from collections import defaultdict
from datetime import date
from pathlib import Path
import pandas as pd
import research_pure_box_core_geometry_simplicity_v13 as v13
import research_pure_box_capital_architecture_v22 as v22

EC=v13.ENTRY_COST; XC=v13.EXIT_COST
CAP=.50; RB=.0125; H=15

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

def close_series(bm,sym,calendar,end_i,n=61):
    vals=[]
    start=max(0,end_i-n)
    for d in calendar[start:end_i]:
        b=bm.get(sym,{}).get(d)
        if b is not None: vals.append((d,float(b["close"])))
    return vals[-n:]

def returns_map(series):
    out={}
    for i in range(1,len(series)):
        p0=series[i-1][1];p1=series[i][1]
        if p0>0:out[series[i][0]]=p1/p0-1
    return out

def corr60(bm,calendar,cidx,s1,s2,entry_date):
    end_i=cidx[entry_date]
    a=returns_map(close_series(bm,s1,calendar,end_i,61))
    b=returns_map(close_series(bm,s2,calendar,end_i,61))
    ds=sorted(set(a)&set(b))
    if len(ds)<30:return None
    xa=[a[d] for d in ds]; xb=[b[d] for d in ds]
    ma=statistics.mean(xa);mb=statistics.mean(xb)
    va=sum((x-ma)**2 for x in xa);vb=sum((x-mb)**2 for x in xb)
    if va<=0 or vb<=0:return None
    return sum((x-ma)*(y-mb) for x,y in zip(xa,xb))/math.sqrt(va*vb)

def avg_abs_corr(item,held_syms,bm,calendar,cidx,d):
    cs=[]
    for h in held_syms:
        c=corr60(bm,calendar,cidx,item["symbol"],h,d)
        if c is not None:cs.append(abs(c))
    return statistics.mean(cs) if cs else .50

def order_items(policy,items,held_syms,bm,calendar,cidx,d):
    for x in items:
        x["avg_abs_corr"]=avg_abs_corr(x,held_syms,bm,calendar,cidx,d)
        upside=x["target"]/x["entry_price"]-1
        x["geo_rr"]=upside/x["risk_per_dollar"] if x["risk_per_dollar"]>0 else -1
        x["marginal_score"]=x["geo_rr"]/(1+x["avg_abs_corr"])
    if policy=="LIQUIDITY_FIRST":
        return sorted(items,key=lambda x:(x["liquidity_rank"],x["entry_fraction"],x["symbol"]))
    if policy=="LOW_ENTRY_FIRST":
        return sorted(items,key=lambda x:(x["entry_fraction"],x["liquidity_rank"],x["symbol"]))
    if policy=="DIVERSIFICATION_FIRST":
        return sorted(items,key=lambda x:(x["avg_abs_corr"],x["liquidity_rank"],x["entry_fraction"],x["symbol"]))
    if policy=="MARGINAL_GEOMETRY_DIVERSIFICATION":
        return sorted(items,key=lambda x:(-x["marginal_score"],x["liquidity_rank"],x["entry_fraction"],x["symbol"]))
    if policy=="HYBRID_LIQUIDITY_GEOMETRY":
        liq=sorted(items,key=lambda x:(x["liquidity_rank"],x["symbol"]))
        rr=sorted(items,key=lambda x:(-x["geo_rr"],x["symbol"]))
        lr={id(x):i for i,x in enumerate(liq,1)}; rrk={id(x):i for i,x in enumerate(rr,1)}
        return sorted(items,key=lambda x:(lr[id(x)]+rrk[id(x)],x["entry_fraction"],x["symbol"]))
    raise ValueError(policy)

def run(cands,calendar,bm,policy):
    cidx={d:i for i,d in enumerate(calendar)}
    by=defaultdict(list)
    for c in cands:
        d=str(c["direct_entry_date"])
        if v13.VAL_START<=d<=v13.VAL_END and d in cidx:by[d].append(c)
    days=[d for d in calendar if v13.VAL_START<=d<=v13.VAL_END]
    cash=1.;pos={};eq=[];expo=[];trs=[];funded_pnl=defaultdict(float)
    blocked=partial=entries=0;reqrisk=realrisk=0.;entry_corrs=[]
    for d in days:
        for s in list(pos):
            b=bm.get(s,{}).get(d)
            if b is None:continue
            p=pos[s];p["hold"]+=1
            o=float(b["open"]);px=None
            if o<=p["lower"]:px=o
            elif o>=p["target"]:px=o
            if px is not None:
                proceeds=p["shares"]*px*(1-XC);cash+=proceeds
                r=proceeds/p["cost_basis"]-1;trs.append(r);funded_pnl[s]+=p["cost_basis"]*r;del pos[s]

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
            rq=min(RB*eqo/riskpd,CAP*eqo);reqrisk+=RB*eqo
            raw.append({**c,"symbol":s,"entry_price":op,"lower":lo,"upper":hi,"target":target,
                        "entry_fraction":ef,"risk_per_dollar":riskpd,"request":rq})
        raw=order_items(policy,raw,list(pos),bm,calendar,cidx,d)
        rem=cash;allocs=[]
        for x in raw:
            if rem<=1e-12:
                allocs.append(0.);blocked+=1;continue
            amt=min(x["request"],rem);allocs.append(amt)
            if amt+1e-12<x["request"]:partial+=1
            rem-=amt
        for x,amt in zip(raw,allocs):
            if amt<=1e-12:continue
            invest=amt*(1-EC);cash-=amt
            pos[x["symbol"]]={**x,"shares":invest/x["entry_price"],"cost_basis":amt,"hold":1,"last":x["entry_price"]}
            entries+=1;realrisk+=amt*x["risk_per_dollar"];entry_corrs.append(x["avg_abs_corr"])

        for s in list(pos):
            p=pos[s];b=bm.get(s,{}).get(d)
            if b is None:continue
            lo=float(b["low"]);hi=float(b["high"]);cl=float(b["close"]);px=None
            if lo<=p["lower"]:px=p["lower"]
            elif hi>=p["target"]:px=p["target"]
            elif p["hold"]>=H:px=cl
            if px is not None:
                proceeds=p["shares"]*px*(1-XC);cash+=proceeds
                r=proceeds/p["cost_basis"]-1;trs.append(r);funded_pnl[s]+=p["cost_basis"]*r;del pos[s]
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
    absvals=sorted((abs(v) for v in funded_pnl.values()),reverse=True);tot=sum(absvals)
    return {
      "total_return":vals[-1]/vals[0]-1,"cagr":(vals[-1]/vals[0])**(1/yrs)-1,
      "max_drawdown":mdd(vals),"daily_sharpe":sharpe(vals),
      "avg_exposure":statistics.mean(expo),"idle_day_share":sum(x<.10 for x in expo)/len(expo),
      "completed_trades":len(trs),"profit_factor":pf(trs),"mean_trade":statistics.mean(trs) if trs else None,
      "entries":entries,"blocked_entries":blocked,"partial_entries":partial,
      "risk_realization_ratio":realrisk/reqrisk if reqrisk else None,
      "avg_entry_abs_corr":statistics.mean(entry_corrs) if entry_corrs else None,
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
    policies=("LIQUIDITY_FIRST","LOW_ENTRY_FIRST","DIVERSIFICATION_FIRST","MARGINAL_GEOMETRY_DIVERSIFICATION","HYBRID_LIQUIDITY_GEOMETRY")
    rows=[];summary={"schema":"PURE-BOX-SIMPLE-CORE-MARGINAL-CAPITAL-ALLOCATION-V33","results":{}}
    for pol in policies:
        r=run(cs,cal,bm,pol)
        summary["results"][pol]=r;rows.append({"policy":pol,**r})
    pd.DataFrame(rows).to_csv(out/"results.csv",index=False)
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(pd.DataFrame(rows)[["policy","total_return","cagr","max_drawdown","daily_sharpe","rolling_12m_min_return","avg_entry_abs_corr","top5_abs_funded_pnl_share"]].to_string(index=False))
if __name__=="__main__":main()
