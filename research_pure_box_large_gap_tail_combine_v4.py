#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd

ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
src=Path(a.indir);out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
files=sorted(src.glob("**/gap_tail_*.csv"))
if len(files)<6: raise RuntimeError(f"expected 6 yearly shards got {len(files)}")
x=pd.concat([pd.read_csv(f) for f in files],ignore_index=True).sort_values(["rank_cap","target_fraction","year","method","lane"])
x.to_csv(out/"annual_results.csv",index=False)

rows=[]
for (cap,target,method,lane),g in x.groupby(["rank_cap","target_fraction","method","lane"]):
    comp=1.0
    for r in g.sort_values("year").itertuples():
        comp*=1+float(r.total_return)
    rows.append({
      "rank_cap":int(cap),"target_fraction":float(target),"method":method,"lane":lane,
      "segments":len(g),"compounded_return":comp-1,
      "positive_years":int((g.total_return>0).sum()),
      "avg_year_return":float(g.total_return.mean()),
      "avg_sharpe":float(g.sharpe.mean()) if g.sharpe.notna().any() else None,
      "worst_mdd":float(g.max_drawdown.min()) if g.max_drawdown.notna().any() else None,
      "avg_exposure":float(g.avg_exposure.mean()),
      "total_trades":int(g.completed_trades.sum()),
      "avg_pf":float(g.profit_factor.mean()) if g.profit_factor.notna().any() else None,
      "weighted_mean_trade":float((g.mean_trade*g.completed_trades).sum()/g.completed_trades.sum()) if g.completed_trades.sum()>0 else None,
      "yearly_return":json.dumps({str(int(r.year)):float(r.total_return) for r in g.itertuples()},sort_keys=True),
      "yearly_pf":json.dumps({str(int(r.year)):None if pd.isna(r.profit_factor) else float(r.profit_factor) for r in g.itertuples()},sort_keys=True),
      "yearly_threshold":json.dumps({str(int(r.year)):None if pd.isna(r.expanding_q20) else float(r.expanding_q20) for r in g.itertuples()},sort_keys=True),
    })
s=pd.DataFrame(rows)
s.to_csv(out/"summary_table.csv",index=False)

checks=[]
for cap in (300,500):
  for target in (.6,.8):
    b=s[(s.rank_cap==cap)&(s.target_fraction==target)&(s.method=="BASELINE")&(s.lane=="ALL")].iloc[0]
    for method in ("EXPANDING","FIXED_-1PCT"):
      non=s[(s.rank_cap==cap)&(s.target_fraction==target)&(s.method==method)&(s.lane=="NON_EXTREME")].iloc[0]
      tail=s[(s.rank_cap==cap)&(s.target_fraction==target)&(s.method==method)&(s.lane=="EXTREME_TAIL")].iloc[0]
      non_vs_tail=bool(float(non.weighted_mean_trade)>float(tail.weighted_mean_trade) and float(non.avg_pf)>float(tail.avg_pf))
      risk_better=bool(float(non.worst_mdd)>=float(b.worst_mdd))
      return_not_destroyed=bool(float(non.compounded_return)>=0.75*float(b.compounded_return)) if float(b.compounded_return)>0 else bool(float(non.compounded_return)>float(b.compounded_return))
      sharpe_better=bool(pd.notna(non.avg_sharpe) and pd.notna(b.avg_sharpe) and float(non.avg_sharpe)>=float(b.avg_sharpe))
      passed=non_vs_tail and risk_better and (return_not_destroyed or sharpe_better)
      checks.append({
        "rank_cap":cap,"target_fraction":target,"method":method,
        "baseline_compounded_return":float(b.compounded_return),
        "non_extreme_compounded_return":float(non.compounded_return),
        "tail_compounded_return":float(tail.compounded_return),
        "baseline_avg_sharpe":None if pd.isna(b.avg_sharpe) else float(b.avg_sharpe),
        "non_extreme_avg_sharpe":None if pd.isna(non.avg_sharpe) else float(non.avg_sharpe),
        "baseline_worst_mdd":float(b.worst_mdd),"non_extreme_worst_mdd":float(non.worst_mdd),
        "non_extreme_mean_trade":float(non.weighted_mean_trade),"tail_mean_trade":float(tail.weighted_mean_trade),
        "non_extreme_avg_pf":float(non.avg_pf),"tail_avg_pf":float(tail.avg_pf),
        "non_vs_tail_trade_economics":non_vs_tail,
        "risk_better":risk_better,"return_not_destroyed":return_not_destroyed,
        "sharpe_better":sharpe_better,"passed":passed
      })
cdf=pd.DataFrame(checks);cdf.to_csv(out/"support_checks.csv",index=False)
summary={"schema":"LARGE-GAP-TAIL-EXCLUSION-V4",
         "expanding_passed":int(cdf[cdf.method=="EXPANDING"].passed.sum()),
         "expanding_total":int((cdf.method=="EXPANDING").sum()),
         "fixed_passed":int(cdf[cdf.method=="FIXED_-1PCT"].passed.sum()),
         "fixed_total":int((cdf.method=="FIXED_-1PCT").sum()),
         "checks":checks}
(out/"summary.json").write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
