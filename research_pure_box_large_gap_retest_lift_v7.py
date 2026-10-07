#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd

KEYS=["year","rank_cap","symbol","signal_date","confirmation_date","entry_date"]
TEST_YEARS=(2021,2022,2023,2024,2025,2026)

def pf(rs):
    rs=[float(x) for x in rs if pd.notna(x)]
    w=sum(x for x in rs if x>0); l=-sum(x for x in rs if x<0)
    return w/l if l>0 else None

def zscore(x):
    x=np.asarray(x,float); sd=np.nanstd(x,ddof=0)
    return np.zeros(len(x)) if sd<=1e-12 else (x-np.nanmean(x))/sd

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
    x["year"]=x.year.astype(int);x["rank_cap"]=x.rank_cap.astype(int)
    for c in ["symbol","signal_date","confirmation_date","entry_date"]:
        x[c]=x[c].astype(str)
m=ga.merge(rr[KEYS+["rebound_from_low_box","low_progress_box"]],on=KEYS,how="inner",validate="one_to_one")
m["close_lift_box"]=m.rebound_from_low_box-m.low_progress_box

# Freeze expanding thresholds strictly from prior years.
thr=[]
for cap in (300,500):
    z=m[m.rank_cap==cap]
    for year in TEST_YEARS:
        hist=z[z.year<year].copy()
        gapq=float(hist.gap_component.dropna().quantile(.20))
        for method in ("EXPANDING","FIXED_-1PCT"):
            he=hist[hist.gap_component<=gapq] if method=="EXPANDING" else hist[hist.gap_component<=-.01]
            thr.append({
              "rank_cap":cap,"year":year,"gap_method":method,
              "gap_threshold":gapq if method=="EXPANDING" else -.01,
              "history_extreme_n":int(len(he)),
              "lowprog_median":float(he.low_progress_box.dropna().median()),
              "close_lift_median":float(he.close_lift_box.dropna().median()),
            })
tdf=pd.DataFrame(thr);tdf.to_csv(out/"thresholds_by_year.csv",index=False)
tmap={(int(r.rank_cap),int(r.year),r.gap_method):r for r in tdf.itertuples()}

files=sorted(Path(a.events_dir).glob("**/gap_geometry_events_*.csv.gz"))
if len(files)<6: raise RuntimeError(f"expected 6 event shards got {len(files)}")
e=pd.concat([pd.read_csv(f) for f in files],ignore_index=True)
e["year"]=e.year.astype(int);e["rank_cap"]=e.rank_cap.astype(int)
e["close_lift_box"]=e.rebound_from_low_box-e.low_progress_box

# Assign two method-specific retest/lift states.
long=[]
for method in ("EXPANDING","FIXED_-1PCT"):
    q=e.copy()
    gaplane=[];state=[]
    for r in q.itertuples():
        t=tmap[(int(r.rank_cap),int(r.year),method)]
        extreme=float(r.gap_component)<=float(t.gap_threshold)
        gaplane.append("EXTREME_GAP" if extreme else "NON_EXTREME")
        if not extreme:
            state.append(None);continue
        retest=float(r.low_progress_box)<=float(t.lowprog_median)
        lift=float(r.close_lift_box)>float(t.close_lift_median)
        if retest and lift:s="RETEST_LIFT"
        elif retest and not lift:s="RETEST_WEAK_LIFT"
        elif (not retest) and lift:s="NO_RETEST_LIFT"
        else:s="NO_RETEST_WEAK_LIFT"
        state.append(s)
    q["gap_method"]=method;q["gap_lane_v7"]=gaplane;q["state_v7"]=state
    long.append(q)
x=pd.concat(long,ignore_index=True)
x[x.gap_lane_v7=="EXTREME_GAP"].to_csv(out/"extreme_gap_events_v7.csv.gz",index=False,compression="gzip")

# Continuous joint model.
regs=[]
for cap in (300,500):
  for target in (.60,.80):
    for method in ("EXPANDING","FIXED_-1PCT"):
      z=x[(x.rank_cap==cap)&(x.target_fraction==target)&
          (x.gap_method==method)&(x.gap_lane_v7=="EXTREME_GAP")].copy()
      z=z.dropna(subset=["net_return","low_progress_box","close_lift_box","entry_fraction","gap_component"])
      years=sorted(z.year.unique())
      cols=[
        np.ones(len(z)),
        zscore(z.low_progress_box),
        zscore(z.close_lift_box),
        zscore(z.entry_fraction),
        zscore(z.gap_component),
      ]
      names=["intercept","z_low_progress","z_close_lift","z_entry_fraction","z_gap_component"]
      for yy in years[1:]:
        cols.append((z.year.to_numpy()==yy).astype(float));names.append(f"year_{yy}")
      X=np.column_stack(cols);y=z.net_return.to_numpy(float)
      beta=np.linalg.lstsq(X,y,rcond=None)[0]
      b=dict(zip(names,beta))
      regs.append({
        "rank_cap":cap,"target_fraction":target,"gap_method":method,"n":len(z),
        "coef_low_progress":float(b["z_low_progress"]),
        "coef_close_lift":float(b["z_close_lift"]),
        "coef_entry_fraction":float(b["z_entry_fraction"]),
        "coef_gap_component":float(b["z_gap_component"]),
        "condition_number":float(np.linalg.cond(X)),
      })
regdf=pd.DataFrame(regs);regdf.to_csv(out/"joint_residual_control.csv",index=False)

# 2x2 event state map by year and aggregate.
yr=[]
ex=x[x.gap_lane_v7=="EXTREME_GAP"].dropna(subset=["state_v7"]).copy()
for (cap,target,method,year,state),g in ex.groupby(
    ["rank_cap","target_fraction","gap_method","year","state_v7"]
):
    reasons=g.exit_reason.astype(str)
    yr.append({
      "rank_cap":int(cap),"target_fraction":float(target),"gap_method":method,
      "year":int(year),"state":state,"n":len(g),
      "mean_trade":float(g.net_return.mean()),"profit_factor":pf(g.net_return),
      "target_share":float(reasons.isin(["target","target_gap"]).mean()),
      "stop_share":float(reasons.isin(["stop","stop_gap"]).mean()),
      "mean_mfe_return":float(g.mfe_return.mean()),"mean_mae_return":float(g.mae_return.mean()),
    })
yrdf=pd.DataFrame(yr);yrdf.to_csv(out/"state_yearly.csv",index=False)

agg=[]
for (cap,target,method,state),g in ex.groupby(
    ["rank_cap","target_fraction","gap_method","state_v7"]
):
    reasons=g.exit_reason.astype(str)
    agg.append({
      "rank_cap":int(cap),"target_fraction":float(target),"gap_method":method,
      "state":state,"n":len(g),"mean_trade":float(g.net_return.mean()),
      "profit_factor":pf(g.net_return),
      "target_share":float(reasons.isin(["target","target_gap"]).mean()),
      "stop_share":float(reasons.isin(["stop","stop_gap"]).mean()),
      "mean_mfe_return":float(g.mfe_return.mean()),"mean_mae_return":float(g.mae_return.mean()),
    })
aggdf=pd.DataFrame(agg);aggdf.to_csv(out/"state_summary.csv",index=False)

def row(df,cap,target,method,state):
    z=df[(df.rank_cap==cap)&(df.target_fraction==target)&(df.gap_method==method)&(df.state==state)]
    return None if z.empty else z.iloc[0]

checks=[]
for cap in (300,500):
  for target in (.60,.80):
    for method in ("EXPANDING","FIXED_-1PCT"):
      a1=row(aggdf,cap,target,method,"RETEST_LIFT")
      a2=row(aggdf,cap,target,method,"NO_RETEST_LIFT")
      a3=row(aggdf,cap,target,method,"RETEST_WEAK_LIFT")
      reg=regdf[(regdf.rank_cap==cap)&(regdf.target_fraction==target)&(regdf.gap_method==method)].iloc[0]
      if a1 is None or a2 is None or a3 is None:continue
      yearly=[]
      for yy in TEST_YEARS:
        r1=row(yrdf[yrdf.year==yy],cap,target,method,"RETEST_LIFT")
        r2=row(yrdf[yrdf.year==yy],cap,target,method,"NO_RETEST_LIFT")
        if r1 is not None and r2 is not None:
            yearly.append((yy,float(r1.mean_trade)-float(r2.mean_trade)))
      retest_better=sum(d>0 for _,d in yearly)
      primary=bool(float(reg.coef_low_progress)<0 and
                   float(a1.mean_trade)>float(a2.mean_trade) and
                   float(a1.profit_factor)>float(a2.profit_factor) and
                   retest_better>=4)
      checks.append({
        "rank_cap":cap,"target_fraction":target,"gap_method":method,
        "coef_low_progress":float(reg.coef_low_progress),
        "coef_close_lift":float(reg.coef_close_lift),
        "coef_entry_fraction":float(reg.coef_entry_fraction),
        "coef_gap_component":float(reg.coef_gap_component),
        "retest_lift_n":int(a1.n),"no_retest_lift_n":int(a2.n),
        "retest_lift_mean":float(a1.mean_trade),"no_retest_lift_mean":float(a2.mean_trade),
        "retest_lift_pf":float(a1.profit_factor),"no_retest_lift_pf":float(a2.profit_factor),
        "retest_better_years":retest_better,"yearly_diffs":json.dumps({str(y):d for y,d in yearly},sort_keys=True),
        "retest_weak_lift_mean":float(a3.mean_trade),"retest_weak_lift_pf":float(a3.profit_factor),
        "lift_helped_within_retest":bool(float(a1.mean_trade)>float(a3.mean_trade) and float(a1.profit_factor)>float(a3.profit_factor)),
        "primary_retest_support":primary,
      })
cdf=pd.DataFrame(checks);cdf.to_csv(out/"support_checks.csv",index=False)
top500=cdf[cdf.rank_cap==500]
summary={
  "schema":"LARGE-GAP-RETEST-LIFT-V7",
  "top500_low_progress_negative":int((top500.coef_low_progress<0).sum()),
  "top500_total":int(len(top500)),
  "top500_primary_support":int(top500.primary_retest_support.sum()),
  "all_primary_support":int(cdf.primary_retest_support.sum()),
  "all_total":int(len(cdf)),
  "checks":checks,
}
(out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
print(json.dumps({k:summary[k] for k in ["schema","top500_low_progress_negative","top500_total","top500_primary_support","all_primary_support","all_total"]},indent=2))
