#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd

TEST_YEARS=(2021,2022,2023,2024,2025,2026)

ap=argparse.ArgumentParser()
ap.add_argument("--labels",required=True)
ap.add_argument("--outdir",required=True)
a=ap.parse_args()
out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
x=pd.read_csv(a.labels,compression="infer")
x["year"]=x.year.astype(int)

rows=[];parts=[]
for cap in (300,500):
    z=x[x.rank_cap==cap].copy()
    for year in TEST_YEARS:
        hist=z[(z.year<year)&z.gap_component.notna()]
        if hist.empty: raise RuntimeError(f"no history cap={cap} year={year}")
        q20=float(hist.gap_component.quantile(.20))
        cur=z[z.year==year].copy()
        cur["expanding_q20"]=q20
        cur["expanding_lane"]=cur.gap_component.map(
            lambda v:"EXTREME_TAIL" if pd.notna(v) and float(v)<=q20 else "NON_EXTREME"
        )
        cur["fixed_lane"]=cur.gap_component.map(
            lambda v:"EXTREME_TAIL" if pd.notna(v) and float(v)<=-.01 else "NON_EXTREME"
        )
        rows.append({
          "rank_cap":cap,"test_year":year,"history_start":int(hist.year.min()),
          "history_end":int(hist.year.max()),"history_n":int(len(hist)),
          "expanding_q20":q20,
          "test_n":int(len(cur)),
          "expanding_extreme_n":int((cur.expanding_lane=="EXTREME_TAIL").sum()),
          "fixed_extreme_n":int((cur.fixed_lane=="EXTREME_TAIL").sum()),
        })
        parts.append(cur)

lab=pd.concat(parts,ignore_index=True)
pd.DataFrame(rows).to_csv(out/"thresholds_by_year.csv",index=False)
lab.to_csv(out/"tail_labeled_candidates.csv.gz",index=False,compression="gzip")
(out/"summary.json").write_text(json.dumps({
  "schema":"LARGE-GAP-TAIL-PREP-V4",
  "test_years":list(TEST_YEARS),
  "rows":len(rows),
  "candidates":len(lab)
},indent=2))
print(open(out/"summary.json").read())
