#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd

FEATURES=["gap_component","intraday_component","close_recovery_from_low","downside_wick_fraction","volume_ratio20","gap_share_of_negative_move"]
GRADED={
 "gap_component":"direct",
 "close_recovery_from_low":"direct",
 "downside_wick_fraction":"direct",
 "gap_share_of_negative_move":"inverse",
}
ap=argparse.ArgumentParser();ap.add_argument("--mechanism-dir",required=True);ap.add_argument("--portfolio-dir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
m=Path(a.mechanism_dir);p=Path(a.portfolio_dir);out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
q=pd.read_csv(m/"event_quintiles.csv");c=pd.read_csv(m/"continuous_summary.csv")
pf=sorted(p.glob("**/selloff_anatomy_portfolio_*.csv"))
if len(pf)<8:raise RuntimeError(f"expected 8 portfolio shards got {len(pf)}")
x=pd.concat([pd.read_csv(f) for f in pf],ignore_index=True);x["period"]=x.year.map(lambda y:"discovery" if int(y)<=2022 else "validation")
x.to_csv(out/"annual_portfolio_results.csv",index=False)

prows=[]
for (cap,target,feat,lane,period),g in x.groupby(["rank_cap","target_fraction","feature","lane","period"]):
  comp=1.0
  for r in g.sort_values("year").itertuples():comp*=1+float(r.total_return)
  prows.append({"rank_cap":int(cap),"target_fraction":float(target),"feature":feat,"lane":lane,"period":period,"segments":len(g),"compounded_segment_return":comp-1,"positive_segments":int((g.total_return>0).sum()),"avg_sharpe":float(g.sharpe.mean()) if g.sharpe.notna().any() else None,"worst_segment_mdd":float(g.max_drawdown.min()) if g.max_drawdown.notna().any() else None,"avg_exposure":float(g.avg_exposure.mean()),"total_trades":int(g.completed_trades.sum()),"yearly_return":json.dumps({str(int(r.year)):float(r.total_return) for r in g.itertuples()},sort_keys=True)})
pdf=pd.DataFrame(prows);pdf.to_csv(out/"portfolio_summary.csv",index=False)

checks=[];support={}
for feat,direction in GRADED.items():
  arr=[]
  for cap in (300,500):
    for target in (.6,.8):
      for period in ("discovery","validation"):
        qq=q[(q.rank_cap==cap)&(q.target_fraction==target)&(q.feature==feat)&(q.period==period)]
        q1=qq[qq.quintile==1];q5=qq[qq.quintile==5]
        cc=c[(c.rank_cap==cap)&(c.target_fraction==target)&(c.feature==feat)&(c.period==period)]
        p1=pdf[(pdf.rank_cap==cap)&(pdf.target_fraction==target)&(pdf.feature==feat)&(pdf.lane=="Q1")&(pdf.period==period)]
        p5=pdf[(pdf.rank_cap==cap)&(pdf.target_fraction==target)&(pdf.feature==feat)&(pdf.lane=="Q5")&(pdf.period==period)]
        if q1.empty or q5.empty or cc.empty or p1.empty or p5.empty:continue
        a1=q1.iloc[0];a5=q5.iloc[0];cr=cc.iloc[0];r1=p1.iloc[0];r5=p5.iloc[0]
        if direction=="direct":
          event=bool(float(a5.mean_trade)>float(a1.mean_trade) and float(a5.profit_factor)>float(a1.profit_factor))
          corr=bool(pd.notna(cr.rho_return) and float(cr.rho_return)>0)
          port=bool(float(r5.compounded_segment_return)>float(r1.compounded_segment_return))
          ybad=json.loads(a1.yearly_mean_trade);ygood=json.loads(a5.yearly_mean_trade)
        else:
          event=bool(float(a1.mean_trade)>float(a5.mean_trade) and float(a1.profit_factor)>float(a5.profit_factor))
          corr=bool(pd.notna(cr.rho_return) and float(cr.rho_return)<0)
          port=bool(float(r1.compounded_segment_return)>float(r5.compounded_segment_return))
          ybad=json.loads(a5.yearly_mean_trade);ygood=json.loads(a1.yearly_mean_trade)
        yrs=sorted(set(ybad)&set(ygood));better=sum(float(ygood[y])>float(ybad[y]) for y in yrs)
        not_one=bool(len(yrs)>=2 and better>=2)
        passed=event and corr and port and not_one
        rec={"feature":feat,"direction":direction,"rank_cap":cap,"target_fraction":target,"period":period,
             "q1_n":int(a1.n),"q5_n":int(a5.n),"q1_mean_trade":float(a1.mean_trade),"q5_mean_trade":float(a5.mean_trade),
             "q1_pf":None if pd.isna(a1.profit_factor) else float(a1.profit_factor),"q5_pf":None if pd.isna(a5.profit_factor) else float(a5.profit_factor),
             "rho_return":None if pd.isna(cr.rho_return) else float(cr.rho_return),
             "q1_portfolio_comp":float(r1.compounded_segment_return),"q5_portfolio_comp":float(r5.compounded_segment_return),
             "better_years":better,"overlap_years":yrs,"event_order":event,"correlation_direction":corr,
             "portfolio_order":port,"not_one_year":not_one,"passed":passed}
        checks.append(rec);arr.append(rec)
  support[feat]={"passed_checks":sum(z["passed"] for z in arr),"total_checks":len(arr),"all_checks_passed":bool(arr and all(z["passed"] for z in arr))}
pd.DataFrame(checks).to_csv(out/"support_checks.csv",index=False)
summary={"schema":"LARGE-SELLOFF-ANATOMY-V2","support":support,"checks":checks}
(out/"summary.json").write_text(json.dumps(summary,indent=2))
print(json.dumps({"schema":summary["schema"],"support":support},indent=2))
