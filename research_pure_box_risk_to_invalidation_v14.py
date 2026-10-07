#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,math,statistics
from collections import defaultdict
from datetime import date
from pathlib import Path
import pandas as pd

import research_pure_box_core_geometry_simplicity_v13 as core

VAL_START=core.VAL_START
VAL_END=core.VAL_END
ENTRY_COST=core.ENTRY_COST
EXIT_COST=core.EXIT_COST
TARGET_FRAC=0.60
MAX_HOLD=20
SINGLE_CAP=0.33
RISK_BUDGETS=(0.0025,0.0050,0.0075,0.0100)

def mdd(vals):
    if not vals:return None
    p=vals[0];d=0.0
    for x in vals:
        p=max(p,x)
        if p>0:d=min(d,x/p-1)
    return d

def sharpe(vals):
    if len(vals)<3:return None
    r=[vals[i]/vals[i-1]-1 for i in range(1,len(vals)) if vals[i-1]>0]
    if len(r)<2:return None
    sd=statistics.stdev(r)
    return None if sd==0 else statistics.mean(r)/sd*math.sqrt(252)

def pf(rs):
    w=sum(x for x in rs if x>0);l=-sum(x for x in rs if x<0)
    return w/l if l>0 else (float("inf") if w>0 else None)

def run(cands,calendar,bm,mode,risk_budget=None):
    cidx={d:i for i,d in enumerate(calendar)}
    byday=defaultdict(list)
    for c in cands:
        d=str(c["direct_entry_date"])
        if VAL_START<=d<=VAL_END and d in cidx:
            byday[d].append(c)

    days=[d for d in calendar if VAL_START<=d<=VAL_END]
    cash=1.0;pos={};eq=[];expo=[];tr=[]
    requested_weights=[];realized_risks=[]
    capped_entries=0;entry_count=0;cash_constrained_days=0;entry_days=0

    for d in days:
        # Opening gap exits.
        for sym in list(pos):
            b=bm.get(sym,{}).get(d)
            if b is None:continue
            p=pos[sym];op=float(b["open"]);px=None;reason=None
            if op<=p["lower"]:px=op;reason="stop_gap"
            elif op>=p["target"]:px=op;reason="target_gap"
            if px is not None:
                proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                tr.append(proceeds/p["cost_basis"]-1);del pos[sym]

        cand=[c for c in byday.get(d,[]) if str(c["symbol"]) not in pos]
        cand.sort(key=lambda x:(str(x["symbol"]),str(x["signal_date"])))
        ded=[];seen=set()
        for c in cand:
            sym=str(c["symbol"])
            if sym in seen:continue
            seen.add(sym);ded.append(c)
        cand=ded

        eqo=cash
        for sym,p in pos.items():
            b=bm.get(sym,{}).get(d)
            eqo+=p["shares"]*(float(b["open"]) if b is not None else p["last"])

        valid=[]
        req=[]
        for c in cand:
            sym=str(c["symbol"]);b=bm.get(sym,{}).get(d)
            if b is None:continue
            op=float(b["open"]);lo=float(c["lower"]);hi=float(c["upper"])
            target=lo+TARGET_FRAC*(hi-lo)
            if not(lo<op<target):continue
            stop_dist=(op-lo)/op
            if stop_dist<=1e-9:continue
            if mode=="fixed20":
                w=0.20
                capped=False
            else:
                raw=float(risk_budget)/stop_dist
                w=min(SINGLE_CAP,raw)
                capped=raw>SINGLE_CAP
            valid.append((c,op,lo,hi,target,stop_dist,w,capped))
            req.append(w*eqo)

        if valid:
            entry_days+=1
            budget=min(cash,sum(req))
            sc=budget/sum(req) if req else 0.0
            if sc<1-1e-12:cash_constrained_days+=1
            for (c,op,lo,hi,target,stop_dist,w,capped),rq in zip(valid,req):
                amt=rq*sc
                if amt<=1e-12 or amt>cash+1e-10:continue
                invest=amt*(1-ENTRY_COST);cash-=amt
                sym=str(c["symbol"])
                realized_weight=amt/eqo if eqo>0 else 0.0
                requested_weights.append(w)
                realized_risks.append(realized_weight*stop_dist)
                capped_entries+=int(capped)
                entry_count+=1
                pos[sym]={"shares":invest/op,"cost_basis":amt,"entry_i":cidx[d],
                          "lower":lo,"upper":hi,"target":target,"last":op}

        # Same-day/intraday lifecycle.
        for sym in list(pos):
            p=pos[sym];b=bm.get(sym,{}).get(d);hold=cidx[d]-p["entry_i"]+1
            if b is None:
                if hold>=MAX_HOLD:
                    px=p["last"];proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                    tr.append(proceeds/p["cost_basis"]-1);del pos[sym]
                continue
            lo=float(b["low"]);hi=float(b["high"]);cl=float(b["close"]);px=None
            if lo<=p["lower"]:px=p["lower"]
            elif hi>=p["target"]:px=p["target"]
            elif hold>=MAX_HOLD:px=cl
            if px is not None:
                proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                tr.append(proceeds/p["cost_basis"]-1);del pos[sym]
            else:p["last"]=cl

        val=cash;inv=0.0
        for sym,p in pos.items():
            b=bm.get(sym,{}).get(d);px=float(b["close"]) if b is not None else p["last"];p["last"]=px
            v=p["shares"]*px;val+=v;inv+=v
        eq.append((d,val));expo.append(inv/val if val>0 else 0.0)

    vals=[v for _,v in eq];rs=[float(x) for x in tr]
    yrs=max((date.fromisoformat(days[-1])-date.fromisoformat(days[0])).days/365.2425,1/365)
    return {
      "total_return":vals[-1]/vals[0]-1,
      "cagr":(vals[-1]/vals[0])**(1/yrs)-1,
      "max_drawdown":mdd(vals),
      "daily_sharpe":sharpe(vals),
      "avg_exposure":statistics.mean(expo) if expo else 0.0,
      "completed_trades":len(tr),
      "open_positions_at_end":len(pos),
      "profit_factor":pf(rs),
      "mean_trade":statistics.mean(rs) if rs else None,
      "win_rate":sum(x>0 for x in rs)/len(rs) if rs else None,
      "avg_requested_weight":statistics.mean(requested_weights) if requested_weights else None,
      "avg_realized_initial_risk":statistics.mean(realized_risks) if realized_risks else None,
      "single_cap_share":capped_entries/entry_count if entry_count else None,
      "cash_constrained_day_share":cash_constrained_days/entry_days if entry_days else None,
      "entries":entry_count
    }

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=core.load(a.indir)

    rows=[];results={}
    for cap in (300,500):
        cands=core.strict_signals(sig,cap,cal,idx,nxt,bm)
        base=run(cands,cal,bm,"fixed20")
        key=f"top{cap}__FIXED20"
        results[key]={**base,"candidate_n":len(cands),"mode":"fixed20","risk_budget":None}
        rows.append({"rank_cap":cap,"lane":"FIXED20",**results[key]})
        for rb in RISK_BUDGETS:
            r=run(cands,cal,bm,"risk",rb)
            lane=f"RISK_{rb*100:.2f}PCT"
            key=f"top{cap}__{lane}"
            results[key]={**r,"candidate_n":len(cands),"mode":"risk","risk_budget":rb}
            rows.append({"rank_cap":cap,"lane":lane,**results[key]})

    df=pd.DataFrame(rows)
    df.to_csv(out/"results.csv",index=False)
    summary={
      "schema":"PURE-BOX-RISK-TO-INVALIDATION-V14",
      "window":[VAL_START,VAL_END],
      "single_name_cap":SINGLE_CAP,
      "target_fraction":TARGET_FRAC,
      "max_hold":MAX_HOLD,
      "risk_budget_grid":list(RISK_BUDGETS),
      "results":results,
      "automatic_production_change":False
    }
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))

if __name__=="__main__":main()
