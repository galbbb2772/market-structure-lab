#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd

STOCK_FEATURES=["rebound_from_low_box","low_progress_box"]
CELLS=[
 "STRONG_STOCK|WEAK_MARKET_DAY",
 "STRONG_STOCK|STRONG_MARKET_DAY",
 "WEAK_STOCK|WEAK_MARKET_DAY",
 "WEAK_STOCK|STRONG_MARKET_DAY",
]

def pf(rs):
    rs=[float(x) for x in rs if pd.notna(x)]
    w=sum(x for x in rs if x>0);l=-sum(x for x in rs if x<0)
    return w/l if l>0 else None

ap=argparse.ArgumentParser()
ap.add_argument("--indir",required=True)
ap.add_argument("--outdir",required=True)
a=ap.parse_args()
src=Path(a.indir);out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

cfiles=sorted(src.glob("**/candidates_*.csv.gz"))
efiles=sorted(src.glob("**/events_*.csv.gz"))
if len(cfiles)<16 or len(efiles)<32:
    raise RuntimeError(f"expected >=16 candidate and >=32 event shards, got {len(cfiles)} {len(efiles)}")

cand=pd.concat([pd.read_csv(f) for f in cfiles],ignore_index=True)
events=pd.concat([pd.read_csv(f) for f in efiles],ignore_index=True)
cand["period"]=np.where(cand.year.astype(int)<=2022,"discovery","validation")
events["period"]=np.where(events.year.astype(int)<=2022,"discovery","validation")

thresholds={}
for cap in (300,500):
    thresholds[f"top{cap}"]={}
    d=cand[(cand.rank_cap==cap)&(cand.period=="discovery")]
    for feat in STOCK_FEATURES:
        med=float(pd.to_numeric(d[feat],errors="coerce").median())
        thresholds[f"top{cap}"][feat]=med
        for df in (cand,events):
            m=df.rank_cap==cap
            stock=np.where(pd.to_numeric(df.loc[m,feat],errors="coerce")>=med,"STRONG_STOCK","WEAK_STOCK")
            market=df.loc[m,"market_state"].astype(str).to_numpy()
            df.loc[m,f"cell__{feat}"]=[f"{s}|{mk}" if mk in ("WEAK_MARKET_DAY","STRONG_MARKET_DAY") else None
                                          for s,mk in zip(stock,market)]

(out/"thresholds.json").write_text(json.dumps(thresholds,indent=2),encoding="utf-8")
cand.to_csv(out/"labeled_candidates.csv.gz",index=False,compression="gzip")

rows=[]
for cap in (300,500):
  for target in (.60,.80):
    for feat in STOCK_FEATURES:
      col=f"cell__{feat}"
      for period in ("discovery","validation"):
        z=events[(events.rank_cap==cap)&(events.target_fraction==target)&(events.period==period)]
        for cell in CELLS:
          g=z[z[col]==cell].copy()
          if g.empty:continue
          rs=g.net_return.astype(float).tolist();reasons=g.exit_reason.astype(str)
          rows.append({
            "rank_cap":cap,"target_fraction":target,"feature":feat,"period":period,"cell":cell,
            "n":int(len(g)),
            "mean_trade":float(g.net_return.mean()),
            "median_trade":float(g.net_return.median()),
            "profit_factor":pf(rs),
            "win_rate":float((g.net_return>0).mean()),
            "target_share":float(reasons.isin(["target","target_gap"]).mean()),
            "stop_share":float(reasons.isin(["stop","stop_gap"]).mean()),
            "max_hold_share":float(reasons.str.startswith("max_hold").mean()),
            "mean_holding_sessions":float(g.holding_sessions.mean()),
            "mean_mfe_return":float(g.mfe_return.mean()),
            "mean_mae_return":float(g.mae_return.mean()),
            "yearly_mean_trade":json.dumps({
              str(int(y)):float(gg.net_return.mean()) for y,gg in g.groupby("year")
            },sort_keys=True),
            "yearly_pf":json.dumps({
              str(int(y)):pf(gg.net_return.astype(float).tolist()) for y,gg in g.groupby("year")
            },sort_keys=True),
            "yearly_n":json.dumps({
              str(int(y)):int(len(gg)) for y,gg in g.groupby("year")
            },sort_keys=True),
          })
edf=pd.DataFrame(rows)
edf.to_csv(out/"event_cells.csv",index=False)

summary={"schema":"LARGE-STOCK-MARKET-DIVERGENCE-MECHANISM-V4",
         "thresholds":thresholds,"features":{}}
for feat in STOCK_FEATURES:
  summary["features"][feat]={}
  for cap in (300,500):
    summary["features"][feat][f"top{cap}"]={}
    for target in (.60,.80):
      tk=f"t{int(target*100)}";summary["features"][feat][f"top{cap}"][tk]={}
      for period in ("discovery","validation"):
        z=edf[(edf.feature==feat)&(edf.rank_cap==cap)&
              (edf.target_fraction==target)&(edf.period==period)]
        summary["features"][feat][f"top{cap}"][tk][period]={
          r.cell:{
            "n":int(r.n),"mean_trade":float(r.mean_trade),
            "profit_factor":None if pd.isna(r.profit_factor) else float(r.profit_factor),
            "win_rate":float(r.win_rate),"target_share":float(r.target_share),
            "stop_share":float(r.stop_share),
            "mean_holding_sessions":float(r.mean_holding_sessions),
            "yearly_mean_trade":json.loads(r.yearly_mean_trade),
            "yearly_pf":json.loads(r.yearly_pf),
          } for r in z.itertuples()
        }

(out/"mechanism_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
print(json.dumps({"schema":summary["schema"],"candidate_rows":len(cand),"event_cell_rows":len(edf)},indent=2))
