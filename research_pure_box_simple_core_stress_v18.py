#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,statistics,math
from collections import defaultdict
from datetime import date
from pathlib import Path
import pandas as pd
import research_pure_box_core_geometry_simplicity_v13 as v13

CAP=.50
RBS=(.0125,.015)
COSTS=(.0005,.001,.002)

def bottom20(cands):
    out=[]
    for c in cands:
        lo=float(c["lower"]);hi=float(c["upper"]);op=float(c["direct_entry_price"])
        if hi<=lo:continue
        ef=(op-lo)/(hi-lo)
        if ef<=.20:
            z=dict(c);z["entry_fraction"]=ef;out.append(z)
    return out

def delayed_candidates(cands,nxt,bm,delay):
    if delay==0:return cands
    out=[]
    for c in cands:
        d=str(c["direct_entry_date"])
        for _ in range(delay):
            d=nxt.get(d)
            if not d:break
        if not d:continue
        b=bm.get(str(c["symbol"]),{}).get(d)
        if b is None:continue
        op=float(b["open"]);lo=float(c["lower"]);hi=float(c["upper"])
        target=lo+.60*(hi-lo)
        if not(lo<op<target):continue
        z=dict(c);z["stress_entry_date"]=d;z["stress_entry_price"]=op;out.append(z)
    return out

def mdd(vals):
    if not vals:return None
    p=vals[0];d=0.
    for x in vals:
        p=max(p,x)
        if p>0:d=min(d,x/p-1)
    return d

def sharpe(vals):
    if len(vals)<3:return None
    rs=[vals[i]/vals[i-1]-1 for i in range(1,len(vals)) if vals[i-1]>0]
    if len(rs)<2:return None
    sd=statistics.stdev(rs)
    return None if sd==0 else statistics.mean(rs)/sd*math.sqrt(252)

def pf(rs):
    w=sum(x for x in rs if x>0);l=-sum(x for x in rs if x<0)
    return w/l if l>0 else None

def run(cands,calendar,bm,rb,cost,delay):
    cidx={d:i for i,d in enumerate(calendar)}
    by=defaultdict(list)
    edate="direct_entry_date" if delay==0 else "stress_entry_date"
    eprice="direct_entry_price" if delay==0 else "stress_entry_price"
    for c in cands:
        d=str(c[edate])
        if v13.VAL_START<=d<=v13.VAL_END and d in cidx:by[d].append(c)
    days=[d for d in calendar if v13.VAL_START<=d<=v13.VAL_END]
    cash=1.;pos={};eq=[];expo=[];tr=[]
    for d in days:
        for s in list(pos):
            b=bm.get(s,{}).get(d)
            if b is None:continue
            p=pos[s];op=float(b["open"]);px=None
            if op<=p["lower"]:px=op
            elif op>=p["target"]:px=op
            if px is not None:
                proceeds=p["shares"]*px*(1-cost);cash+=proceeds
                tr.append(proceeds/p["cost_basis"]-1);del pos[s]

        cand=[c for c in by.get(d,[]) if str(c["symbol"]) not in pos]
        cand.sort(key=lambda x:(str(x["symbol"]),str(x["signal_date"])))
        ded=[];seen=set()
        for c in cand:
            s=str(c["symbol"])
            if s in seen:continue
            seen.add(s);ded.append(c)
        cand=ded

        eqo=cash
        for s,p in pos.items():
            b=bm.get(s,{}).get(d);eqo+=p["shares"]*(float(b["open"]) if b is not None else p["last"])

        valid=[]
        for c in cand:
            s=str(c["symbol"]);b=bm.get(s,{}).get(d)
            if b is None:continue
            op=float(c[eprice]);lo=float(c["lower"]);hi=float(c["upper"]);target=lo+.60*(hi-lo)
            if not(lo<op<target):continue
            riskpd=1-(lo*(1-cost))/(op*(1+cost))
            if riskpd<=0:continue
            raw=rb*eqo/riskpd;req=min(raw,CAP*eqo)
            valid.append((c,op,lo,target,req))
        total=sum(x[4] for x in valid);sc=min(1.,cash/total) if total>0 else 0.
        for c,op,lo,target,req in valid:
            amt=req*sc
            if amt<=1e-12:continue
            invest=amt*(1-cost);cash-=amt;s=str(c["symbol"])
            pos[s]={"shares":invest/op,"cost_basis":amt,"entry_i":cidx[d],"lower":lo,"target":target,"last":op}

        for s in list(pos):
            p=pos[s];b=bm.get(s,{}).get(d);hold=cidx[d]-p["entry_i"]+1
            if b is None:
                if hold>=20:
                    proceeds=p["shares"]*p["last"]*(1-cost);cash+=proceeds
                    tr.append(proceeds/p["cost_basis"]-1);del pos[s]
                continue
            lo=float(b["low"]);hi=float(b["high"]);cl=float(b["close"]);px=None
            if lo<=p["lower"]:px=p["lower"]
            elif hi>=p["target"]:px=p["target"]
            elif hold>=20:px=cl
            if px is not None:
                proceeds=p["shares"]*px*(1-cost);cash+=proceeds
                tr.append(proceeds/p["cost_basis"]-1);del pos[s]
            else:p["last"]=cl

        val=cash;inv=0.
        for s,p in pos.items():
            b=bm.get(s,{}).get(d);px=float(b["close"]) if b is not None else p["last"];p["last"]=px
            z=p["shares"]*px;val+=z;inv+=z
        eq.append((d,val));expo.append(inv/val if val>0 else 0.)

    vals=[v for _,v in eq]
    edf=pd.DataFrame(eq,columns=["date","equity"]);edf["year"]=edf.date.str[:4]
    yearly={y:float(g.equity.iloc[-1]/g.equity.iloc[0]-1) for y,g in edf.groupby("year")}
    yearly_mdd={y:mdd(g.equity.tolist()) for y,g in edf.groupby("year")}
    roll=[]
    if len(edf)>=252:
        for i in range(251,len(edf)):
            g=edf.iloc[i-251:i+1]
            rv=float(g.equity.iloc[-1]/g.equity.iloc[0]-1)
            roll.append(rv)
    return {
      "total_return":vals[-1]/vals[0]-1,
      "max_drawdown":mdd(vals),
      "daily_sharpe":sharpe(vals),
      "avg_exposure":statistics.mean(expo),
      "completed_trades":len(tr),
      "profit_factor":pf(tr),
      "mean_trade":statistics.mean(tr) if tr else None,
      "win_rate":sum(x>0 for x in tr)/len(tr) if tr else None,
      "yearly_return":yearly,
      "yearly_mdd":yearly_mdd,
      "rolling_12m_min_return":min(roll) if roll else None,
      "rolling_12m_positive_share":sum(x>0 for x in roll)/len(roll) if roll else None,
      "rolling_12m_median_return":statistics.median(roll) if roll else None
    }

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=v13.load(a.indir)
    rows=[];summary={"schema":"PURE-BOX-SIMPLE-CORE-STRESS-V18","window":[v13.VAL_START,v13.VAL_END],"results":{}}
    for cap in (300,500):
        base=bottom20(v13.strict_signals(sig,cap,cal,idx,nxt,bm))
        for delay in (0,1):
            cs=delayed_candidates(base,nxt,bm,delay)
            for cost in COSTS:
                for rb in RBS:
                    r=run(cs,cal,bm,rb,cost,delay)
                    key=f"top{cap}__d{delay}__c{cost:.4f}__r{rb:.4f}"
                    summary["results"][key]={**r,"candidate_n":len(cs),"rank_cap":cap,"delay":delay,"cost":cost,"risk_budget":rb}
                    rows.append(summary["results"][key])
    pd.DataFrame(rows).to_csv(out/"results.csv",index=False)
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(pd.DataFrame(rows)[["rank_cap","delay","cost","risk_budget","candidate_n","total_return","max_drawdown","daily_sharpe","rolling_12m_min_return","rolling_12m_positive_share"]].to_string(index=False))
if __name__=="__main__":main()
