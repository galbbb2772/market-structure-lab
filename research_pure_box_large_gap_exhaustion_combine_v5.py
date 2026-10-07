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

ef=sorted(src.glob("**/gap_exhaustion_events_*.csv"))
pf=sorted(src.glob("**/gap_exhaustion_portfolios_*.csv"))
if len(ef)<6 or len(pf)<6:
    raise RuntimeError(f"expected 6+6 shards got {len(ef)} {len(pf)}")
e=pd.concat([pd.read_csv(f) for f in ef],ignore_index=True)
p=pd.concat([pd.read_csv(f) for f in pf],ignore_index=True)
e.to_csv(out/"annual_event_results.csv",index=False)
p.to_csv(out/"annual_portfolio_results.csv",index=False)

def wavg(g,col,w="n"):
    z=g[[col,w]].dropna()
    if z.empty:return None
    ww=z[w].astype(float)
    return float((z[col].astype(float)*ww).sum()/ww.sum()) if ww.sum()>0 else None

erows=[]
for (cap,target,method,feat,lane),g in e.groupby(
    ["rank_cap","target_fraction","gap_method","exhaustion_feature","lane"]
):
    gp=float(g.gross_positive_return_sum.sum())
    gl=float(g.gross_negative_return_abs_sum.sum())
    erows.append({
      "rank_cap":int(cap),"target_fraction":float(target),
      "gap_method":method,"exhaustion_feature":feat,"lane":lane,
      "years":int(g.year.nunique()),"n":int(g.n.sum()),
      "mean_trade":wavg(g,"mean_trade"),
      "profit_factor":gp/gl if gl>0 else None,
      "win_rate":wavg(g,"win_rate"),
      "target_share":wavg(g,"target_share"),
      "stop_share":wavg(g,"stop_share"),
      "mean_holding_sessions":wavg(g,"mean_holding_sessions"),
      "mean_mfe_return":wavg(g,"mean_mfe_return"),
      "mean_mae_return":wavg(g,"mean_mae_return"),
      "yearly_mean_trade":json.dumps({str(int(r.year)):float(r.mean_trade) for r in g.itertuples()},sort_keys=True),
      "yearly_pf":json.dumps({str(int(r.year)):None if pd.isna(r.profit_factor) else float(r.profit_factor) for r in g.itertuples()},sort_keys=True),
      "yearly_n":json.dumps({str(int(r.year)):int(r.n) for r in g.itertuples()},sort_keys=True),
    })
edf=pd.DataFrame(erows);edf.to_csv(out/"event_summary.csv",index=False)

prows=[]
for (cap,target,method,feat,lane),g in p.groupby(
    ["rank_cap","target_fraction","gap_method","exhaustion_feature","lane"]
):
    comp=1.0
    for r in g.sort_values("year").itertuples():
        comp*=1+float(r.total_return)
    prows.append({
      "rank_cap":int(cap),"target_fraction":float(target),
      "gap_method":method,"exhaustion_feature":feat,"lane":lane,
      "segments":len(g),"compounded_return":comp-1,
      "positive_years":int((g.total_return>0).sum()),
      "avg_sharpe":float(g.sharpe.mean()) if g.sharpe.notna().any() else None,
      "worst_mdd":float(g.max_drawdown.min()) if g.max_drawdown.notna().any() else None,
      "avg_exposure":float(g.avg_exposure.mean()),
      "total_trades":int(g.completed_trades.sum()),
      "yearly_return":json.dumps({str(int(r.year)):float(r.total_return) for r in g.itertuples()},sort_keys=True),
    })
pdf=pd.DataFrame(prows);pdf.to_csv(out/"portfolio_summary.csv",index=False)

def ev(cap,target,method,feat,lane):
    z=edf[(edf.rank_cap==cap)&(edf.target_fraction==target)&
          (edf.gap_method==method)&(edf.exhaustion_feature==feat)&(edf.lane==lane)]
    return None if z.empty else z.iloc[0]
def po(cap,target,method,feat,lane):
    z=pdf[(pdf.rank_cap==cap)&(pdf.target_fraction==target)&
          (pdf.gap_method==method)&(pdf.exhaustion_feature==feat)&(pdf.lane==lane)]
    return None if z.empty else z.iloc[0]
def ym(s):
    try:return json.loads(s)
    except:return {}

checks=[]
support={}
for feat in ("rebound_from_low_box","low_progress_box"):
    support[feat]={}
    for method in ("EXPANDING","FIXED_-1PCT"):
        arr=[]
        for cap in (300,500):
            for target in (.60,.80):
                strong=ev(cap,target,method,feat,"EXTREME_GAP__STRONG")
                weak=ev(cap,target,method,feat,"EXTREME_GAP__WEAK")
                ps=po(cap,target,method,feat,"EXTREME_GAP__STRONG")
                pw=po(cap,target,method,feat,"EXTREME_GAP__WEAK")
                if any(x is None for x in (strong,weak,ps,pw)):continue

                event_order=bool(float(strong.mean_trade)>float(weak.mean_trade) and
                                 float(strong.profit_factor)>float(weak.profit_factor))
                portfolio_order=bool(float(ps.compounded_return)>float(pw.compounded_return))
                ys=ym(strong.yearly_mean_trade); yw=ym(weak.yearly_mean_trade)
                yrs=sorted(set(ys)&set(yw))
                better=sum(float(ys[y])>float(yw[y]) for y in yrs)
                majority=bool(len(yrs)>=4 and better>len(yrs)/2)
                passed=event_order and portfolio_order and majority
                rec={
                  "feature":feat,"gap_method":method,"rank_cap":cap,"target_fraction":target,
                  "strong_n":int(strong.n),"weak_n":int(weak.n),
                  "strong_mean_trade":float(strong.mean_trade),"weak_mean_trade":float(weak.mean_trade),
                  "strong_pf":None if pd.isna(strong.profit_factor) else float(strong.profit_factor),
                  "weak_pf":None if pd.isna(weak.profit_factor) else float(weak.profit_factor),
                  "strong_portfolio_comp":float(ps.compounded_return),
                  "weak_portfolio_comp":float(pw.compounded_return),
                  "better_years":better,"overlap_years":yrs,
                  "event_order":event_order,"portfolio_order":portfolio_order,
                  "majority_years":majority,"passed":passed
                }
                checks.append(rec);arr.append(rec)
        support[feat][method]={
          "passed_checks":sum(x["passed"] for x in arr),
          "total_checks":len(arr),
          "all_checks_passed":bool(arr and all(x["passed"] for x in arr))
        }

cdf=pd.DataFrame(checks);cdf.to_csv(out/"support_checks.csv",index=False)
summary={"schema":"LARGE-GAP-EXHAUSTION-INTERACTION-V5","support":support,"checks":checks}
(out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
print(json.dumps({"schema":summary["schema"],"support":support},indent=2))
