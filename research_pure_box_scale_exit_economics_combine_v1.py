#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math, statistics
from pathlib import Path
import pandas as pd

ap=argparse.ArgumentParser()
ap.add_argument("--indir",required=True)
ap.add_argument("--outdir",required=True)
a=ap.parse_args()
src=Path(a.indir);out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

files=sorted(src.glob("**/scale_exit_economics_*.csv"))
if len(files)<8:
    raise RuntimeError(f"expected 8 yearly shards, got {len(files)}")
x=pd.concat([pd.read_csv(f) for f in files],ignore_index=True)
x["period"]=x.year.map(lambda y:"discovery" if int(y)<=2022 else "validation")
x.to_csv(out/"annual_results.csv",index=False)

def wavg(g,col,wcol="completed_trades"):
    z=g[[col,wcol]].dropna()
    if len(z)==0:return None
    w=z[wcol].astype(float)
    if float(w.sum())<=0:return None
    return float((z[col].astype(float)*w).sum()/w.sum())

summary={
  "schema":"SCALE-AWARE-EXIT-ECONOMICS-V1",
  "discovery":"2019-2022",
  "validation":"2023-2026Q1",
  "primary_panel":"common_eligible",
  "primary_horizon":20,
  "lanes":{}
}

for cap in (300,500):
    ck=f"top{cap}"
    summary["lanes"][ck]={}
    for scale in ("small","large"):
        summary["lanes"][ck][scale]={}
        for sample in ("common_eligible","target_specific"):
            summary["lanes"][ck][scale][sample]={}
            for h in (10,20,40):
                summary["lanes"][ck][scale][sample][f"h{h}"]={}
                for target in (.5,.6,.8,1.0):
                    key=f"t{int(target*100)}"
                    zz=x[(x.rank_cap==cap)&(x.scale==scale)&
                         (x.sample_panel==sample)&(x.max_hold==h)&
                         (x.target_fraction==target)]
                    lane={}
                    for period in ("discovery","validation"):
                        g=zz[zz.period==period].sort_values("year")
                        comp=1.0
                        for r in g.itertuples():
                            comp*=1+float(r.total_return)
                        posyears=int((g.total_return>0).sum())
                        gp=float(g.gross_positive_return_sum.sum())
                        gl=float(g.gross_negative_return_abs_sum.sum())
                        capdays=float(g.capital_days.sum())
                        sumrets=float(g.total_return.sum())
                        lane[period]={
                          "segments":int(len(g)),
                          "compounded_segment_return":comp-1,
                          "positive_segments":posyears,
                          "avg_segment_return":float(g.total_return.mean()) if len(g) else None,
                          "avg_sharpe":float(g.sharpe.mean()) if len(g) else None,
                          "worst_segment_mdd":float(g.max_drawdown.min()) if len(g) else None,
                          "avg_exposure":float(g.avg_exposure.mean()) if len(g) else None,
                          "avg_concurrent_positions":float(g.avg_concurrent_positions.mean()) if len(g) else None,
                          "entries":int(g.entries.sum()) if len(g) else 0,
                          "completed_trades":int(g.completed_trades.sum()) if len(g) else 0,
                          "aggregate_profit_factor":gp/gl if gl>0 else None,
                          "weighted_mean_trade":wavg(g,"mean_trade"),
                          "weighted_median_trade":wavg(g,"median_trade"),
                          "weighted_mean_holding_sessions":wavg(g,"mean_holding_sessions"),
                          "weighted_median_holding_sessions":wavg(g,"median_holding_sessions"),
                          "weighted_target_exit_share":wavg(g,"target_exit_share"),
                          "weighted_stop_exit_share":wavg(g,"stop_exit_share"),
                          "weighted_max_hold_exit_share":wavg(g,"max_hold_exit_share"),
                          "weighted_mean_mfe_return":wavg(g,"mean_mfe_return"),
                          "weighted_mean_mae_return":wavg(g,"mean_mae_return"),
                          "avg_turnover":float(g.turnover_alloc_over_mean_equity.mean()) if len(g) else None,
                          "capital_days":capdays,
                          "sum_segment_return_per_100_capital_days":sumrets/capdays*100 if capdays>0 else None,
                          "avg_return_over_avg_exposure":float(g.return_over_avg_exposure.mean()) if len(g) else None,
                          "yearly_return":{str(int(r.year)):float(r.total_return) for r in g.itertuples()},
                          "yearly_mdd":{str(int(r.year)):float(r.max_drawdown) for r in g.itertuples()},
                          "yearly_sharpe":{str(int(r.year)):None if pd.isna(r.sharpe) else float(r.sharpe) for r in g.itertuples()},
                        }
                    summary["lanes"][ck][scale][sample][f"h{h}"][key]=lane

# Compact primary validation comparison table.
primary=[]
for cap in (300,500):
    for scale in ("small","large"):
        for target in (.5,.6,.8,1.0):
            d=summary["lanes"][f"top{cap}"][scale]["common_eligible"]["h20"][f"t{int(target*100)}"]["validation"]
            primary.append({
              "rank_cap":cap,"scale":scale,"target_fraction":target,
              "compounded_segment_return":d["compounded_segment_return"],
              "positive_segments":d["positive_segments"],
              "avg_sharpe":d["avg_sharpe"],
              "worst_segment_mdd":d["worst_segment_mdd"],
              "avg_exposure":d["avg_exposure"],
              "aggregate_profit_factor":d["aggregate_profit_factor"],
              "weighted_mean_trade":d["weighted_mean_trade"],
              "weighted_mean_holding_sessions":d["weighted_mean_holding_sessions"],
              "weighted_target_exit_share":d["weighted_target_exit_share"],
              "weighted_stop_exit_share":d["weighted_stop_exit_share"],
              "weighted_max_hold_exit_share":d["weighted_max_hold_exit_share"],
              "capital_efficiency_per_100_days":d["sum_segment_return_per_100_capital_days"],
            })
pd.DataFrame(primary).to_csv(out/"primary_validation_comparison.csv",index=False)
summary["primary_validation_comparison"]=primary

(out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
print(json.dumps({"schema":summary["schema"],"primary_validation_comparison":primary},indent=2))
