#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd
import research_pure_box_large_market_permission_year_v1 as large

TARGETS=(.60,.80)

ap=argparse.ArgumentParser()
ap.add_argument("--year",type=int,required=True)
ap.add_argument("--indir",required=True)
ap.add_argument("--labels",required=True)
ap.add_argument("--outdir",required=True)
a=ap.parse_args()
out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

_,cal,_,_,bm,_=large.load(a.indir,a.year)
lab=pd.read_csv(a.labels,compression="infer")
lab["year"]=lab.year.astype(int)

rows=[]
for cap in (300,500):
    z=lab[(lab.year==a.year)&(lab.rank_cap==cap)].copy()
    thr=float(z.expanding_q20.iloc[0]) if len(z) else None
    lanes=[
      ("BASELINE","ALL",z),
      ("EXPANDING","NON_EXTREME",z[z.expanding_lane=="NON_EXTREME"]),
      ("EXPANDING","EXTREME_TAIL",z[z.expanding_lane=="EXTREME_TAIL"]),
      ("FIXED_-1PCT","NON_EXTREME",z[z.fixed_lane=="NON_EXTREME"]),
      ("FIXED_-1PCT","EXTREME_TAIL",z[z.fixed_lane=="EXTREME_TAIL"]),
    ]
    for target in TARGETS:
        for method,lane,g in lanes:
            res=large.run_portfolio(g,bm,cal,a.year,target)
            rows.append({
              "year":a.year,"rank_cap":cap,"target_fraction":target,
              "method":method,"lane":lane,
              "expanding_q20":thr,
              "candidate_count":int(len(g)),
              **res
            })
df=pd.DataFrame(rows)
df.to_csv(out/f"gap_tail_{a.year}.csv",index=False)
print(json.dumps({"schema":"LARGE-GAP-TAIL-YEAR-V4","year":a.year,"rows":len(df)},indent=2))
