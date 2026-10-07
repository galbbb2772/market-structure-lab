#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math, statistics
from collections import defaultdict
from pathlib import Path
import pandas as pd

import research_pure_box_large_gap_retest_lift_historical_portfolio_v10 as base

ALLOC=0.20
TARGETS=(0.60,0.80)

def pf(v):
    w=sum(x for x in v if x>0); l=-sum(x for x in v if x<0)
    return w/l if l>0 else (float("inf") if w>0 else None)

def mdd(vals):
    if not vals:return None
    p=vals[0]; d=0.0
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

def run_priority(cands,bars,calendar,target_fraction):
    cidx={d:i for i,d in enumerate(calendar)}
    bybar={str(s):{str(r["date"]):r for r in g.to_dict("records")}
           for s,g in bars.groupby("ticker",sort=False)}
    byday=defaultdict(list)
    for r in cands.to_dict("records"):
        d=str(r["entry_date"])
        if d in cidx:byday[d].append(r)

    cash=1.0; pos={}; eq=[]; expo=[]; trades=[]
    rl_entries=0; rwl_entries=0

    for d in calendar:
        for sym in list(pos):
            b=bybar.get(sym,{}).get(d)
            if b is None:continue
            p=pos[sym]; op=float(b["open"]); px=None; reason=None
            if op<=p["lower"]:px=op;reason="stop_gap"
            elif op>=p["target"]:px=op;reason="target_gap"
            if px is not None:
                proceeds=p["shares"]*px*(1-base.EXIT_COST);cash+=proceeds
                trades.append({**p,"exit_date":d,"net_return":proceeds/p["cost_basis"]-1})
                del pos[sym]

        day=[x for x in byday.get(d,[]) if str(x["symbol"]) not in pos]
        # RL first, then RWL. Stable tie-breaker inside each priority.
        day.sort(key=lambda x:(0 if x["state"]=="RETEST_LIFT" else 1,str(x["symbol"]),str(x["signal_date"])))
        ded=[];seen=set()
        for x in day:
            sym=str(x["symbol"])
            if sym in seen:continue
            seen.add(sym);ded.append(x)
        day=ded

        eq_open=cash
        for sym,p in pos.items():
            b=bybar.get(sym,{}).get(d)
            eq_open+=p["shares"]*(float(b["open"]) if b is not None else p["last"])

        for priority_state in ("RETEST_LIFT","RETEST_WEAK_LIFT"):
            group=[]
            for c in day:
                if c["state"]!=priority_state:continue
                sym=str(c["symbol"]); b=bybar.get(sym,{}).get(d)
                if b is None or sym in pos:continue
                op=float(b["open"]); lo=float(c["lower"]); hi=float(c["upper"])
                target=lo+target_fraction*(hi-lo)
                if lo<op<target:group.append((c,op,lo,hi,target))
            if not group or cash<=1e-12:continue
            req=[ALLOC*eq_open]*len(group)
            budget=min(cash,sum(req)); scale=budget/sum(req) if req else 0.0
            for (c,op,lo,hi,target),rq in zip(group,req):
                amt=rq*scale
                if amt<=1e-12 or amt>cash+1e-10:continue
                invest=amt*(1-base.ENTRY_COST);cash-=amt
                sym=str(c["symbol"])
                pos[sym]={
                    "symbol":sym,"state":priority_state,
                    "signal_date":str(c["signal_date"]),"confirmation_date":str(c["confirmation_date"]),
                    "entry_date":d,"entry_price":op,"lower":lo,"upper":hi,"target":target,
                    "shares":invest/op,"cost_basis":amt,"entry_i":cidx[d],"last":op
                }
                if priority_state=="RETEST_LIFT":rl_entries+=1
                else:rwl_entries+=1

        for sym in list(pos):
            p=pos[sym]; b=bybar.get(sym,{}).get(d); hold=cidx[d]-p["entry_i"]+1
            if b is None:
                if hold>=base.MAX_HOLD:
                    px=p["last"]; proceeds=p["shares"]*px*(1-base.EXIT_COST);cash+=proceeds
                    trades.append({**p,"exit_date":d,"net_return":proceeds/p["cost_basis"]-1})
                    del pos[sym]
                continue
            lo=float(b["low"]);hi=float(b["high"]);cl=float(b["close"]);px=None
            if lo<=p["lower"]:px=p["lower"]
            elif hi>=p["target"]:px=p["target"]
            elif hold>=base.MAX_HOLD:px=cl
            if px is not None:
                proceeds=p["shares"]*px*(1-base.EXIT_COST);cash+=proceeds
                trades.append({**p,"exit_date":d,"net_return":proceeds/p["cost_basis"]-1})
                del pos[sym]
            else:p["last"]=cl

        val=cash; inv=0.0
        for sym,p in pos.items():
            b=bybar.get(sym,{}).get(d); px=float(b["close"]) if b is not None else p["last"];p["last"]=px
            q=p["shares"]*px;val+=q;inv+=q
        eq.append({"date":d,"equity":val});expo.append(inv/val if val>0 else 0.0)

    vals=[x["equity"] for x in eq]; rs=[float(t["net_return"]) for t in trades]
    rl_realized=sum(1 for t in trades if t["state"]=="RETEST_LIFT")
    rwl_realized=sum(1 for t in trades if t["state"]=="RETEST_WEAK_LIFT")
    return {
      "start_equity":1.0,"end_equity":vals[-1] if vals else 1.0,
      "total_return":vals[-1]-1 if vals else 0.0,
      "max_drawdown":mdd(vals),"daily_sharpe":sharpe(vals),
      "avg_exposure":statistics.mean(expo) if expo else 0.0,
      "completed_trades":len(trades),"profit_factor":pf(rs),
      "mean_trade":statistics.mean(rs) if rs else None,
      "win_rate":sum(x>0 for x in rs)/len(rs) if rs else None,
      "rl_entries":rl_entries,"rwl_entries":rwl_entries,
      "rl_realized_trades":rl_realized,"rwl_realized_trades":rwl_realized
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--anatomy-labels",required=True)
    ap.add_argument("--resilience-labels",required=True)
    ap.add_argument("--thresholds",required=True)
    ap.add_argument("--source-dir",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

    merged=base.merge_labels(a.anatomy_labels,a.resilience_labels)
    thresholds=base.load_thresholds(a.thresholds)
    classified=base.classify_candidates(merged,thresholds)
    z=classified[(classified.rank_cap==500)&(classified.gap_method=="EXPANDING")].copy()
    syms=set(z.symbol.astype(str));syms.add("SPY")
    bars,calendar=base.load_bars(a.source_dir,syms)

    lanes={
      "RL_ONLY":["RETEST_LIFT"],
      "RETEST_POOL":["RETEST_LIFT","RETEST_WEAK_LIFT"],
      "LIFT_POOL_CONTROL":["RETEST_LIFT","NO_RETEST_LIFT"],
      "EXTREME_ALL_CONTROL":["RETEST_LIFT","RETEST_WEAK_LIFT","NO_RETEST_LIFT","NO_RETEST_WEAK_LIFT"],
    }
    rows=[];results={}
    base.ALLOC=ALLOC
    for target in TARGETS:
      for name,states in lanes.items():
        q=z[z.state.isin(states)].copy()
        r=base.run_portfolio(q,bars,calendar,target)
        row={k:v for k,v in r.items() if k not in ("trade_rows","equity_rows","yearly_returns")}
        row.update({"lane":name,"target_fraction":target,"candidate_n":int(len(q))})
        rows.append(row);results[f"{name}__t{int(target*100)}"]=row
      q=z[z.state.isin(["RETEST_LIFT","RETEST_WEAK_LIFT"])].copy()
      r=run_priority(q,bars,calendar,target)
      row={**r,"lane":"RL_PRIORITY_RWL_FILLER","target_fraction":target,"candidate_n":int(len(q))}
      rows.append(row);results[f"RL_PRIORITY_RWL_FILLER__t{int(target*100)}"]=row

    df=pd.DataFrame(rows)
    df.to_csv(out/"state_expansion_results.csv",index=False)

    diag={}
    for target in TARGETS:
        core=results[f"RL_ONLY__t{int(target*100)}"]
        fill=results[f"RL_PRIORITY_RWL_FILLER__t{int(target*100)}"]
        diag[f"t{int(target*100)}"]={
          "return_improved":fill["total_return"]>core["total_return"],
          "exposure_improved":fill["avg_exposure"]>core["avg_exposure"],
          "mdd_better_than_minus20pct":fill["max_drawdown"]>-0.20,
          "sharpe_retention":None if not core["daily_sharpe"] else fill["daily_sharpe"]/core["daily_sharpe"],
          "rl_realized_not_reduced":fill["rl_realized_trades"]>=core["completed_trades"],
        }

    summary={
      "schema":"LARGE-GAP-RETEST-LIFT-CAPITAL-FILLER-V12",
      "research_only":True,
      "window":[calendar[0],calendar[-1]],
      "allocation_per_event":ALLOC,
      "results":results,
      "diagnostics":diag,
      "automatic_production_change":False
    }
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))

if __name__=="__main__":
    main()
