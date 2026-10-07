#!/usr/bin/env python3
from __future__ import annotations

import argparse, json, math
from pathlib import Path
import pandas as pd

import research_pure_box_large_gap_retest_lift_historical_portfolio_v10 as base

ALLOCS=(0.10,0.20,0.25,0.33,0.50)
TARGETS=(0.60,0.80)

def cagr(start,end,years):
    if start<=0 or end<=0 or years<=0:
        return None
    return (end/start)**(1/years)-1

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--anatomy-labels",required=True)
    ap.add_argument("--resilience-labels",required=True)
    ap.add_argument("--thresholds",required=True)
    ap.add_argument("--source-dir",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()

    out=Path(a.outdir); out.mkdir(parents=True,exist_ok=True)

    merged=base.merge_labels(a.anatomy_labels,a.resilience_labels)
    thresholds=base.load_thresholds(a.thresholds)
    classified=base.classify_candidates(merged,thresholds)

    z=classified[
        (classified.rank_cap==500) &
        (classified.gap_method=="EXPANDING") &
        (classified.state=="RETEST_LIFT")
    ].copy()
    symbols=set(z.symbol.astype(str)); symbols.add("SPY")
    bars,calendar=base.load_bars(a.source_dir,symbols)
    years=(pd.Timestamp(calendar[-1])-pd.Timestamp(calendar[0])).days/365.2425

    rows=[]
    detail={}
    for alloc in ALLOCS:
        base.ALLOC=alloc
        for target in TARGETS:
            r=base.run_portfolio(z,bars,calendar,target)
            row={
                "allocation_per_event":alloc,
                "target_fraction":target,
                "candidate_n":int(len(z)),
                "total_return":float(r["total_return"]),
                "cagr":cagr(float(r["start_equity"]),float(r["end_equity"]),years),
                "max_drawdown":float(r["max_drawdown"]),
                "daily_sharpe":None if r["daily_sharpe"] is None else float(r["daily_sharpe"]),
                "avg_exposure":float(r["avg_exposure"]),
                "completed_trades":int(r["completed_trades"]),
                "open_positions_at_end":int(r["open_positions_at_end"]),
                "profit_factor":None if r["profit_factor"] is None else float(r["profit_factor"]),
                "mean_trade":None if r["mean_trade"] is None else float(r["mean_trade"]),
                "win_rate":None if r["win_rate"] is None else float(r["win_rate"]),
                "yearly_returns":r["yearly_returns"],
            }
            rows.append(row)
            key=f"a{int(round(alloc*100))}__t{int(round(target*100))}"
            detail[key]=row

    df=pd.DataFrame(rows)
    df.to_csv(out/"capital_utilization_results.csv",index=False)

    # Adjacent monotonicity diagnostics per target.
    diagnostics={}
    for target in TARGETS:
        q=df[df.target_fraction==target].sort_values("allocation_per_event")
        diagnostics[f"t{int(target*100)}"]={
            "return_non_decreasing":bool((q.total_return.diff().dropna()>=-1e-12).all()),
            "exposure_non_decreasing":bool((q.avg_exposure.diff().dropna()>=-1e-12).all()),
            "best_return_allocation":float(q.loc[q.total_return.idxmax(),"allocation_per_event"]),
            "best_return":float(q.total_return.max()),
            "best_sharpe_allocation":float(q.loc[q.daily_sharpe.idxmax(),"allocation_per_event"]),
            "best_sharpe":float(q.daily_sharpe.max()),
        }

    summary={
        "schema":"LARGE-GAP-RETEST-LIFT-CAPITAL-UTILIZATION-V11",
        "research_only":True,
        "signal_contract":"Top500 / EXPANDING / RETEST_LIFT unchanged from V7",
        "window":[calendar[0],calendar[-1]],
        "allocation_grid":list(ALLOCS),
        "targets":list(TARGETS),
        "results":detail,
        "diagnostics":diagnostics,
        "automatic_production_change":False,
    }
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))

if __name__=="__main__":
    main()
