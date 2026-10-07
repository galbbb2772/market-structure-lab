#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd

import research_pure_box_large_market_permission_year_v1 as large

FEATURES=[
 "pct_up_1d",
 "new_low_relief_1d",
 "new_low_relief_3d",
 "ma50_recovery_3d",
 "ret20_recovery_3d",
 "median_ret20_recovery_3d",
]
TARGETS=(.60,.80)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--year",type=int,required=True)
    ap.add_argument("--indir",required=True)
    ap.add_argument("--labels",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

    _,cal,_,_,bm,_=large.load(a.indir,a.year)
    labels=pd.read_csv(a.labels,compression="infer")
    labels["year"]=labels.year.astype(int)
    rows=[]

    for cap in (300,500):
        z=labels[(labels.year==a.year)&(labels.rank_cap==cap)].copy()
        for target in TARGETS:
            base=large.run_portfolio(z,bm,cal,a.year,target)
            rows.append({
              "year":a.year,"rank_cap":cap,"target_fraction":target,
              "feature":"ALL","quintile_lane":"ALL",**base
            })
            for feat in FEATURES:
                qcol=f"q__{feat}"
                if qcol not in z.columns:continue
                for q,lane in [(1,"Q1"),(5,"Q5")]:
                    g=z[z[qcol]==q].copy()
                    res=large.run_portfolio(g,bm,cal,a.year,target)
                    rows.append({
                      "year":a.year,"rank_cap":cap,"target_fraction":target,
                      "feature":feat,"quintile_lane":lane,**res
                    })

    df=pd.DataFrame(rows)
    df.to_csv(out/f"market_exhaustion_portfolio_{a.year}.csv",index=False)
    print(json.dumps({
      "schema":"LARGE-MARKET-EXHAUSTION-PORTFOLIO-YEAR-V3",
      "year":a.year,"rows":len(df)
    },indent=2))

if __name__=="__main__":
    main()
