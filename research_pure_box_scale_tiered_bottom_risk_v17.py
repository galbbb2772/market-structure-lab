#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,statistics
from collections import defaultdict
from datetime import date
from pathlib import Path
import pandas as pd
import research_pure_box_core_geometry_simplicity_v13 as v13

ENTRY_COST=v13.ENTRY_COST; EXIT_COST=v13.EXIT_COST; CAP=.50
LANES=[
 ("equal_1.00",.01,.01),("equal_1.25",.0125,.0125),("equal_1.50",.015,.015),
 ("L075_S025",.0075,.0025),("L100_S025",.01,.0025),("L100_S050",.01,.005),
 ("L125_S025",.0125,.0025),("L125_S050",.0125,.005),
 ("L150_S025",.015,.0025),("L150_S050",.015,.005),("L150_S075",.015,.0075)
]

def bottom20(cands):
    out=[]
    for c in cands:
        lo=float(c["lower"]);hi=float(c["upper"]);op=float(c["direct_entry_price"])
        if hi<=lo:continue
        ef=(op-lo)/(hi-lo)
        if ef<=.20:
            z=dict(c);z["entry_fraction"]=ef;out.append(z)
    return out

def run(cands,calendar,bm,large_risk=None,small_risk=None,fixed20=False):
    cidx={d:i for i,d in enumerate(calendar)}
    by=defaultdict(list)
    for c in cands:
        d=str(c["direct_entry_date"])
        if v13.VAL_START<=d<=v13.VAL_END and d in cidx:by[d].append(c)
    days=[d for d in calendar if v13.VAL_START<=d<=v13.VAL_END]
    cash=1.;pos={};eq=[];expo=[];trs=[];weights=[];risks=[];counts={"small":0,"large":0}
    for d in days:
        for s in list(pos):
            b=bm.get(s,{}).get(d)
            if b is None:continue
            p=pos[s];op=float(b["open"]);px=None
            if op<=p["lower"]:px=op
            elif op>=p["target"]:px=op
            if px is not None:
                pr=p["shares"]*px*(1-EXIT_COST);cash+=pr;trs.append(pr/p["cost_basis"]-1);del pos[s]
        cand=[c for c in by.get(d,[]) if str(c["symbol"]) not in pos]
        cand.sort(key=lambda x:(str(x["symbol"]),str(x["signal_date"])))
        ded=[];seen=set()
        for c in cand:
            s=str(c["symbol"])
            if s in seen:continue
            seen.add(s);ded.append(c)
        eqo=cash
        for s,p in pos.items():
            b=bm.get(s,{}).get(d);eqo+=p["shares"]*(float(b["open"]) if b else p["last"])
        valid=[]
        for c in ded:
            s=str(c["symbol"]);b=bm.get(s,{}).get(d)
            if b is None:continue
            op=float(b["open"]);lo=float(c["lower"]);hi=float(c["upper"]);target=lo+.60*(hi-lo)
            if not(lo<op<target):continue
            riskpd=1-(lo*(1-EXIT_COST))/(op*(1+ENTRY_COST))
            if riskpd<=0:continue
            if fixed20:req=.20*eqo
            else:
                rb=large_risk if str(c["scale"])=="large" else small_risk
                req=min(rb*eqo/riskpd,CAP*eqo)
            valid.append((c,op,lo,target,riskpd,req))
        tot=sum(x[5] for x in valid);sc=min(1.,cash/tot) if tot else 0.
        for c,op,lo,target,riskpd,req in valid:
            amt=req*sc
            if amt<=1e-12:continue
            cash-=amt;invest=amt*(1-ENTRY_COST);s=str(c["symbol"])
            pos[s]={"shares":invest/op,"cost_basis":amt,"entry_i":cidx[d],"lower":lo,"target":target,"last":op}
            weights.append(amt/eqo);risks.append((amt/eqo)*riskpd);counts[str(c["scale"])]+=1
        for s in list(pos):
            p=pos[s];b=bm.get(s,{}).get(d);hold=cidx[d]-p["entry_i"]+1
            if b is None:
                if hold>=20:
                    pr=p["shares"]*p["last"]*(1-EXIT_COST);cash+=pr;trs.append(pr/p["cost_basis"]-1);del pos[s]
                continue
            lo=float(b["low"]);hi=float(b["high"]);cl=float(b["close"]);px=None
            if lo<=p["lower"]:px=p["lower"]
            elif hi>=p["target"]:px=p["target"]
            elif hold>=20:px=cl
            if px is not None:
                pr=p["shares"]*px*(1-EXIT_COST);cash+=pr;trs.append(pr/p["cost_basis"]-1);del pos[s]
            else:p["last"]=cl
        val=cash;inv=0.
        for s,p in pos.items():
            b=bm.get(s,{}).get(d);px=float(b["close"]) if b else p["last"];p["last"]=px
            z=p["shares"]*px;val+=z;inv+=z
        eq.append((d,val));expo.append(inv/val if val>0 else 0)
    vals=[x[1] for x in eq];yrs=max((date.fromisoformat(days[-1])-date.fromisoformat(days[0])).days/365.2425,1/365)
    return {"total_return":vals[-1]/vals[0]-1,"cagr":(vals[-1]/vals[0])**(1/yrs)-1,
      "max_drawdown":v13.mdd(vals),"daily_sharpe":v13.sharpe(vals),"avg_exposure":statistics.mean(expo),
      "completed_trades":len(trs),"profit_factor":v13.pf(trs),"mean_trade":statistics.mean(trs) if trs else None,
      "win_rate":sum(x>0 for x in trs)/len(trs) if trs else None,
      "avg_initial_weight":statistics.mean(weights) if weights else None,
      "avg_planned_risk":statistics.mean(risks) if risks else None,
      "small_entries":counts["small"],"large_entries":counts["large"]}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=v13.load(a.indir)
    rows=[];summary={"schema":"PURE-BOX-SCALE-TIERED-BOTTOM-RISK-V17","results":{}}
    for cap in (300,500):
        c=bottom20(v13.strict_signals(sig,cap,cal,idx,nxt,bm))
        r=run(c,cal,bm,fixed20=True);summary["results"][f"top{cap}__fixed20"]={**r,"candidate_n":len(c)}
        rows.append({"rank_cap":cap,"lane":"fixed20","large_risk":None,"small_risk":None,"candidate_n":len(c),**r})
        for name,lr,sr in LANES:
            r=run(c,cal,bm,lr,sr);summary["results"][f"top{cap}__{name}"]={**r,"candidate_n":len(c),"large_risk":lr,"small_risk":sr}
            rows.append({"rank_cap":cap,"lane":name,"large_risk":lr,"small_risk":sr,"candidate_n":len(c),**r})
    pd.DataFrame(rows).to_csv(out/"results.csv",index=False)
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(pd.DataFrame(rows)[["rank_cap","lane","total_return","max_drawdown","daily_sharpe","avg_exposure","profit_factor"]].to_string(index=False))
if __name__=="__main__":main()
