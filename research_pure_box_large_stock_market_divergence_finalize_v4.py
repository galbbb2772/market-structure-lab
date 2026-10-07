#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd

PRIMARY="STRONG_STOCK|WEAK_MARKET_DAY"
COMP1="WEAK_STOCK|WEAK_MARKET_DAY"
COMP2="STRONG_STOCK|STRONG_MARKET_DAY"
FEATURES=["rebound_from_low_box","low_progress_box"]

ap=argparse.ArgumentParser()
ap.add_argument("--mechanism_dir",required=True)
ap.add_argument("--portfolio_dir",required=True)
ap.add_argument("--outdir",required=True)
a=ap.parse_args()
m=Path(a.mechanism_dir);p=Path(a.portfolio_dir);out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

mech=json.load(open(m/"mechanism_summary.json"))
edf=pd.read_csv(m/"event_cells.csv")
pfiles=sorted(p.glob("**/stock_market_divergence_portfolio_*.csv"))
if len(pfiles)<8:raise RuntimeError(f"expected 8 portfolio shards, got {len(pfiles)}")
x=pd.concat([pd.read_csv(f) for f in pfiles],ignore_index=True)
x["period"]=x.year.map(lambda y:"discovery" if int(y)<=2022 else "validation")
x.to_csv(out/"annual_portfolio_results.csv",index=False)

prows=[]
for (cap,target,feat,cell,period),g in x.groupby(
    ["rank_cap","target_fraction","feature","cell","period"]
):
    comp=1.
    for r in g.sort_values("year").itertuples():comp*=1+float(r.total_return)
    prows.append({
      "rank_cap":int(cap),"target_fraction":float(target),"feature":feat,"cell":cell,
      "period":period,"segments":int(len(g)),
      "compounded_segment_return":comp-1,
      "positive_segments":int((g.total_return>0).sum()),
      "avg_sharpe":float(g.sharpe.mean()) if g.sharpe.notna().any() else None,
      "worst_segment_mdd":float(g.max_drawdown.min()) if g.max_drawdown.notna().any() else None,
      "avg_exposure":float(g.avg_exposure.mean()),
      "total_trades":int(g.completed_trades.sum()),
      "avg_pf":float(g.profit_factor.mean()) if g.profit_factor.notna().any() else None,
      "yearly_return":json.dumps({str(int(r.year)):float(r.total_return) for r in g.itertuples()},sort_keys=True),
    })
pdf=pd.DataFrame(prows)
pdf.to_csv(out/"portfolio_summary.csv",index=False)

summary={"schema":"LARGE-STOCK-MARKET-DIVERGENCE-V4",
         "mechanism":mech,"support":{}}

for feat in FEATURES:
    checks=[];passed=0;total=0
    for cap in (300,500):
      for target in (.60,.80):
        for period in ("discovery","validation"):
          e=edf[(edf.rank_cap==cap)&(edf.target_fraction==target)&
                (edf.feature==feat)&(edf.period==period)]
          pz=pdf[(pdf.rank_cap==cap)&(pdf.target_fraction==target)&
                 (pdf.feature==feat)&(pdf.period==period)]
          ep=e[e.cell==PRIMARY];e1=e[e.cell==COMP1];e2=e[e.cell==COMP2]
          pp=pz[pz.cell==PRIMARY];p1=pz[pz.cell==COMP1];p2=pz[pz.cell==COMP2]
          if any(z.empty for z in (ep,e1,e2,pp,p1,p2)):continue
          total+=1
          ep=ep.iloc[0];e1=e1.iloc[0];e2=e2.iloc[0];pp=pp.iloc[0];p1=p1.iloc[0];p2=p2.iloc[0]
          event_vs_weak=bool(float(ep.mean_trade)>float(e1.mean_trade) and
                             float(ep.profit_factor)>float(e1.profit_factor))
          event_vs_market=bool(float(ep.mean_trade)>float(e2.mean_trade) and
                               float(ep.profit_factor)>float(e2.profit_factor))
          port_vs_weak=bool(float(pp.compounded_segment_return)>float(p1.compounded_segment_return))
          port_vs_market=bool(float(pp.compounded_segment_return)>float(p2.compounded_segment_return))
          ok=event_vs_weak and event_vs_market and port_vs_weak and port_vs_market
          if ok:passed+=1
          checks.append({
            "rank_cap":cap,"target_fraction":target,"period":period,
            "primary_n":int(ep.n),
            "primary_mean_trade":float(ep.mean_trade),
            "primary_pf":None if pd.isna(ep.profit_factor) else float(ep.profit_factor),
            "weak_stock_weak_market_mean_trade":float(e1.mean_trade),
            "weak_stock_weak_market_pf":None if pd.isna(e1.profit_factor) else float(e1.profit_factor),
            "strong_stock_strong_market_mean_trade":float(e2.mean_trade),
            "strong_stock_strong_market_pf":None if pd.isna(e2.profit_factor) else float(e2.profit_factor),
            "primary_portfolio_comp":float(pp.compounded_segment_return),
            "weak_stock_weak_market_portfolio_comp":float(p1.compounded_segment_return),
            "strong_stock_strong_market_portfolio_comp":float(p2.compounded_segment_return),
            "event_vs_weak":event_vs_weak,"event_vs_market":event_vs_market,
            "portfolio_vs_weak":port_vs_weak,"portfolio_vs_market":port_vs_market,
            "passed":ok,
          })
    summary["support"][feat]={
      "passed_checks":passed,"total_checks":total,
      "all_checks_passed":bool(total>0 and passed==total),
      "checks":checks
    }

(out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
print(json.dumps({
 "schema":summary["schema"],
 "support":{k:{"passed":v["passed_checks"],"total":v["total_checks"],"all":v["all_checks_passed"]}
            for k,v in summary["support"].items()}
},indent=2))
