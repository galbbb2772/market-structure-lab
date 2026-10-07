#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,math,statistics
from collections import defaultdict
from datetime import date
from pathlib import Path
import pandas as pd
import research_pure_box_core_geometry_simplicity_v13 as v13

RISK_BUDGETS=(.0025,.005,.0075,.01,.0125,.015)
CAP=.50
ENTRY_COST=v13.ENTRY_COST;EXIT_COST=v13.EXIT_COST

def run_risk(cands,calendar,bm,target_frac,max_hold,risk_budget=None,fixed=False):
    cidx={d:i for i,d in enumerate(calendar)}
    by=defaultdict(list)
    for c in cands:
        d=str(c["direct_entry_date"])
        if v13.VAL_START<=d<=v13.VAL_END and d in cidx:by[d].append(c)
    days=[d for d in calendar if v13.VAL_START<=d<=v13.VAL_END]
    cash=1.;pos={};eq=[];expo=[];trs=[];weights=[];planned=[];cap_hits=0;requests=0
    for d in days:
        for sym in list(pos):
            b=bm.get(sym,{}).get(d)
            if b is None:continue
            p=pos[sym];op=float(b["open"]);px=None
            if op<=p["lower"]:px=op
            elif op>=p["target"]:px=op
            if px is not None:
                proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                trs.append(proceeds/p["cost_basis"]-1);del pos[sym]
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
            op=float(b["open"]);lo=float(c["lower"]);hi=float(c["upper"])
            target=lo+target_frac*(hi-lo)
            if not(lo<op<target):continue
            riskpd=1.0-(lo*(1-EXIT_COST))/(op*(1+ENTRY_COST))
            if riskpd<=0:continue
            if fixed:
                req=.20*eqo; hit=False; prisk=req*riskpd/eqo
            else:
                raw=risk_budget*eqo/riskpd
                req=min(raw,CAP*eqo);hit=raw>CAP*eqo+1e-12;prisk=req*riskpd/eqo
            valid.append((c,op,lo,hi,target,riskpd,req,hit,prisk))
        total=sum(x[6] for x in valid)
        sc=min(1.,cash/total) if total>0 else 0.
        for c,op,lo,hi,target,riskpd,req,hit,prisk in valid:
            requests+=1
            if hit:cap_hits+=1
            amt=req*sc
            if amt<=1e-12:continue
            invest=amt*(1-ENTRY_COST);cash-=amt;s=str(c["symbol"])
            pos[s]={"shares":invest/op,"cost_basis":amt,"entry_i":cidx[d],"lower":lo,"target":target,"last":op}
            weights.append(amt/eqo);planned.append((amt/eqo)*riskpd)
        for s in list(pos):
            p=pos[s];b=bm.get(s,{}).get(d);hold=cidx[d]-p["entry_i"]+1
            if b is None:
                if hold>=max_hold:
                    proceeds=p["shares"]*p["last"]*(1-EXIT_COST);cash+=proceeds
                    trs.append(proceeds/p["cost_basis"]-1);del pos[s]
                continue
            lo=float(b["low"]);hi=float(b["high"]);cl=float(b["close"]);px=None
            if lo<=p["lower"]:px=p["lower"]
            elif hi>=p["target"]:px=p["target"]
            elif hold>=max_hold:px=cl
            if px is not None:
                proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                trs.append(proceeds/p["cost_basis"]-1);del pos[s]
            else:p["last"]=cl
        val=cash;inv=0.
        for s,p in pos.items():
            b=bm.get(s,{}).get(d);px=float(b["close"]) if b is not None else p["last"];p["last"]=px
            z=p["shares"]*px;val+=z;inv+=z
        eq.append((d,val));expo.append(inv/val if val>0 else 0.)
    vals=[x[1] for x in eq];yrs=max((date.fromisoformat(days[-1])-date.fromisoformat(days[0])).days/365.2425,1/365)
    return {
      "total_return":vals[-1]/vals[0]-1,"cagr":(vals[-1]/vals[0])**(1/yrs)-1,
      "max_drawdown":v13.mdd(vals),"daily_sharpe":v13.sharpe(vals),
      "avg_exposure":statistics.mean(expo),"completed_trades":len(trs),"profit_factor":v13.pf(trs),
      "mean_trade":statistics.mean(trs) if trs else None,"win_rate":sum(x>0 for x in trs)/len(trs) if trs else None,
      "avg_realized_initial_weight":statistics.mean(weights) if weights else None,
      "median_realized_initial_weight":statistics.median(weights) if weights else None,
      "cap_hit_fraction":cap_hits/requests if requests else 0.,
      "avg_planned_account_risk":statistics.mean(planned) if planned else None
    }

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=v13.load(a.indir)
    rows=[];summary={"schema":"PURE-BOX-RISK-TO-INVALIDATION-SIZING-V14","window":[v13.VAL_START,v13.VAL_END],"results":{}}
    for cap in (300,500):
        c=v13.strict_signals(sig,cap,cal,idx,nxt,bm)
        for target in (.60,1.0):
            r=run_risk(c,cal,bm,target,20,fixed=True)
            key=f"top{cap}__t{int(target*100)}__fixed20";summary["results"][key]=r
            rows.append({"rank_cap":cap,"target_fraction":target,"lane":"fixed20","risk_budget":None,**r})
            for rb in RISK_BUDGETS:
                r=run_risk(c,cal,bm,target,20,risk_budget=rb,fixed=False)
                key=f"top{cap}__t{int(target*100)}__risk{rb:.4f}";summary["results"][key]=r
                rows.append({"rank_cap":cap,"target_fraction":target,"lane":"risk","risk_budget":rb,**r})
    pd.DataFrame(rows).to_csv(out/"results.csv",index=False)
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
