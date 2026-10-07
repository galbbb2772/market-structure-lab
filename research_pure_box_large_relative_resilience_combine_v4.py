#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd

STOCK=["rebound_from_low_box","low_progress_box"]
MARKET=["pct_up_1d","pct_new_20d_low"]

def qcuts(s):
    x=pd.to_numeric(s,errors="coerce").dropna()
    return [float(x.quantile(q)) for q in (.2,.4,.6,.8)]

def qassign(v,cuts):
    if pd.isna(v): return np.nan
    return int(np.searchsorted(np.asarray(cuts,float),float(v),side="right")+1)

def pf(rs):
    rs=[float(x) for x in rs if pd.notna(x)]
    w=sum(x for x in rs if x>0); l=-sum(x for x in rs if x<0)
    return w/l if l>0 else None

ap=argparse.ArgumentParser()
ap.add_argument("--indir",required=True)
ap.add_argument("--outdir",required=True)
a=ap.parse_args()
src=Path(a.indir);out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

cfiles=sorted(src.glob("**/relative_resilience_candidates_*.csv.gz"))
efiles=sorted(src.glob("**/relative_resilience_events_*.csv.gz"))
if len(cfiles)<16 or len(efiles)<32:
    raise RuntimeError(f"expected >=16 candidate and >=32 event shards, got {len(cfiles)} {len(efiles)}")

cand=pd.concat([pd.read_csv(f) for f in cfiles],ignore_index=True)
ev=pd.concat([pd.read_csv(f) for f in efiles],ignore_index=True)
cand["year"]=cand.year.astype(int);ev["year"]=ev.year.astype(int)
cand["period"]=np.where(cand.year<=2022,"discovery","validation")
ev["period"]=np.where(ev.year<=2022,"discovery","validation")

thresholds={}
for cap in (300,500):
    thresholds[f"top{cap}"]={}
    d=cand[(cand.rank_cap==cap)&(cand.period=="discovery")]
    for feat in STOCK+MARKET:
        cuts=qcuts(d[feat]);thresholds[f"top{cap}"][feat]=cuts
        cm=cand.rank_cap==cap; em=ev.rank_cap==cap
        cand.loc[cm,f"q__{feat}"]=cand.loc[cm,feat].map(lambda v:qassign(v,cuts))
        ev.loc[em,f"q__{feat}"]=ev.loc[em,feat].map(lambda v:qassign(v,cuts))

# Corner definitions.
def corner_a(r):
    sq=r.get("q__rebound_from_low_box"); mq=r.get("q__pct_up_1d")
    if sq==5 and mq==1:return "STOCK_STRONG_MARKET_WEAK"
    if sq==5 and mq==5:return "STOCK_STRONG_MARKET_STRONG"
    if sq==1 and mq==1:return "STOCK_WEAK_MARKET_WEAK"
    if sq==1 and mq==5:return "STOCK_WEAK_MARKET_STRONG"
    return None
def corner_b(r):
    sq=r.get("q__low_progress_box"); mq=r.get("q__pct_new_20d_low")
    if sq==5 and mq==5:return "STOCK_STRONG_MARKET_STRESSED"
    if sq==5 and mq==1:return "STOCK_STRONG_MARKET_CALM"
    if sq==1 and mq==5:return "STOCK_WEAK_MARKET_STRESSED"
    if sq==1 and mq==1:return "STOCK_WEAK_MARKET_CALM"
    return None

cand["corner_a"]=cand.apply(corner_a,axis=1)
cand["corner_b"]=cand.apply(corner_b,axis=1)
ev["corner_a"]=ev.apply(corner_a,axis=1)
ev["corner_b"]=ev.apply(corner_b,axis=1)

cand.to_csv(out/"labeled_candidates.csv.gz",index=False,compression="gzip")
(out/"thresholds.json").write_text(json.dumps(thresholds,indent=2),encoding="utf-8")

rows=[]
for grid,col in [("A","corner_a"),("B","corner_b")]:
    for (cap,target,period,corner),g in ev.dropna(subset=[col]).groupby(
      ["rank_cap","target_fraction","period",col]
    ):
        rs=g.net_return.astype(float).tolist()
        reasons=g.exit_reason.astype(str)
        rows.append({
          "grid":grid,"rank_cap":int(cap),"target_fraction":float(target),
          "period":period,"corner":corner,"n":int(len(g)),
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
edf.to_csv(out/"event_corner_summary.csv",index=False)

summary={
 "schema":"LARGE-RELATIVE-RESILIENCE-MECHANISM-V4",
 "discovery":"2019-2022","validation":"2023-2026Q1",
 "thresholds":thresholds,
 "event_corners":rows
}
(out/"mechanism_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
print(json.dumps({"schema":summary["schema"],"candidates":len(cand),"events":len(ev),"corner_rows":len(edf)},indent=2))
