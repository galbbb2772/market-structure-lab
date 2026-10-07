#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd

ap=argparse.ArgumentParser()
ap.add_argument("--indir",required=True)
ap.add_argument("--outdir",required=True)
a=ap.parse_args()
src=Path(a.indir); out=Path(a.outdir); out.mkdir(parents=True,exist_ok=True)

ef=sorted(src.glob("**/gap_geometry_events_*.csv.gz"))
gf=sorted(src.glob("**/gap_geometry_groups_*.csv"))
if len(ef)<6 or len(gf)<6:
    raise RuntimeError(f"expected 6+6 shards got {len(ef)} {len(gf)}")
e=pd.concat([pd.read_csv(f) for f in ef],ignore_index=True)
g=pd.concat([pd.read_csv(f) for f in gf],ignore_index=True)
e.to_csv(out/"annual_events.csv.gz",index=False,compression="gzip")
g.to_csv(out/"annual_group_stats.csv",index=False)

def weighted(gx,col):
    z=gx[[col,"n"]].dropna()
    if z.empty or z.n.sum()<=0:return None
    return float((z[col]*z.n).sum()/z.n.sum())

# Part A: direct geometry audit.
geom=[]
base=g[g.strength.isin(["STRONG","WEAK"])].copy()
for (cap,target,method,feat,strength),z in base.groupby(
    ["rank_cap","target_fraction","gap_method","exhaustion_feature","strength"]
):
    geom.append({
      "rank_cap":int(cap),"target_fraction":float(target),"gap_method":method,
      "exhaustion_feature":feat,"strength":strength,"n":int(z.n.sum()),
      "mean_trade":weighted(z,"mean_trade"),"profit_factor_year_avg":weighted(z,"profit_factor"),
      "mean_entry_fraction":weighted(z,"mean_entry_fraction"),
      "mean_stop_distance":weighted(z,"mean_stop_distance"),
      "mean_target_upside":weighted(z,"mean_target_upside"),
      "mean_rr":weighted(z,"mean_rr"),
    })
geomdf=pd.DataFrame(geom); geomdf.to_csv(out/"geometry_group_summary.csv",index=False)

# Part B: within prior-history entry-fraction quartiles.
strat=[]
for (year,cap,target,method,feat),z in g.groupby(
    ["year","rank_cap","target_fraction","gap_method","exhaustion_feature"]
):
    diffs=[];weights=[];wins=0;used=0
    for q in (1,2,3,4):
        s=z[z.strength==f"Q{q}__STRONG"]
        w=z[z.strength==f"Q{q}__WEAK"]
        if s.empty or w.empty:continue
        sr=s.iloc[0];wr=w.iloc[0]
        wt=min(int(sr.n),int(wr.n))
        if wt<=0:continue
        d=float(sr.mean_trade)-float(wr.mean_trade)
        diffs.append(d);weights.append(wt);used+=1
        wins+=int(d>0)
    if weights:
        d=float(np.average(diffs,weights=weights))
        strat.append({
          "year":int(year),"rank_cap":int(cap),"target_fraction":float(target),
          "gap_method":method,"exhaustion_feature":feat,
          "quartiles_used":used,"matched_weight":int(sum(weights)),
          "standardized_strong_minus_weak":d,
          "strong_better_quartiles":wins
        })
stratdf=pd.DataFrame(strat);stratdf.to_csv(out/"stratified_yearly.csv",index=False)

strat_summary=[]
for (cap,target,method,feat),z in stratdf.groupby(
    ["rank_cap","target_fraction","gap_method","exhaustion_feature"]
):
    w=z.matched_weight.astype(float)
    agg=float(np.average(z.standardized_strong_minus_weak,weights=w))
    strat_summary.append({
      "rank_cap":int(cap),"target_fraction":float(target),"gap_method":method,
      "exhaustion_feature":feat,"years":int(len(z)),
      "aggregate_standardized_diff":agg,
      "strong_better_years":int((z.standardized_strong_minus_weak>0).sum()),
      "strong_worse_years":int((z.standardized_strong_minus_weak<0).sum()),
      "yearly_diff":json.dumps({str(int(r.year)):float(r.standardized_strong_minus_weak) for r in z.itertuples()},sort_keys=True)
    })
ss=pd.DataFrame(strat_summary);ss.to_csv(out/"stratified_summary.csv",index=False)

# Part C: residual geometry control.
regs=[]
for cap in (300,500):
  for target in (.60,.80):
    for method,gcol in [("EXPANDING","gap_expanding_lane"),("FIXED_-1PCT","gap_fixed_lane")]:
      for feat,scol in [("rebound_from_low_box","rebound_strength"),("low_progress_box","lowprog_strength")]:
        z=e[(e.rank_cap==cap)&(e.target_fraction==target)&(e[gcol]=="EXTREME_GAP")].copy()
        z=z.dropna(subset=["net_return","entry_fraction","gap_component",scol])
        if len(z)<30:continue
        years=sorted(z.year.astype(int).unique())
        cols=[np.ones(len(z)),z.entry_fraction.to_numpy(float),z.gap_component.to_numpy(float)]
        names=["intercept","entry_fraction","gap_component"]
        for yy in years[1:]:
            cols.append((z.year.astype(int).to_numpy()==yy).astype(float));names.append(f"year_{yy}")
        cols.append((z[scol].astype(str).to_numpy()=="STRONG").astype(float));names.append("STRONG")
        X=np.column_stack(cols); y=z.net_return.to_numpy(float)
        beta=np.linalg.lstsq(X,y,rcond=None)[0]
        b=dict(zip(names,beta))
        regs.append({
          "rank_cap":cap,"target_fraction":target,"gap_method":method,
          "exhaustion_feature":feat,"n":int(len(z)),
          "coef_STRONG":float(b["STRONG"]),
          "coef_entry_fraction":float(b["entry_fraction"]),
          "coef_gap_component":float(b["gap_component"]),
        })
regdf=pd.DataFrame(regs);regdf.to_csv(out/"residual_control.csv",index=False)

checks=[]
for r in ss.to_dict("records"):
    z=regdf[(regdf.rank_cap==r["rank_cap"])&
            (regdf.target_fraction==r["target_fraction"])&
            (regdf.gap_method==r["gap_method"])&
            (regdf.exhaustion_feature==r["exhaustion_feature"])]
    if z.empty:continue
    rr=z.iloc[0]
    # V5 negative effect survives geometry control if both standardized and regression effects remain negative,
    # and at least 4 of 6 yearly standardized effects are negative.
    survives=bool(r["aggregate_standardized_diff"]<0 and
                  int(r["strong_worse_years"])>=4 and
                  float(rr.coef_STRONG)<0)
    checks.append({**r,
      "regression_coef_STRONG":float(rr.coef_STRONG),
      "regression_coef_entry_fraction":float(rr.coef_entry_fraction),
      "regression_coef_gap_component":float(rr.coef_gap_component),
      "negative_effect_survives_geometry_control":survives
    })
cdf=pd.DataFrame(checks);cdf.to_csv(out/"support_checks.csv",index=False)

summary={
 "schema":"LARGE-GAP-GEOMETRY-CONTROL-V6",
 "survived_checks":int(cdf.negative_effect_survives_geometry_control.sum()),
 "total_checks":int(len(cdf)),
 "by_feature":{
   feat:{
     "survived":int(cdf[cdf.exhaustion_feature==feat].negative_effect_survives_geometry_control.sum()),
     "total":int((cdf.exhaustion_feature==feat).sum())
   } for feat in sorted(cdf.exhaustion_feature.unique())
 },
 "checks":checks
}
(out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
print(json.dumps({k:summary[k] for k in ("schema","survived_checks","total_checks","by_feature")},indent=2))
