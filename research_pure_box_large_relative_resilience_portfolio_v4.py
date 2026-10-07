#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd

import research_pure_box_large_market_permission_year_v1 as large

TARGETS=(.60,.80)
CORNERS_A=[
 "STOCK_STRONG_MARKET_WEAK",
 "STOCK_STRONG_MARKET_STRONG",
 "STOCK_WEAK_MARKET_WEAK",
 "STOCK_WEAK_MARKET_STRONG",
]
CORNERS_B=[
 "STOCK_STRONG_MARKET_STRESSED",
 "STOCK_STRONG_MARKET_CALM",
 "STOCK_WEAK_MARKET_STRESSED",
 "STOCK_WEAK_MARKET_CALM",
]

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
              "grid":"ALL","corner":"ALL",**base
            })
            for grid,col,corners in [
              ("A","corner_a",CORNERS_A),
              ("B","corner_b",CORNERS_B),
            ]:
                for corner in corners:
                    g=z[z[col].astype(str)==corner].copy()
                    res=large.run_portfolio(g,bm,cal,a.year,target)
                    rows.append({
                      "year":a.year,"rank_cap":cap,"target_fraction":target,
                      "grid":grid,"corner":corner,**res
                    })

    df=pd.DataFrame(rows)
    df.to_csv(out/f"relative_resilience_portfolio_{a.year}.csv",index=False)
    print(json.dumps({
      "schema":"LARGE-RELATIVE-RESILIENCE-PORTFOLIO-YEAR-V4",
      "year":a.year,"rows":len(df)
    },indent=2))

if __name__=="__main__":
    main()
