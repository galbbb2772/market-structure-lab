#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd

ap=argparse.ArgumentParser()
ap.add_argument("--indir",required=True)
ap.add_argument("--outdir",required=True)
a=ap.parse_args()
src=Path(a.indir);out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

files=sorted(src.glob("**/resilience_portfolio_*.csv"))
if len(files)<8:
    raise RuntimeError(f"expected 8 shards, got {len(files)}")
x=pd.concat([pd.read_csv(f) for f in files],ignore_index=True)
x["period"]=x.year.map(lambda y:"discovery" if int(y)<=2022 else "validation")
x.to_csv(out/"annual_portfolio_stats.csv",index=False)

agg=[]
for (cap,target,alloc,lane,period),g in x.groupby(
    ["rank_cap","target_fraction","allocation","lane","period"]
):
    comp=1.0
    for r in g.sort_values("year").itertuples():
        comp*=1+float(r.total_return)
    agg.append({
      "rank_cap":int(cap),
      "target_fraction":float(target),
      "allocation":float(alloc),
      "lane":lane,
      "period":period,
      "segments":int(len(g)),
      "compounded_segment_return":comp-1,
      "positive_segments":int((g.total_return>0).sum()),
      "avg_segment_return":float(g.total_return.mean()),
      "avg_sharpe":float(g.sharpe.mean()) if g.sharpe.notna().any() else None,
      "worst_segment_mdd":float(g.max_drawdown.min()) if g.max_drawdown.notna().any() else None,
      "avg_exposure":float(g.avg_exposure.mean()),
      "total_trades":int(g.completed_trades.sum()),
      "avg_pf":float(g.profit_factor.mean()) if g.profit_factor.notna().any() else None,
      "avg_mean_trade":float(g.mean_trade.mean()) if g.mean_trade.notna().any() else None,
      "yearly_return":{str(int(r.year)):float(r.total_return) for r in g.itertuples()},
      "yearly_mdd":{str(int(r.year)):float(r.max_drawdown) for r in g.itertuples()},
    })
adf=pd.DataFrame(agg)
adf.to_csv(out/"portfolio_summary.csv",index=False)

# Direct resilient-vs-underperform contrast and baseline comparison.
contr=[]
for (cap,target,alloc,period),g in adf.groupby(
    ["rank_cap","target_fraction","allocation","period"]
):
    d={r.lane:r for r in g.itertuples(index=False)}
    if "RESILIENT_ONLY" in d and "UNDERPERFORM_ONLY" in d:
        a1=d["RESILIENT_ONLY"];b=d["UNDERPERFORM_ONLY"]
        base=d.get("OBSERVABLE_BASELINE")
        contr.append({
          "rank_cap":int(cap),"target_fraction":float(target),"allocation":float(alloc),"period":period,
          "resilient_return":float(a1.compounded_segment_return),
          "underperform_return":float(b.compounded_segment_return),
          "resilience_minus_underperform":float(a1.compounded_segment_return-b.compounded_segment_return),
          "resilient_worst_mdd":float(a1.worst_segment_mdd),
          "underperform_worst_mdd":float(b.worst_segment_mdd),
          "resilient_avg_exposure":float(a1.avg_exposure),
          "underperform_avg_exposure":float(b.avg_exposure),
          "resilient_avg_pf":None if pd.isna(a1.avg_pf) else float(a1.avg_pf),
          "underperform_avg_pf":None if pd.isna(b.avg_pf) else float(b.avg_pf),
          "baseline_return":None if base is None else float(base.compounded_segment_return),
          "resilient_minus_baseline":None if base is None else float(a1.compounded_segment_return-base.compounded_segment_return),
          "resilient_positive_segments":int(a1.positive_segments),
          "underperform_positive_segments":int(b.positive_segments),
          "baseline_positive_segments":None if base is None else int(base.positive_segments),
        })
cdf=pd.DataFrame(contr)
cdf.to_csv(out/"contrast_summary.csv",index=False)

summary={"schema":"LARGE-RESILIENCE-PORTFOLIO-V4","contrasts":{}}
for cap in (300,500):
    ck=f"top{cap}";summary["contrasts"][ck]={}
    for target in (.60,.80):
        tk=f"t{int(target*100)}";summary["contrasts"][ck][tk]={}
        for alloc in (.05,.10,.20):
            ak=f"a{int(alloc*100)}"
            summary["contrasts"][ck][tk][ak]={}
            for period in ("discovery","validation"):
                z=cdf[
                  (cdf.rank_cap==cap)&
                  (cdf.target_fraction==target)&
                  (cdf.allocation==alloc)&
                  (cdf.period==period)
                ]
                if len(z):
                    rr=z.iloc[0]
                    summary["contrasts"][ck][tk][ak][period]={
                      k:(None if pd.isna(rr[k]) else (int(rr[k]) if k.endswith("segments") else float(rr[k])))
                      for k in [
                        "resilient_return","underperform_return","resilience_minus_underperform",
                        "resilient_worst_mdd","underperform_worst_mdd",
                        "resilient_avg_exposure","underperform_avg_exposure",
                        "resilient_avg_pf","underperform_avg_pf",
                        "baseline_return","resilient_minus_baseline",
                        "resilient_positive_segments","underperform_positive_segments","baseline_positive_segments"
                      ]
                    }

(out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
print(json.dumps(summary,indent=2))
