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

files=sorted(src.glob("**/position_sizing_v2_*.csv"))
if len(files)<12:raise RuntimeError(f"expected 12 shards, got {len(files)}")
x=pd.concat([pd.read_csv(f) for f in files],ignore_index=True)
x.to_csv(out/"annual_results.csv",index=False)

summary={"schema":"PURE-BOX-POSITION-SIZING-V2","lanes":{}}
for cap in (300,500):
    summary["lanes"][f"top{cap}"]={}
    for sleeve in ("fresh","wide_fresh"):
        summary["lanes"][f"top{cap}"][sleeve]={}
        z=x[(x.rank_cap==cap)&(x.sleeve==sleeve)]
        for ev in sorted(z.entry_variant.unique()):
            for method in sorted(z.sizing_method.unique()):
                for pc in sorted(z.position_cap.unique()):
                    g=z[(z.entry_variant==ev)&(z.sizing_method==method)&(z.position_cap==pc)].sort_values("year")
                    key=f"{ev}__{method}__{pc}"
                    comp=1.0;vals=[]
                    for r in g.itertuples():
                        comp*=1+float(r.total_return);vals.append(float(r.total_return))
                    summary["lanes"][f"top{cap}"][sleeve][key]={
                      "compounded_walk_forward_return":comp-1,
                      "positive_years":sum(v>0 for v in vals),
                      "years":len(vals),
                      "avg_year_return":statistics.mean(vals) if vals else None,
                      "avg_sharpe":float(g.sharpe.mean()) if len(g) else None,
                      "avg_exposure":float(g.avg_exposure.mean()) if len(g) else None,
                      "avg_profit_factor":float(g.profit_factor.mean()) if len(g) else None,
                      "avg_entry_hhi":float(g.avg_entry_hhi.mean()) if len(g) else None,
                      "avg_largest_new_equity_weight":float(g.avg_largest_new_equity_weight.mean()) if len(g) else None,
                      "avg_deployment_ratio":float(g.avg_deployment_ratio.mean()) if len(g) else None,
                      "avg_residual_budget_day_fraction":float(g.residual_budget_day_fraction.mean()) if len(g) else None,
                      "total_trades":int(g.trades.sum()) if len(g) else 0,
                      "yearly":{str(int(r.year)):float(r.total_return) for r in g.itertuples()},
                      "yearly_mdd":{str(int(r.year)):float(r.max_drawdown) for r in g.itertuples()},
                      "yearly_sharpe":{str(int(r.year)):float(r.sharpe) for r in g.itertuples()},
                    }

(out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
print(json.dumps(summary,indent=2))
