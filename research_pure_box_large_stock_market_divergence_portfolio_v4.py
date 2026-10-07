#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd
import research_pure_box_large_market_permission_year_v1 as large

FEATURES=["rebound_from_low_box","low_progress_box"]
CELLS=[
 "STRONG_STOCK|WEAK_MARKET_DAY",
 "STRONG_STOCK|STRONG_MARKET_DAY",
 "WEAK_STOCK|WEAK_MARKET_DAY",
 "WEAK_STOCK|STRONG_MARKET_DAY",
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
    lab=pd.read_csv(a.labels,compression="infer")
    lab=lab[lab.year.astype(int)==a.year].copy()
    rows=[]
    for cap in (300,500):
      z=lab[lab.rank_cap==cap].copy()
      for target in (.60,.80):
        base=large.run_portfolio(z,bm,cal,a.year,target)
        rows.append({"year":a.year,"rank_cap":cap,"target_fraction":target,
                     "feature":"ALL","cell":"ALL",**base})
        for feat in FEATURES:
          col=f"cell__{feat}"
          for cell in CELLS:
            g=z[z[col]==cell].copy()
            res=large.run_portfolio(g,bm,cal,a.year,target)
            rows.append({"year":a.year,"rank_cap":cap,"target_fraction":target,
                         "feature":feat,"cell":cell,**res})

    df=pd.DataFrame(rows)
    df.to_csv(out/f"stock_market_divergence_portfolio_{a.year}.csv",index=False)
    print(json.dumps({"schema":"LARGE-STOCK-MARKET-DIVERGENCE-PORTFOLIO-YEAR-V4",
                      "year":a.year,"rows":len(df)},indent=2))

if __name__=="__main__":
    main()
