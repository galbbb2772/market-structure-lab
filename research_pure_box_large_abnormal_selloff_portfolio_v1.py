#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd
import research_pure_box_large_market_permission_year_v1 as large

FEATURES=["selloff_1d_atr","selloff_3d_sigma","selloff_5d_sigma","spy_relative_3d_sigma","spy_relative_5d_sigma","own_history_5d_extreme"]
TARGETS=(.6,.8)
ap=argparse.ArgumentParser();ap.add_argument("--year",type=int,required=True);ap.add_argument("--indir",required=True);ap.add_argument("--labels",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
_,cal,_,_,bm,_=large.load(a.indir,a.year)
lab=pd.read_csv(a.labels,compression="infer");lab["year"]=lab.year.astype(int)
rows=[]
for cap in (300,500):
  z=lab[(lab.year==a.year)&(lab.rank_cap==cap)].copy()
  for target in TARGETS:
    rows.append({"year":a.year,"rank_cap":cap,"target_fraction":target,"feature":"ALL","lane":"ALL",**large.run_portfolio(z,bm,cal,a.year,target)})
    for feat in FEATURES:
      q=f"q__{feat}"
      for qn,lane in [(1,"Q1"),(5,"Q5")]:
        g=z[z[q]==qn].copy()
        rows.append({"year":a.year,"rank_cap":cap,"target_fraction":target,"feature":feat,"lane":lane,**large.run_portfolio(g,bm,cal,a.year,target)})
pd.DataFrame(rows).to_csv(out/f"abnormal_selloff_portfolio_{a.year}.csv",index=False)
print(json.dumps({"schema":"LARGE-ABNORMAL-SELLOFF-PORTFOLIO-YEAR-V1","year":a.year,"rows":len(rows)},indent=2))
