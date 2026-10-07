#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd

ap=argparse.ArgumentParser()
ap.add_argument("--mechanism-dir",required=True)
ap.add_argument("--portfolio-dir",required=True)
ap.add_argument("--outdir",required=True)
a=ap.parse_args()
m=Path(a.mechanism_dir);p=Path(a.portfolio_dir);out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

mech=json.load(open(m/"mechanism_summary.json"))
e=pd.read_csv(m/"event_corner_summary.csv")
pf=sorted(p.glob("**/relative_resilience_portfolio_*.csv"))
if len(pf)<8: raise RuntimeError(f"expected 8 portfolio shards, got {len(pf)}")
x=pd.concat([pd.read_csv(f) for f in pf],ignore_index=True)
x["period"]=x.year.map(lambda y:"discovery" if int(y)<=2022 else "validation")
x.to_csv(out/"annual_portfolio_results.csv",index=False)

prows=[]
for (cap,target,grid,corner,period),g in x.groupby(
 ["rank_cap","target_fraction","grid","corner","period"]
):
    comp=1.0
    for r in g.sort_values("year").itertuples():
        comp*=1+float(r.total_return)
    prows.append({
      "rank_cap":int(cap),"target_fraction":float(target),"grid":grid,"corner":corner,
      "period":period,"segments":int(len(g)),
      "compounded_segment_return":comp-1,
      "positive_segments":int((g.total_return>0).sum()),
      "avg_sharpe":float(g.sharpe.mean()) if g.sharpe.notna().any() else None,
      "worst_segment_mdd":float(g.max_drawdown.min()) if g.max_drawdown.notna().any() else None,
      "avg_exposure":float(g.avg_exposure.mean()) if len(g) else None,
      "total_trades":int(g.completed_trades.sum()) if len(g) else 0,
      "yearly_return":json.dumps({str(int(r.year)):float(r.total_return) for r in g.itertuples()},sort_keys=True),
    })
pdf=pd.DataFrame(prows)
pdf.to_csv(out/"portfolio_summary.csv",index=False)

def get_event(grid,cap,target,period,corner):
    z=e[(e.grid==grid)&(e.rank_cap==cap)&(e.target_fraction==target)&
        (e.period==period)&(e.corner==corner)]
    return None if z.empty else z.iloc[0]
def get_port(grid,cap,target,period,corner):
    z=pdf[(pdf.grid==grid)&(pdf.rank_cap==cap)&(pdf.target_fraction==target)&
          (pdf.period==period)&(pdf.corner==corner)]
    return None if z.empty else z.iloc[0]

def year_map(s):
    try:return json.loads(s)
    except:return {}

checks=[]
for grid in ("A","B"):
    if grid=="A":
        primary="STOCK_STRONG_MARKET_WEAK"
        weak_same="STOCK_WEAK_MARKET_WEAK"
        strong_other="STOCK_STRONG_MARKET_STRONG"
    else:
        primary="STOCK_STRONG_MARKET_STRESSED"
        weak_same="STOCK_WEAK_MARKET_STRESSED"
        strong_other="STOCK_STRONG_MARKET_CALM"

    for cap in (300,500):
        for target in (.60,.80):
            for period in ("discovery","validation"):
                ep=get_event(grid,cap,target,period,primary)
                ew=get_event(grid,cap,target,period,weak_same)
                eo=get_event(grid,cap,target,period,strong_other)
                pp=get_port(grid,cap,target,period,primary)
                pw=get_port(grid,cap,target,period,weak_same)
                po=get_port(grid,cap,target,period,strong_other)
                if any(v is None for v in (ep,ew,eo,pp,pw,po)):continue

                event_same=bool(float(ep.mean_trade)>float(ew.mean_trade) and
                                float(ep.profit_factor)>float(ew.profit_factor))
                event_not_inferior=bool(float(ep.mean_trade)>=float(eo.mean_trade))
                portfolio_same=bool(float(pp.compounded_segment_return)>float(pw.compounded_segment_return))
                portfolio_not_inferior=bool(float(pp.compounded_segment_return)>=float(po.compounded_segment_return))

                py=year_map(ep.yearly_mean_trade); wy=year_map(ew.yearly_mean_trade)
                overlap=sorted(set(py)&set(wy))
                better_years=sum(float(py[y])>float(wy[y]) for y in overlap)
                not_one_year=bool(len(overlap)>=2 and better_years>=2)

                passed=event_same and event_not_inferior and portfolio_same and portfolio_not_inferior and not_one_year
                checks.append({
                  "grid":grid,"rank_cap":cap,"target_fraction":target,"period":period,
                  "primary":primary,"weak_same_market":weak_same,"strong_other_market":strong_other,
                  "primary_n":int(ep.n),"weak_n":int(ew.n),"strong_other_n":int(eo.n),
                  "primary_mean_trade":float(ep.mean_trade),"weak_mean_trade":float(ew.mean_trade),
                  "strong_other_mean_trade":float(eo.mean_trade),
                  "primary_pf":None if pd.isna(ep.profit_factor) else float(ep.profit_factor),
                  "weak_pf":None if pd.isna(ew.profit_factor) else float(ew.profit_factor),
                  "primary_portfolio_comp":float(pp.compounded_segment_return),
                  "weak_portfolio_comp":float(pw.compounded_segment_return),
                  "strong_other_portfolio_comp":float(po.compounded_segment_return),
                  "overlap_years":overlap,"primary_better_years":better_years,
                  "event_same_market_superiority":event_same,
                  "event_not_inferior_to_strong_other_market":event_not_inferior,
                  "portfolio_same_market_superiority":portfolio_same,
                  "portfolio_not_inferior_to_strong_other_market":portfolio_not_inferior,
                  "not_one_year":not_one_year,
                  "passed":passed,
                })

cdf=pd.DataFrame(checks)
cdf.to_csv(out/"support_checks.csv",index=False)

summary={
 "schema":"LARGE-RELATIVE-RESILIENCE-V4",
 "mechanism":mech,
 "support":{},
 "checks":checks
}
for grid in ("A","B"):
    g=[r for r in checks if r["grid"]==grid]
    summary["support"][grid]={
      "passed_checks":sum(r["passed"] for r in g),
      "total_checks":len(g),
      "all_checks_passed":bool(g and all(r["passed"] for r in g))
    }

(out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
print(json.dumps({"schema":summary["schema"],"support":summary["support"]},indent=2))
