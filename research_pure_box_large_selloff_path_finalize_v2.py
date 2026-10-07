#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd
FEATURES=["signal_clv","signal_lower_wick","signal_body_recovery","deceleration_1v3","deceleration_2v5","down_day_count_5","signal_volume_ratio20"]
DIRECTIONAL=set(["signal_clv","signal_lower_wick","signal_body_recovery","deceleration_1v3","deceleration_2v5"])
ap=argparse.ArgumentParser();ap.add_argument("--mechanism-dir",required=True);ap.add_argument("--portfolio-dir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
m=Path(a.mechanism_dir);p=Path(a.portfolio_dir);out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
q=pd.read_csv(m/"event_quintiles.csv");c=pd.read_csv(m/"continuous_summary.csv");pf=sorted(p.glob("**/selloff_path_portfolio_*.csv"))
if len(pf)<8:raise RuntimeError(f"expected8 got{len(pf)}")
x=pd.concat([pd.read_csv(f) for f in pf],ignore_index=True);x["period"]=x.year.map(lambda y:"discovery" if int(y)<=2022 else "validation");x.to_csv(out/"annual_portfolio_results.csv",index=False)
prows=[]
for (cap,target,feat,lane,period),g in x.groupby(["rank_cap","target_fraction","feature","lane","period"]):
 comp=1.
 for r in g.sort_values("year").itertuples():comp*=1+float(r.total_return)
 prows.append({"rank_cap":int(cap),"target_fraction":float(target),"feature":feat,"lane":lane,"period":period,"segments":len(g),"compounded_segment_return":comp-1,"positive_segments":int((g.total_return>0).sum()),"avg_sharpe":float(g.sharpe.mean()) if g.sharpe.notna().any() else None,"worst_segment_mdd":float(g.max_drawdown.min()) if g.max_drawdown.notna().any() else None,"avg_exposure":float(g.avg_exposure.mean()),"total_trades":int(g.completed_trades.sum()),"yearly_return":json.dumps({str(int(r.year)):float(r.total_return) for r in g.itertuples()},sort_keys=True)})
pdf=pd.DataFrame(prows);pdf.to_csv(out/"portfolio_summary.csv",index=False)
checks=[];support={}
for feat in FEATURES:
 arr=[]
 for cap in (300,500):
  for target in (.6,.8):
   for period in ("discovery","validation"):
    qq=q[(q.rank_cap==cap)&(q.target_fraction==target)&(q.feature==feat)&(q.period==period)];q1=qq[qq.quintile==1];q5=qq[qq.quintile==5]
    cc=c[(c.rank_cap==cap)&(c.target_fraction==target)&(c.feature==feat)&(c.period==period)]
    p1=pdf[(pdf.rank_cap==cap)&(pdf.target_fraction==target)&(pdf.feature==feat)&(pdf.lane=="Q1")&(pdf.period==period)]
    p5=pdf[(pdf.rank_cap==cap)&(pdf.target_fraction==target)&(pdf.feature==feat)&(pdf.lane=="Q5")&(pdf.period==period)]
    if q1.empty or q5.empty or cc.empty or p1.empty or p5.empty:continue
    a1=q1.iloc[0];a5=q5.iloc[0];cr=cc.iloc[0];r1=p1.iloc[0];r5=p5.iloc[0]
    event=bool(float(a5.mean_trade)>float(a1.mean_trade) and float(a5.profit_factor)>float(a1.profit_factor));corr=bool(pd.notna(cr.rho_return) and float(cr.rho_return)>0);port=bool(float(r5.compounded_segment_return)>float(r1.compounded_segment_return))
    y1=json.loads(a1.yearly_mean_trade);y5=json.loads(a5.yearly_mean_trade);yrs=sorted(set(y1)&set(y5));better=sum(float(y5[y])>float(y1[y]) for y in yrs);notone=bool(len(yrs)>=2 and better>=2)
    passed=bool(feat in DIRECTIONAL and event and corr and port and notone)
    rec={"feature":feat,"directional_test":feat in DIRECTIONAL,"rank_cap":cap,"target_fraction":target,"period":period,"q1_n":int(a1.n),"q5_n":int(a5.n),"q1_mean_trade":float(a1.mean_trade),"q5_mean_trade":float(a5.mean_trade),"q1_pf":None if pd.isna(a1.profit_factor) else float(a1.profit_factor),"q5_pf":None if pd.isna(a5.profit_factor) else float(a5.profit_factor),"rho_return":None if pd.isna(cr.rho_return) else float(cr.rho_return),"q1_portfolio_comp":float(r1.compounded_segment_return),"q5_portfolio_comp":float(r5.compounded_segment_return),"q5_better_years":better,"overlap_years":yrs,"event_order":event,"correlation_direction":corr,"portfolio_order":port,"not_one_year":notone,"passed":passed};checks.append(rec);arr.append(rec)
 support[feat]={"directional_test":feat in DIRECTIONAL,"passed_checks":sum(z["passed"] for z in arr),"total_checks":len(arr),"all_checks_passed":bool(feat in DIRECTIONAL and arr and all(z["passed"] for z in arr))}
pd.DataFrame(checks).to_csv(out/"support_checks.csv",index=False);summary={"schema":"LARGE-SELLOFF-PATH-V2","support":support,"checks":checks};(out/"summary.json").write_text(json.dumps(summary,indent=2));print(json.dumps({"schema":summary["schema"],"support":support},indent=2))
