#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd

KEYS=["year","rank_cap","symbol","signal_date","confirmation_date","entry_date"]
TEST_YEARS=(2021,2022,2023,2024,2025,2026)
SEED=20261007
BOOT=5000

def pf(rs):
    rs=np.asarray([float(x) for x in rs if pd.notna(x)],float)
    if len(rs)==0: return None
    w=rs[rs>0].sum(); l=-rs[rs<0].sum()
    return float(w/l) if l>0 else None

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
    long=[]
    for method in ("EXPANDING","FIXED_-1PCT"):
        q=events.copy()
        lane=[]; state=[]
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
        q["gap_method"]=method
        q["gap_lane_v8"]=lane
        q["state_v8"]=state
        long.append(q)
    return pd.concat(long,ignore_index=True),tdf

def mean_diff(z, value="net_return"):
    a=z.loc[z.state_v8=="RETEST_LIFT",value].dropna()
    b=z.loc[z.state_v8=="NO_RETEST_LIFT",value].dropna()
    if len(a)==0 or len(b)==0: return np.nan
    return float(a.mean()-b.mean())

def winsor_diff(z):
    vals=z.net_return.dropna()
    lo,hi=vals.quantile([.025,.975])
    q=z.copy()
    q["wr"]=q.net_return.clip(lo,hi)
    return mean_diff(q,"wr"),float(lo),float(hi)

def symbol_balanced_diff(z):
    s=(z[z.state_v8.isin(["RETEST_LIFT","NO_RETEST_LIFT"])]
       .groupby(["symbol","state_v8"],as_index=False).net_return.mean())
    a=s.loc[s.state_v8=="RETEST_LIFT","net_return"]
    b=s.loc[s.state_v8=="NO_RETEST_LIFT","net_return"]
    return float(a.mean()-b.mean()) if len(a) and len(b) else np.nan, int(s.symbol.nunique())

def cluster_bootstrap(z, seed_offset=0):
    q=z[z.state_v8.isin(["RETEST_LIFT","NO_RETEST_LIFT"])].copy()
    syms=np.array(sorted(q.symbol.dropna().astype(str).unique()))
    rng=np.random.default_rng(SEED+seed_offset)
    by={s:q[q.symbol.astype(str)==s] for s in syms}
    diffs=[]
    for _ in range(BOOT):
        draw=rng.choice(syms,size=len(syms),replace=True)
        parts=[by[s] for s in draw]
        b=pd.concat(parts,ignore_index=True)
        d=mean_diff(b)
        if np.isfinite(d): diffs.append(d)
    arr=np.asarray(diffs,float)
    return {
        "bootstrap_draws":int(len(arr)),
        "bootstrap_p_diff_gt_0":float((arr>0).mean()) if len(arr) else np.nan,
        "bootstrap_q05":float(np.quantile(arr,.05)) if len(arr) else np.nan,
        "bootstrap_q50":float(np.quantile(arr,.50)) if len(arr) else np.nan,
        "bootstrap_q95":float(np.quantile(arr,.95)) if len(arr) else np.nan,
    }

ap=argparse.ArgumentParser()
ap.add_argument("--anatomy-labels",required=True)
ap.add_argument("--resilience-labels",required=True)
ap.add_argument("--events-dir",required=True)
ap.add_argument("--outdir",required=True)
a=ap.parse_args()
out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

ga=pd.read_csv(a.anatomy_labels,compression="infer")
rr=pd.read_csv(a.resilience_labels,compression="infer")
for x in (ga,rr):
    x["year"]=x.year.astype(int); x["rank_cap"]=x.rank_cap.astype(int)
    for c in ["symbol","signal_date","confirmation_date","entry_date"]: x[c]=x[c].astype(str)
m=ga.merge(rr[KEYS+["rebound_from_low_box","low_progress_box"]],on=KEYS,how="inner",validate="one_to_one")
m["close_lift_box"]=m.rebound_from_low_box-m.low_progress_box

files=sorted(Path(a.events_dir).glob("**/gap_geometry_events_*.csv.gz"))
if len(files)<6: raise RuntimeError(f"expected 6 event shards got {len(files)}")
e=pd.concat([pd.read_csv(f) for f in files],ignore_index=True)
e["year"]=e.year.astype(int);e["rank_cap"]=e.rank_cap.astype(int)
e["symbol"]=e.symbol.astype(str)
e["close_lift_box"]=e.rebound_from_low_box-e.low_progress_box

x,tdf=classify(e,m)
tdf.to_csv(out/"thresholds_by_year.csv",index=False)

rows=[]
loo_rows=[]
for cap in (300,500):
  for target in (.60,.80):
    for method in ("EXPANDING","FIXED_-1PCT"):
      z=x[(x.rank_cap==cap)&(x.target_fraction==target)&
          (x.gap_method==method)&(x.gap_lane_v8=="EXTREME_GAP")&
          (x.state_v8.isin(["RETEST_LIFT","NO_RETEST_LIFT"]))].copy()
      raw=mean_diff(z)
      wd,lo,hi=winsor_diff(z)
      sbd,nsym=symbol_balanced_diff(z)
      yearly={}
      for yy in TEST_YEARS:
          zy=z[z.year==yy]
          yearly[str(yy)]=mean_diff(zy) if len(zy) else np.nan
      loo={}
      for yy in TEST_YEARS:
          d=mean_diff(z[z.year!=yy])
          loo[str(yy)]=d
          loo_rows.append({"rank_cap":cap,"target_fraction":target,"gap_method":method,
                           "omitted_year":yy,"diff":d})
      finite_year={k:v for k,v in yearly.items() if np.isfinite(v)}
      best_year=max(finite_year,key=finite_year.get) if finite_year else None
      exbest=mean_diff(z[z.year!=int(best_year)]) if best_year is not None else np.nan
      boot=cluster_bootstrap(z,seed_offset=cap*100+int(target*100)+(0 if method=="EXPANDING" else 1))
      a1=z[z.state_v8=="RETEST_LIFT"]; a2=z[z.state_v8=="NO_RETEST_LIFT"]
      minloo=min([v for v in loo.values() if np.isfinite(v)],default=np.nan)
      robust=bool(cap==500 and raw>0 and wd>0 and sbd>0 and minloo>0 and exbest>0 and
                  boot["bootstrap_p_diff_gt_0"]>=.90)
      rows.append({
          "rank_cap":cap,"target_fraction":target,"gap_method":method,
          "retest_n":int(len(a1)),"no_retest_n":int(len(a2)),
          "retest_mean":float(a1.net_return.mean()) if len(a1) else np.nan,
          "no_retest_mean":float(a2.net_return.mean()) if len(a2) else np.nan,
          "retest_pf":pf(a1.net_return),"no_retest_pf":pf(a2.net_return),
          "raw_diff":raw,"winsor_diff":wd,"winsor_lo":lo,"winsor_hi":hi,
          "symbol_balanced_diff":sbd,"n_symbols":nsym,
          "min_leave_one_year_out_diff":minloo,
          "best_year":best_year,"ex_best_year_diff":exbest,
          "yearly_diffs":json.dumps(yearly,sort_keys=True),
          "diff_2026":yearly.get("2026",np.nan),
          **boot,
          "broadly_robust":robust,
      })

rdf=pd.DataFrame(rows)
rdf.to_csv(out/"robustness_checks.csv",index=False)
pd.DataFrame(loo_rows).to_csv(out/"leave_one_year_out.csv",index=False)

top=rdf[rdf.rank_cap==500].copy()
robust_n=int(top.broadly_robust.sum())
recent_n=int((top.diff_2026>0).sum())
if robust_n>=3 and recent_n>=2:
    verdict="PROMOTE_CANDIDATE"
elif robust_n>=3:
    verdict="HISTORICAL_SUPPORT_RECENT_DECAY"
else:
    verdict="DO_NOT_PROMOTE"

summary={
    "schema":"LARGE-GAP-RETEST-ROBUSTNESS-V8",
    "top500_broadly_robust":robust_n,
    "top500_total":int(len(top)),
    "top500_positive_2026":recent_n,
    "verdict":verdict,
    "checks":rows,
}
(out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
print(json.dumps({k:summary[k] for k in ["schema","top500_broadly_robust","top500_total","top500_positive_2026","verdict"]},indent=2))
