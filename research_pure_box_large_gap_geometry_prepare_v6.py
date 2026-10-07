#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd

TEST_YEARS=(2021,2022,2023,2024,2025,2026)
KEYS=["year","rank_cap","symbol","signal_date","confirmation_date","entry_date"]

def qcuts(s):
    x=pd.to_numeric(s,errors="coerce").dropna()
    return [float(x.quantile(q)) for q in (.25,.50,.75)]

def qassign(v,cuts):
    if pd.isna(v): return np.nan
    return int(np.searchsorted(np.asarray(cuts,float),float(v),side="right")+1)

ap=argparse.ArgumentParser()
ap.add_argument("--anatomy-labels",required=True)
ap.add_argument("--resilience-labels",required=True)
ap.add_argument("--outdir",required=True)
a=ap.parse_args()
out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

ga=pd.read_csv(a.anatomy_labels,compression="infer")
rr=pd.read_csv(a.resilience_labels,compression="infer")
for x in (ga,rr):
    x["year"]=x.year.astype(int); x["rank_cap"]=x.rank_cap.astype(int)
    for c in ["symbol","signal_date","confirmation_date","entry_date"]:
        x[c]=x[c].astype(str)

keep_rr=KEYS+["rebound_from_low_box","low_progress_box"]
m=ga.merge(rr[keep_rr],on=KEYS,how="inner",validate="one_to_one")
w=(m["upper"].astype(float)-m["lower"].astype(float)).clip(lower=1e-12)
m["entry_fraction"]=(m["entry_price"].astype(float)-m["lower"].astype(float))/w
m["stop_distance"]=(m["entry_price"].astype(float)-m["lower"].astype(float))/m["entry_price"].astype(float)
for t in (.60,.80):
    key=str(int(t*100))
    target=m["lower"].astype(float)+t*w
    m[f"target_upside_{key}"]=target/m["entry_price"].astype(float)-1
    m[f"rr_{key}"]=m[f"target_upside_{key}"]/m["stop_distance"].replace(0,np.nan)

rows=[];parts=[]
for cap in (300,500):
    z=m[m.rank_cap==cap].copy()
    for year in TEST_YEARS:
        hist=z[z.year<year].copy(); cur=z[z.year==year].copy()
        if len(hist)<100: raise RuntimeError(f"insufficient history cap={cap} year={year}")
        gap_q20=float(hist.gap_component.dropna().quantile(.20))
        rb_med=float(hist.rebound_from_low_box.dropna().median())
        lp_med=float(hist.low_progress_box.dropna().median())
        cur["gap_q20_prior"]=gap_q20
        cur["rebound_median_prior"]=rb_med
        cur["lowprog_median_prior"]=lp_med
        cur["gap_expanding_lane"]=np.where(cur.gap_component<=gap_q20,"EXTREME_GAP","NON_EXTREME")
        cur["gap_fixed_lane"]=np.where(cur.gap_component<=-.01,"EXTREME_GAP","NON_EXTREME")
        cur["rebound_strength"]=np.where(cur.rebound_from_low_box>rb_med,"STRONG","WEAK")
        cur["lowprog_strength"]=np.where(cur.low_progress_box>lp_med,"STRONG","WEAK")

        rec={"rank_cap":cap,"test_year":year,"history_start":int(hist.year.min()),
             "history_end":int(hist.year.max()),"history_n":int(len(hist)),
             "gap_q20_prior":gap_q20,"rebound_median_prior":rb_med,"lowprog_median_prior":lp_med}
        for method,gcol in [("EXPANDING","gap_expanding_lane"),("FIXED_-1PCT","gap_fixed_lane")]:
            if method=="EXPANDING":
                he=hist[hist.gap_component<=gap_q20]
            else:
                he=hist[hist.gap_component<=-.01]
            cuts=qcuts(he.entry_fraction)
            cur[f"entry_q__{method}"]=cur.entry_fraction.map(lambda v:qassign(v,cuts))
            rec[f"{method}_entry_q25"]=cuts[0];rec[f"{method}_entry_q50"]=cuts[1];rec[f"{method}_entry_q75"]=cuts[2]
            rec[f"{method}_hist_extreme_n"]=int(len(he))
        rows.append(rec);parts.append(cur)

lab=pd.concat(parts,ignore_index=True)
pd.DataFrame(rows).to_csv(out/"thresholds_by_year.csv",index=False)
lab.to_csv(out/"geometry_labeled_candidates.csv.gz",index=False,compression="gzip")
summary={"schema":"LARGE-GAP-GEOMETRY-PREP-V6","merged_candidates":int(len(m)),
         "test_candidates":int(len(lab)),"threshold_rows":len(rows)}
(out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
print(json.dumps(summary,indent=2))
