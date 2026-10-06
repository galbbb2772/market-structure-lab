#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,statistics
from pathlib import Path
import pandas as pd

ap=argparse.ArgumentParser()
ap.add_argument("--indir",required=True)
ap.add_argument("--outdir",required=True)
a=ap.parse_args()
src=Path(a.indir);out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

files=sorted(src.glob("**/entry_confirmation_mechanism_*.csv"))
if len(files)<12:raise RuntimeError(f"expected 12 shards, got {len(files)}")
x=pd.concat([pd.read_csv(f) for f in files],ignore_index=True)
x.to_csv(out/"annual_results.csv",index=False)

summary={"schema":"PURE-BOX-ENTRY-CONFIRMATION-MECHANISM-V1.1","lanes":{}}
for cap in (300,500):
    summary["lanes"][f"top{cap}"]={}
    for sleeve in ("all","fresh","wide_fresh"):
        summary["lanes"][f"top{cap}"][sleeve]={}
        for variant in sorted(x.variant.unique()):
            g=x[(x.rank_cap==cap)&(x.sleeve==sleeve)&(x.variant==variant)].sort_values("year")
            comp=1.0; vals=[]
            for r in g.itertuples():
                comp*=1+float(r.total_return);vals.append(float(r.total_return))
            summary["lanes"][f"top{cap}"][sleeve][variant]={
              "compounded_walk_forward_return":comp-1,
              "positive_years":sum(v>0 for v in vals),
              "years":len(vals),
              "avg_year_return":statistics.mean(vals) if vals else None,
              "avg_sharpe":float(g.sharpe.mean()) if len(g) else None,
              "avg_exposure":float(g.avg_exposure.mean()) if len(g) else None,
              "avg_profit_factor":float(g.profit_factor.mean()) if len(g) else None,
              "total_trades":int(g.trades.sum()) if len(g) else 0,
              "avg_confirmation_rate":float(g.confirmation_rate.mean()) if len(g) else None,
              "avg_entry_vs_baseline_next_open":float(g.avg_entry_vs_baseline_next_open.mean()) if len(g) else None,
              "yearly":{str(int(r.year)):float(r.total_return) for r in g.itertuples()},
              "yearly_mdd":{str(int(r.year)):float(r.max_drawdown) for r in g.itertuples()},
              "yearly_sharpe":{str(int(r.year)):float(r.sharpe) for r in g.itertuples()},
            }

(out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
print(json.dumps(summary,indent=2))
