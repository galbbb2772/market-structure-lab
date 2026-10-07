#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math, statistics
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd

import research_pure_box_large_market_permission_year_v1 as large
import research_pure_box_breadth_permission_v1 as breadthmod

ENTRY_COST=.0005
EXIT_COST=.0005
ALLOC=.10
MAX_HOLD=20
TARGETS={"60":.60,"80":.80}
FRESH={300:23,500:24}
FEATURES=[
 "pct_up_1d",
 "new_low_relief_1d",
 "new_low_relief_3d",
 "ma50_recovery_3d",
 "ret20_recovery_3d",
 "median_ret20_recovery_3d",
]

def qcuts(s):
    x=pd.to_numeric(s,errors="coerce").dropna()
    return [float(x.quantile(q)) for q in (.2,.4,.6,.8)]

def qassign(v,cuts):
    if pd.isna(v):return np.nan
    return int(np.searchsorted(np.asarray(cuts,float),float(v),side="right")+1)

def spearman(a,b):
    z=pd.DataFrame({"a":a,"b":b}).dropna()
    if len(z)<10:return None
    return float(z.a.rank(method="average").corr(z.b.rank(method="average")))

def enrich_breadth(b):
    x=b.copy().sort_values("date").reset_index(drop=True)
    x["new_low_relief_1d"]=x.pct_new_20d_low.shift(1)-x.pct_new_20d_low
    x["new_low_relief_3d"]=x.pct_new_20d_low.shift(3)-x.pct_new_20d_low
    x["ma50_recovery_3d"]=x.pct_above_ma50-x.pct_above_ma50.shift(3)
    x["ret20_recovery_3d"]=x.pct_ret20_positive-x.pct_ret20_positive.shift(3)
    x["median_ret20_recovery_3d"]=x.median_ret20-x.median_ret20.shift(3)
    return x

def make_events(c,bm,calendar,target_frac):
    large.CALENDAR=calendar
    ci={d:i for i,d in enumerate(calendar)}
    rows=[]
    for r in c.to_dict("records"):
        x=large.event_outcome(r,bm,ci,target_frac)
        if x is not None:
            rows.append({**r,"target_fraction":target_frac,**x})
    return pd.DataFrame(rows)

def run_portfolio(c,bm,calendar,year,target_frac):
    return large.run_portfolio(c,bm,calendar,year,target_frac)

def load_year(indir,year):
    sig,cal,idx,nxt,bm,spy=large.load(indir,year)
    # Rebuild a bars frame from the same yearly artifacts so breadth is identical
    # to Breadth Permission V1.
    p=Path(indir)
    parts=[]
    for bp in sorted(p.glob("**/bars_*.csv.gz")):
        for ch in pd.read_csv(bp,chunksize=300000):
            ch["date"]=ch.date.astype(str);ch["ticker"]=ch.ticker.astype(str)
            parts.append(ch)
    bars=pd.concat(parts,ignore_index=True)
    bars=bars.sort_values(["ticker","date"]).drop_duplicates(["ticker","date"],keep="last")
    return sig,cal,idx,nxt,bm,bars

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--year",type=int,required=True)
    ap.add_argument("--indir",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

    sig,cal,idx,nxt,bm,bars=load_year(a.indir,a.year)
    # Regime fields are unnecessary; use empty mapping.
    c=large.confirmed(sig,cal,idx,nxt,bm,{})
    c=c[c.scale=="large"].copy()

    event_rows=[]
    portfolio_rows=[]
    receipt={"schema":"LARGE-MARKET-EXHAUSTION-YEAR-V3","year":a.year,"caps":{}}

    for cap in (300,500):
        b=enrich_breadth(breadthmod.build_breadth(bars,cap))
        bmap={r["date"]:r for r in b.to_dict("records")}
        z=c[(c.liquidity_rank<=cap)&(c.box_age_sessions<=FRESH[cap])].copy()
        # Features must be known by confirmation close.
        for feat in FEATURES:
            z[feat]=z.confirmation_date.map(lambda d:bmap.get(str(d),{}).get(feat,np.nan))
        z["breadth_date"]=z.confirmation_date

        receipt["caps"][str(cap)]={
          "confirmed_fresh_large":int(len(z)),
          "feature_nonnull":{f:int(z[f].notna().sum()) for f in FEATURES}
        }

        # Persist row-level observations once per cap; outcome columns added per target below.
        for label,frac in TARGETS.items():
            e=make_events(z,bm,cal,frac)
            if e.empty:continue
            for feat in FEATURES:
                for q in range(1,6):
                    # Year worker cannot assign discovery-fixed quintiles; raw values are persisted.
                    pass
                y_target=e.exit_reason.astype(str).isin(["target","target_gap"]).astype(float)
                y_stop=e.exit_reason.astype(str).isin(["stop","stop_gap"]).astype(float)
                event_rows.append({
                  "year":a.year,"rank_cap":cap,"target_fraction":frac,
                  "feature":feat,"scope":"continuous",
                  "n":int(e[feat].notna().sum()),
                  "mean_feature":float(pd.to_numeric(e[feat],errors="coerce").mean()),
                  "rho_return":spearman(e[feat],e.net_return),
                  "rho_target":spearman(e[feat],y_target),
                  "rho_stop":spearman(e[feat],y_stop),
                })

            keep=["year","rank_cap","target_fraction","symbol","signal_date","confirmation_date","entry_date",
                  "entry_price","lower","upper","liquidity_rank","box_age_sessions",
                  "exit_reason","holding_sessions","net_return","mfe_return","mae_return"]+FEATURES
            ee=e.copy()
            ee["year"]=a.year;ee["rank_cap"]=cap
            ee[keep].to_csv(out/f"events_{cap}_{label}_{a.year}.csv.gz",index=False,compression="gzip")

    pd.DataFrame(event_rows).to_csv(out/f"continuous_{a.year}.csv",index=False)
    (out/f"summary_{a.year}.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
    print(json.dumps(receipt,indent=2))

if __name__=="__main__":
    main()
