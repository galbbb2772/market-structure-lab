#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd

FEATURES=[
 "pct_up_1d",
 "new_low_relief_1d",
 "new_low_relief_3d",
 "ma50_recovery_3d",
 "ret20_recovery_3d",
 "median_ret20_recovery_3d",
]

ap=argparse.ArgumentParser()
ap.add_argument("--mechanism_dir",required=True)
ap.add_argument("--portfolio_dir",required=True)
ap.add_argument("--outdir",required=True)
a=ap.parse_args()
m=Path(a.mechanism_dir);p=Path(a.portfolio_dir);out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

mech=json.load(open(m/"mechanism_summary.json"))
q=pd.read_csv(m/"event_quintiles.csv")
c=pd.read_csv(m/"continuous_summary.csv")
pf=sorted(p.glob("**/market_exhaustion_portfolio_*.csv"))
if len(pf)<8: raise RuntimeError(f"expected 8 portfolio shards, got {len(pf)}")
x=pd.concat([pd.read_csv(f) for f in pf],ignore_index=True)
x["period"]=x.year.map(lambda y:"discovery" if int(y)<=2022 else "validation")
x.to_csv(out/"annual_portfolio_results.csv",index=False)

prows=[]
for (cap,target,feat,lane,period),g in x.groupby(
    ["rank_cap","target_fraction","feature","quintile_lane","period"]
):
    comp=1.0
    for r in g.sort_values("year").itertuples():
        comp*=1+float(r.total_return)
    prows.append({
      "rank_cap":int(cap),"target_fraction":float(target),"feature":feat,
      "quintile_lane":lane,"period":period,
      "segments":int(len(g)),
      "compounded_segment_return":comp-1,
      "positive_segments":int((g.total_return>0).sum()),
      "avg_segment_return":float(g.total_return.mean()),
      "avg_sharpe":float(g.sharpe.mean()) if g.sharpe.notna().any() else None,
      "worst_segment_mdd":float(g.max_drawdown.min()) if g.max_drawdown.notna().any() else None,
      "avg_exposure":float(g.avg_exposure.mean()),
      "total_trades":int(g.completed_trades.sum()),
      "avg_pf":float(g.profit_factor.mean()) if g.profit_factor.notna().any() else None,
      "yearly_return":json.dumps({str(int(r.year)):float(r.total_return) for r in g.itertuples()},sort_keys=True),
    })
pdf=pd.DataFrame(prows)
pdf.to_csv(out/"portfolio_summary.csv",index=False)

summary={
 "schema":"LARGE-MARKET-EXHAUSTION-V3",
 "mechanism":mech,
 "feature_support":{},
 "portfolio_baseline":{}
}

for cap in (300,500):
    summary["portfolio_baseline"][f"top{cap}"]={}
    for target in (.60,.80):
        tk=f"t{int(target*100)}"
        summary["portfolio_baseline"][f"top{cap}"][tk]={}
        for period in ("discovery","validation"):
            z=pdf[(pdf.rank_cap==cap)&(pdf.target_fraction==target)&
                  (pdf.feature=="ALL")&(pdf.quintile_lane=="ALL")&(pdf.period==period)]
            if len(z):
                r=z.iloc[0]
                summary["portfolio_baseline"][f"top{cap}"][tk][period]={
                  "compounded_segment_return":float(r.compounded_segment_return),
                  "positive_segments":int(r.positive_segments),
                  "avg_sharpe":None if pd.isna(r.avg_sharpe) else float(r.avg_sharpe),
                  "worst_segment_mdd":float(r.worst_segment_mdd),
                  "avg_exposure":float(r.avg_exposure),
                  "total_trades":int(r.total_trades),
                  "yearly_return":json.loads(r.yearly_return),
                }

for feat in FEATURES:
    item={"checks":[]}
    pass_count=0;total=0
    for cap in (300,500):
        for target in (.60,.80):
            for period in ("discovery","validation"):
                qq=q[(q.rank_cap==cap)&(q.target_fraction==target)&(q.feature==feat)&(q.period==period)]
                q1=qq[qq.quintile==1];q5=qq[qq.quintile==5]
                cc=c[(c.rank_cap==cap)&(c.target_fraction==target)&(c.feature==feat)&(c.period==period)]
                pp=pdf[(pdf.rank_cap==cap)&(pdf.target_fraction==target)&(pdf.feature==feat)&(pdf.period==period)]
                p1=pp[pp.quintile_lane=="Q1"];p5=pp[pp.quintile_lane=="Q5"]
                if q1.empty or q5.empty or cc.empty or p1.empty or p5.empty:continue
                total+=1
                r1=q1.iloc[0];r5=q5.iloc[0];cr=cc.iloc[0];pr1=p1.iloc[0];pr5=p5.iloc[0]
                event_order=bool(float(r5.mean_trade)>float(r1.mean_trade) and float(r5.profit_factor)>float(r1.profit_factor))
                corr_dir=bool(pd.notna(cr.rho_return) and float(cr.rho_return)>0 and
                              pd.notna(cr.rho_target) and float(cr.rho_target)>0 and
                              pd.notna(cr.rho_stop) and float(cr.rho_stop)<0)
                portfolio_order=bool(float(pr5.compounded_segment_return)>float(pr1.compounded_segment_return))
                passed=event_order and corr_dir and portfolio_order
                if passed:pass_count+=1
                item["checks"].append({
                  "rank_cap":cap,"target_fraction":target,"period":period,
                  "q1_mean_trade":float(r1.mean_trade),"q5_mean_trade":float(r5.mean_trade),
                  "q1_pf":None if pd.isna(r1.profit_factor) else float(r1.profit_factor),
                  "q5_pf":None if pd.isna(r5.profit_factor) else float(r5.profit_factor),
                  "rho_return":None if pd.isna(cr.rho_return) else float(cr.rho_return),
                  "rho_target":None if pd.isna(cr.rho_target) else float(cr.rho_target),
                  "rho_stop":None if pd.isna(cr.rho_stop) else float(cr.rho_stop),
                  "q1_portfolio_comp":float(pr1.compounded_segment_return),
                  "q5_portfolio_comp":float(pr5.compounded_segment_return),
                  "event_order":event_order,"correlation_direction":corr_dir,
                  "portfolio_order":portfolio_order,"passed":passed,
                })
    item["passed_checks"]=pass_count
    item["total_checks"]=total
    item["all_checks_passed"]=bool(total>0 and pass_count==total)
    summary["feature_support"][feat]=item

(out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
print(json.dumps({
  "schema":summary["schema"],
  "support":{k:{"passed":v["passed_checks"],"total":v["total_checks"],"all":v["all_checks_passed"]}
             for k,v in summary["feature_support"].items()}
},indent=2))
