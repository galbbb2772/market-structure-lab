#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd

KEYS=["year","rank_cap","symbol","signal_date","confirmation_date","entry_date"]
TEST_YEARS=(2021,2022,2023,2024,2025,2026)
SEED=20261007
DRAWS=20000

def classify(events, labels):
    thr=[]
    for cap in (300,500):
        z=labels[labels.rank_cap==cap]
        for year in TEST_YEARS:
            hist=z[z.year<year].copy()
            gapq=float(hist.gap_component.dropna().quantile(.20))
            for method in ("EXPANDING","FIXED_-1PCT"):
                he=hist[hist.gap_component<=gapq] if method=="EXPANDING" else hist[hist.gap_component<=-.01]
                thr.append({
                    "rank_cap":cap,"year":year,"gap_method":method,
                    "gap_threshold":gapq if method=="EXPANDING" else -.01,
                    "lowprog_median":float(he.low_progress_box.dropna().median()),
                    "close_lift_median":float(he.close_lift_box.dropna().median()),
                })
    tdf=pd.DataFrame(thr)
    tmap={(int(r.rank_cap),int(r.year),r.gap_method):r for r in tdf.itertuples()}
    out=[]
    for method in ("EXPANDING","FIXED_-1PCT"):
        q=events.copy(); lane=[]; state=[]
        for r in q.itertuples():
            t=tmap[(int(r.rank_cap),int(r.year),method)]
            extreme=float(r.gap_component)<=float(t.gap_threshold)
            lane.append("EXTREME_GAP" if extreme else "NON_EXTREME")
            if not extreme:
                state.append(None); continue
            retest=float(r.low_progress_box)<=float(t.lowprog_median)
            lift=float(r.close_lift_box)>float(t.close_lift_median)
            if retest and lift: s="RETEST_LIFT"
            elif retest: s="RETEST_WEAK_LIFT"
            elif lift: s="NO_RETEST_LIFT"
            else: s="NO_RETEST_WEAK_LIFT"
            state.append(s)
        q["gap_method"]=method;q["gap_lane_v9"]=lane;q["state_v9"]=state
        out.append(q)
    return pd.concat(out,ignore_index=True),tdf

ap=argparse.ArgumentParser()
ap.add_argument("--anatomy-labels",required=True)
ap.add_argument("--resilience-labels",required=True)
ap.add_argument("--events-dir",required=True)
ap.add_argument("--outdir",required=True)
a=ap.parse_args()
out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

ga=pd.read_csv(a.anatomy_labels,compression="infer")
rr=pd.read_csv(a.resilience_labels,compression="infer")
for q in (ga,rr):
    q["year"]=q.year.astype(int);q["rank_cap"]=q.rank_cap.astype(int)
    for c in ["symbol","signal_date","confirmation_date","entry_date"]: q[c]=q[c].astype(str)
m=ga.merge(rr[KEYS+["rebound_from_low_box","low_progress_box"]],on=KEYS,how="inner",validate="one_to_one")
m["close_lift_box"]=m.rebound_from_low_box-m.low_progress_box

files=sorted(Path(a.events_dir).glob("**/gap_geometry_events_*.csv.gz"))
if len(files)<6: raise RuntimeError(f"expected 6 event shards got {len(files)}")
e=pd.concat([pd.read_csv(f) for f in files],ignore_index=True)
e["year"]=e.year.astype(int);e["rank_cap"]=e.rank_cap.astype(int)
e["close_lift_box"]=e.rebound_from_low_box-e.low_progress_box
x,tdf=classify(e,m)
tdf.to_csv(out/"thresholds_by_year.csv",index=False)

rows=[]
for target in (.60,.80):
  for method in ("EXPANDING","FIXED_-1PCT"):
    z=x[(x.rank_cap==500)&(x.target_fraction==target)&
        (x.gap_method==method)&(x.gap_lane_v9=="EXTREME_GAP")&
        (x.state_v9.isin(["RETEST_LIFT","NO_RETEST_LIFT"]))].copy()
    hist=z[z.year<=2025]
    cur=z[z.year==2026]
    hr=hist.loc[hist.state_v9=="RETEST_LIFT","net_return"].dropna().to_numpy(float)
    hn=hist.loc[hist.state_v9=="NO_RETEST_LIFT","net_return"].dropna().to_numpy(float)
    cr=cur.loc[cur.state_v9=="RETEST_LIFT","net_return"].dropna().to_numpy(float)
    cn=cur.loc[cur.state_v9=="NO_RETEST_LIFT","net_return"].dropna().to_numpy(float)
    if min(len(hr),len(hn),len(cr),len(cn))==0:
        raise RuntimeError("empty required state")
    obs_r=float(cr.mean());obs_n=float(cn.mean());obs_d=obs_r-obs_n
    rng=np.random.default_rng(SEED+int(target*100)+(0 if method=="EXPANDING" else 1))
    sim_r=hr[rng.integers(0,len(hr),size=(DRAWS,len(cr)))].mean(axis=1)
    sim_n=hn[rng.integers(0,len(hn),size=(DRAWS,len(cn)))].mean(axis=1)
    sim_d=sim_r-sim_n
    p_diff=float((sim_d<=obs_d).mean())
    p_r=float((sim_r<=obs_r).mean())
    p_n=float((sim_n>=obs_n).mean())
    if p_r<.05 and p_n<.05: driver="BOTH"
    elif p_r<.05: driver="RETEST_WEAKNESS"
    elif p_n<.05: driver="CONTROL_STRENGTH"
    else: driver="NEITHER"
    rows.append({
      "target_fraction":target,"gap_method":method,
      "hist_retest_n":len(hr),"hist_no_retest_n":len(hn),
      "n_2026_retest":len(cr),"n_2026_no_retest":len(cn),
      "hist_retest_mean":float(hr.mean()),"hist_no_retest_mean":float(hn.mean()),
      "hist_diff":float(hr.mean()-hn.mean()),
      "retest_2026_mean":obs_r,"no_retest_2026_mean":obs_n,"diff_2026":obs_d,
      "p_hist_edge_diff_le_2026":p_diff,
      "p_hist_retest_mean_le_2026":p_r,
      "p_hist_no_retest_mean_ge_2026":p_n,
      "sim_diff_q01":float(np.quantile(sim_d,.01)),
      "sim_diff_q05":float(np.quantile(sim_d,.05)),
      "sim_diff_q50":float(np.quantile(sim_d,.50)),
      "sim_diff_q95":float(np.quantile(sim_d,.95)),
      "driver":driver,
      "significant_decay":bool(p_diff<.05),
    })

rdf=pd.DataFrame(rows)
rdf.to_csv(out/"decay_significance.csv",index=False)
n_sig=int(rdf.significant_decay.sum())
if n_sig==4: verdict="DECAY_EVIDENCE"
elif n_sig>=2: verdict="DECAY_WARNING"
else: verdict="SAMPLE_NOISE_PLAUSIBLE"
summary={
  "schema":"LARGE-GAP-RETEST-RECENT-DECAY-V9",
  "significant_decay_specs":n_sig,
  "total_specs":4,
  "verdict":verdict,
  "checks":rows,
}
(out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
print(json.dumps({k:summary[k] for k in ["schema","significant_decay_specs","total_specs","verdict"]},indent=2))
