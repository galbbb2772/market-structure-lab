#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd

TEST_YEARS=(2021,2022,2023,2024,2025,2026)
KEYS=["year","rank_cap","symbol","signal_date","confirmation_date","entry_date"]

ap=argparse.ArgumentParser()
ap.add_argument("--anatomy-labels",required=True)
ap.add_argument("--resilience-labels",required=True)
ap.add_argument("--outdir",required=True)
a=ap.parse_args()
out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

ga=pd.read_csv(a.anatomy_labels,compression="infer")
rr=pd.read_csv(a.resilience_labels,compression="infer")
for x in (ga,rr):
    x["year"]=x.year.astype(int)
    x["rank_cap"]=x.rank_cap.astype(int)
    for c in ["symbol","signal_date","confirmation_date","entry_date"]:
        x[c]=x[c].astype(str)

keep_rr=KEYS+["rebound_from_low_box","low_progress_box"]
m=ga.merge(rr[keep_rr],on=KEYS,how="inner",validate="one_to_one")
if len(m)<1000:
    raise RuntimeError(f"unexpectedly small merged candidate set: {len(m)}")

threshold_rows=[];parts=[]
for cap in (300,500):
    z=m[m.rank_cap==cap].copy()
    for year in TEST_YEARS:
        hist=z[z.year<year].copy()
        cur=z[z.year==year].copy()
        if len(hist)<100:
            raise RuntimeError(f"not enough history cap={cap} year={year}: {len(hist)}")
        gap_q20=float(hist.gap_component.dropna().quantile(.20))
        rebound_med=float(hist.rebound_from_low_box.dropna().median())
        lowprog_med=float(hist.low_progress_box.dropna().median())
        cur["gap_q20_prior"]=gap_q20
        cur["rebound_median_prior"]=rebound_med
        cur["lowprog_median_prior"]=lowprog_med
        cur["gap_expanding_lane"]=cur.gap_component.map(
            lambda v:"EXTREME_GAP" if pd.notna(v) and float(v)<=gap_q20 else "NON_EXTREME"
        )
        cur["gap_fixed_lane"]=cur.gap_component.map(
            lambda v:"EXTREME_GAP" if pd.notna(v) and float(v)<=-.01 else "NON_EXTREME"
        )
        cur["rebound_strength"]=cur.rebound_from_low_box.map(
            lambda v:"STRONG" if pd.notna(v) and float(v)>rebound_med else "WEAK"
        )
        cur["lowprog_strength"]=cur.low_progress_box.map(
            lambda v:"STRONG" if pd.notna(v) and float(v)>lowprog_med else "WEAK"
        )
        threshold_rows.append({
          "rank_cap":cap,"test_year":year,
          "history_start":int(hist.year.min()),"history_end":int(hist.year.max()),
          "history_n":int(len(hist)),
          "gap_q20_prior":gap_q20,
          "rebound_median_prior":rebound_med,
          "lowprog_median_prior":lowprog_med,
          "test_n":int(len(cur)),
        })
        parts.append(cur)

lab=pd.concat(parts,ignore_index=True)
pd.DataFrame(threshold_rows).to_csv(out/"thresholds_by_year.csv",index=False)
lab.to_csv(out/"interaction_labeled_candidates.csv.gz",index=False,compression="gzip")
summary={"schema":"LARGE-GAP-EXHAUSTION-PREP-V5","merged_candidates":int(len(m)),
         "test_candidates":int(len(lab)),"threshold_rows":len(threshold_rows)}
(out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
print(json.dumps(summary,indent=2))
