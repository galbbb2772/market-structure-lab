#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, statistics
from pathlib import Path
import pandas as pd

ap=argparse.ArgumentParser()
ap.add_argument("--indir",required=True)
ap.add_argument("--outdir",required=True)
a=ap.parse_args()
src=Path(a.indir);out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

efiles=sorted(src.glob("**/large_permission_events_*.csv"))
pfiles=sorted(src.glob("**/large_permission_portfolios_*.csv"))
if len(efiles)<8 or len(pfiles)<8:
    raise RuntimeError(f"expected 8 event + 8 portfolio shards, got {len(efiles)} {len(pfiles)}")

e=pd.concat([pd.read_csv(f) for f in efiles],ignore_index=True)
p=pd.concat([pd.read_csv(f) for f in pfiles],ignore_index=True)
e["period"]=e.year.map(lambda y:"discovery" if int(y)<=2022 else "validation")
p["period"]=p.year.map(lambda y:"discovery" if int(y)<=2022 else "validation")
e.to_csv(out/"annual_event_state_stats.csv",index=False)
p.to_csv(out/"annual_portfolio_state_stats.csv",index=False)

def wavg(g,col,w="n"):
    z=g[[col,w]].dropna()
    if z.empty:return None
    ww=z[w].astype(float)
    if ww.sum()<=0:return None
    return float((z[col].astype(float)*ww).sum()/ww.sum())

event_rows=[]
for (cap,target,dim,state,period),g in e.groupby(
    ["rank_cap","target_fraction","state_dimension","state","period"],dropna=False
):
    gp=float(g.gross_positive_return_sum.sum())
    gl=float(g.gross_negative_return_abs_sum.sum())
    n=int(g.n.sum())
    event_rows.append({
      "rank_cap":int(cap),"target_fraction":float(target),
      "state_dimension":str(dim),"state":str(state),"period":period,
      "n":n,
      "mean_trade":wavg(g,"mean_trade"),
      "weighted_year_median_trade":wavg(g,"median_trade"),
      "profit_factor":gp/gl if gl>0 else None,
      "win_rate":wavg(g,"win_rate"),
      "target_share":wavg(g,"target_share"),
      "stop_share":wavg(g,"stop_share"),
      "max_hold_share":wavg(g,"max_hold_share"),
      "mean_holding_sessions":wavg(g,"mean_holding_sessions"),
      "mean_mfe_return":wavg(g,"mean_mfe_return"),
      "mean_mae_return":wavg(g,"mean_mae_return"),
      "years_present":int(g.year.nunique()),
      "yearly_n":{str(int(r.year)):int(r.n) for r in g.itertuples()},
      "yearly_mean_trade":{str(int(r.year)):float(r.mean_trade) for r in g.itertuples()},
    })
event_agg=pd.DataFrame(event_rows)
event_agg.to_csv(out/"event_state_summary.csv",index=False)

portfolio_rows=[]
for (cap,target,dim,state,lane,period),g in p.groupby(
    ["rank_cap","target_fraction","state_dimension","state","portfolio_lane","period"],dropna=False
):
    comp=1.0
    for r in g.sort_values("year").itertuples():
        comp*=1+float(r.total_return)
    portfolio_rows.append({
      "rank_cap":int(cap),"target_fraction":float(target),
      "state_dimension":str(dim),"state":str(state),"portfolio_lane":str(lane),
      "period":period,"segments":int(len(g)),
      "compounded_segment_return":comp-1,
      "positive_segments":int((g.total_return>0).sum()),
      "avg_segment_return":float(g.total_return.mean()) if len(g) else None,
      "avg_sharpe":float(g.sharpe.mean()) if g.sharpe.notna().any() else None,
      "worst_segment_mdd":float(g.max_drawdown.min()) if g.max_drawdown.notna().any() else None,
      "avg_exposure":float(g.avg_exposure.mean()) if len(g) else None,
      "total_trades":int(g.completed_trades.sum()) if len(g) else 0,
      "avg_pf":float(g.profit_factor.mean()) if g.profit_factor.notna().any() else None,
      "yearly_return":{str(int(r.year)):float(r.total_return) for r in g.itertuples()},
    })
portfolio_agg=pd.DataFrame(portfolio_rows)
portfolio_agg.to_csv(out/"portfolio_state_summary.csv",index=False)

# Pair discovery / validation for mechanism screening.
screen=[]
keys=event_agg[["rank_cap","target_fraction","state_dimension","state"]].drop_duplicates()
for r in keys.itertuples(index=False):
    z=event_agg[
      (event_agg.rank_cap==r.rank_cap)&
      (event_agg.target_fraction==r.target_fraction)&
      (event_agg.state_dimension==r.state_dimension)&
      (event_agg.state==r.state)
    ]
    d=z[z.period=="discovery"]
    v=z[z.period=="validation"]
    if d.empty or v.empty:continue
    dd=d.iloc[0];vv=v.iloc[0]
    screen.append({
      "rank_cap":int(r.rank_cap),"target_fraction":float(r.target_fraction),
      "state_dimension":r.state_dimension,"state":r.state,
      "discovery_n":int(dd.n),"validation_n":int(vv.n),
      "discovery_mean_trade":float(dd.mean_trade),
      "validation_mean_trade":float(vv.mean_trade),
      "discovery_pf":None if pd.isna(dd.profit_factor) else float(dd.profit_factor),
      "validation_pf":None if pd.isna(vv.profit_factor) else float(vv.profit_factor),
      "discovery_stop_share":float(dd.stop_share),
      "validation_stop_share":float(vv.stop_share),
      "same_mean_sign":bool((dd.mean_trade>=0)==(vv.mean_trade>=0)),
      "same_pf_side":bool(
         pd.notna(dd.profit_factor) and pd.notna(vv.profit_factor) and
         ((dd.profit_factor>=1)==(vv.profit_factor>=1))
      ),
    })
screen_df=pd.DataFrame(screen)
screen_df.to_csv(out/"mechanism_screen.csv",index=False)

# Compact top500 target60 report plus top300 robustness.
summary={
 "schema":"LARGE-MARKET-PERMISSION-V1",
 "discovery":"2019-2022",
 "validation":"2023-2026Q1",
 "primary_target":0.60,
 "robustness_target":0.80,
 "preexisting_state_definitions_only":True,
 "top500_target60":[],
 "top300_target60":[],
}
for cap,key in [(500,"top500_target60"),(300,"top300_target60")]:
    z=screen_df[(screen_df.rank_cap==cap)&(screen_df.target_fraction==.60)].copy()
    # Sort with replicated weak states first, then sample size.
    z["replicated_weak"]=(
       (z.discovery_mean_trade<0)&(z.validation_mean_trade<0)&
       (z.discovery_pf<1)&(z.validation_pf<1)
    )
    z["replicated_strong"]=(
       (z.discovery_mean_trade>0)&(z.validation_mean_trade>0)&
       (z.discovery_pf>1)&(z.validation_pf>1)
    )
    z=z.sort_values(["replicated_weak","replicated_strong","validation_n"],
                    ascending=[False,False,False])
    summary[key]=z.to_dict("records")

# Baseline portfolio annual reference.
base=portfolio_agg[
  (portfolio_agg.state_dimension=="ALL")&
  (portfolio_agg.state=="ALL")&
  (portfolio_agg.portfolio_lane=="baseline")
]
summary["baseline_portfolio"]={}
for cap in (300,500):
  summary["baseline_portfolio"][f"top{cap}"]={}
  for target in (.60,.80):
    summary["baseline_portfolio"][f"top{cap}"][f"t{int(target*100)}"]={}
    for period in ("discovery","validation"):
      g=base[(base.rank_cap==cap)&(base.target_fraction==target)&(base.period==period)]
      if len(g):
        rr=g.iloc[0]
        summary["baseline_portfolio"][f"top{cap}"][f"t{int(target*100)}"][period]={
          "compounded_segment_return":float(rr.compounded_segment_return),
          "positive_segments":int(rr.positive_segments),
          "avg_sharpe":None if pd.isna(rr.avg_sharpe) else float(rr.avg_sharpe),
          "worst_segment_mdd":None if pd.isna(rr.worst_segment_mdd) else float(rr.worst_segment_mdd),
          "avg_exposure":float(rr.avg_exposure),
          "yearly_return":rr.yearly_return,
        }

(out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
print(json.dumps({
  "schema":summary["schema"],
  "top500_target60_first10":summary["top500_target60"][:10],
  "baseline_portfolio":summary["baseline_portfolio"]
},indent=2))
