#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, statistics
from pathlib import Path
import numpy as np
import pandas as pd

FEATURES=[
 "low_progress_box","rebound_from_low_box","range_ratio",
 "confirmation_clv","volume_ratio20","selloff_5d"
]
TARGETS=("50","60","80","100")
HORIZONS=(10,20,40)

def spearman(a,b):
    z=pd.DataFrame({"a":a,"b":b}).dropna()
    if len(z)<10:return None
    ra=z.a.rank(method="average")
    rb=z.b.rank(method="average")
    v=ra.corr(rb)
    return None if pd.isna(v) else float(v)

def horizon_outcome(g,label,h):
    ev=g[f"t{label}_event"].astype(str)
    day=pd.to_numeric(g[f"t{label}_event_day"],errors="coerce")
    complete=g[f"h{h}_complete"].astype(bool)
    eligible=g[f"t{label}_eligible"].astype(bool)
    usable=eligible & ((day.notna() & (day<=h)) | complete)
    out=pd.Series("censored",index=g.index,dtype=object)
    out.loc[usable]="unresolved"
    out.loc[usable & day.notna() & (day<=h) & (ev=="target")]="target"
    out.loc[usable & day.notna() & (day<=h) & (ev=="stop")]="stop"
    out.loc[~eligible]="ineligible"
    return out

def qcuts(s):
    x=s.dropna().astype(float)
    return [float(x.quantile(q)) for q in (.2,.4,.6,.8)]

def qassign(v,cuts):
    if pd.isna(v):return np.nan
    return int(np.searchsorted(np.array(cuts,float),float(v),side="right")+1)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--indir",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    src=Path(a.indir);out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

    files=sorted(src.glob("**/strategy_reconstruction_*.csv.gz"))
    if len(files)<8:raise RuntimeError(f"expected 8 shards, got {len(files)}")
    x=pd.concat([pd.read_csv(f) for f in files],ignore_index=True)
    x["signal_date"]=x.signal_date.astype(str)
    x["period"]=np.where(x.signal_date<="2022-12-31","discovery","validation")
    x.to_csv(out/"observations.csv.gz",index=False,compression="gzip")

    path_rows=[]
    prog_rows=[]
    for cap in (300,500):
        freshcol=f"fresh_top{cap}"
        capdf=x[(x.liquidity_rank<=cap)&x[freshcol].astype(bool)]
        for period in ("discovery","validation"):
            for stage in ("raw_bottom_signal","confirmed_no_new_low_green"):
                base=capdf[(capdf.period==period)&(capdf.stage==stage)]
                for scale in ("all","small","large"):
                    z=base if scale=="all" else base[base.scale==scale]
                    for h in HORIZONS:
                        usable_prog=z[z[f"h{h}_complete"].astype(bool)]
                        prog_rows.append({
                          "rank_cap":cap,"period":period,"stage":stage,"scale":scale,"horizon":h,
                          "n":int(len(usable_prog)),
                          "mean_mfe_box_progress":float(usable_prog[f"mfe_progress_{h}"].mean()) if len(usable_prog) else None,
                          "median_mfe_box_progress":float(usable_prog[f"mfe_progress_{h}"].median()) if len(usable_prog) else None,
                          "mean_mae_return":float(usable_prog[f"mae_return_{h}"].mean()) if len(usable_prog) else None,
                          "median_mae_return":float(usable_prog[f"mae_return_{h}"].median()) if len(usable_prog) else None,
                        })
                    for label in TARGETS:
                        elig=z[z[f"t{label}_eligible"].astype(bool)].copy()
                        if elig.empty:
                            continue
                        for h in HORIZONS:
                            oc=horizon_outcome(elig,label,h)
                            usable=elig[oc!="censored"]
                            ocu=oc.loc[usable.index]
                            hits=usable[ocu=="target"]
                            hitdays=pd.to_numeric(hits[f"t{label}_event_day"],errors="coerce")
                            path_rows.append({
                              "rank_cap":cap,"period":period,"stage":stage,"scale":scale,
                              "target_fraction":int(label)/100,"horizon":h,
                              "eligible_n":int(len(elig)),"usable_n":int(len(usable)),
                              "target_rate":float((ocu=="target").mean()) if len(usable) else None,
                              "stop_rate":float((ocu=="stop").mean()) if len(usable) else None,
                              "unresolved_rate":float((ocu=="unresolved").mean()) if len(usable) else None,
                              "censored_n":int((oc=="censored").sum()),
                              "median_sessions_to_target":float(hitdays.median()) if len(hitdays) else None,
                              "mean_target_gross_return":float(hits[f"t{label}_target_return"].mean()) if len(hits) else None,
                              "median_target_gross_return":float(hits[f"t{label}_target_return"].median()) if len(hits) else None,
                            })

    pd.DataFrame(path_rows).to_csv(out/"reversion_path_targets.csv",index=False)
    pd.DataFrame(prog_rows).to_csv(out/"reversion_path_progress.csv",index=False)

    quintile_rows=[]
    corr_rows=[]
    thresholds={}
    for cap in (300,500):
        freshcol=f"fresh_top{cap}"
        base=x[(x.liquidity_rank<=cap)&x[freshcol].astype(bool)&
               (x.stage=="confirmed_no_new_low_green")].copy()
        thresholds[f"top{cap}"]={}
        for scale in ("small","large"):
            thresholds[f"top{cap}"][scale]={}
            disc=base[(base.period=="discovery")&(base.scale==scale)]
            for feat in FEATURES:
                cuts=qcuts(disc[feat])
                thresholds[f"top{cap}"][scale][feat]=cuts
                for period in ("discovery","validation"):
                    z=base[(base.period==period)&(base.scale==scale)].copy()
                    z["q"]=z[feat].map(lambda v:qassign(v,cuts))
                    # continuous diagnostics
                    t60=horizon_outcome(z,"60",20)
                    t100=horizon_outcome(z,"100",20)
                    y60=pd.Series(np.nan,index=z.index)
                    y100=pd.Series(np.nan,index=z.index)
                    y60.loc[t60.isin(["target","stop","unresolved"])]=(t60.loc[t60.isin(["target","stop","unresolved"])]=="target").astype(float)
                    y100.loc[t100.isin(["target","stop","unresolved"])]=(t100.loc[t100.isin(["target","stop","unresolved"])]=="target").astype(float)
                    corr_rows.append({
                      "rank_cap":cap,"period":period,"scale":scale,"feature":feat,"n":int(z[feat].notna().sum()),
                      "rho_fwd10":spearman(z[feat],z.fwd10_return),
                      "rho_mfe20":spearman(z[feat],z.mfe_progress_20),
                      "rho_t60_win20":spearman(z[feat],y60),
                      "rho_t100_win20":spearman(z[feat],y100),
                    })
                    for qn in range(1,6):
                        g=z[z.q==qn]
                        if g.empty:continue
                        o60=horizon_outcome(g,"60",20)
                        o100=horizon_outcome(g,"100",20)
                        u60=o60.isin(["target","stop","unresolved"])
                        u100=o100.isin(["target","stop","unresolved"])
                        quintile_rows.append({
                          "rank_cap":cap,"period":period,"scale":scale,"feature":feat,"quintile":qn,
                          "n":int(len(g)),
                          "mean_feature":float(g[feat].mean()),
                          "mean_fwd10":float(g.fwd10_return.mean()),
                          "mean_mfe_progress20":float(g.mfe_progress_20.mean()),
                          "t60_target_rate20":float((o60[u60]=="target").mean()) if u60.any() else None,
                          "t100_target_rate20":float((o100[u100]=="target").mean()) if u100.any() else None,
                          "t60_stop_rate20":float((o60[u60]=="stop").mean()) if u60.any() else None,
                        })

    pd.DataFrame(quintile_rows).to_csv(out/"exhaustion_quintiles.csv",index=False)
    pd.DataFrame(corr_rows).to_csv(out/"exhaustion_correlations.csv",index=False)

    # Compact validation receipt, descriptive only.
    pr=pd.DataFrame(path_rows)
    cr=pd.DataFrame(corr_rows)
    receipt={"schema":"STRATEGY-RECONSTRUCTION-V1",
             "discovery":"2019-2022","validation":"2023-2026Q1",
             "quintile_thresholds":thresholds,
             "validation_highlights":{}}
    for cap in (300,500):
        receipt["validation_highlights"][f"top{cap}"]={}
        for scale in ("small","large"):
            key=f"{scale}"
            receipt["validation_highlights"][f"top{cap}"][key]={}
            p=pr[(pr.rank_cap==cap)&(pr.period=="validation")&
                 (pr.stage=="confirmed_no_new_low_green")&(pr.scale==scale)&
                 (pr.horizon==20)]
            receipt["validation_highlights"][f"top{cap}"][key]["path20"]={
              str(r.target_fraction):{
                "n":int(r.usable_n),"target_rate":float(r.target_rate),
                "stop_rate":float(r.stop_rate),"median_days":None if pd.isna(r.median_sessions_to_target) else float(r.median_sessions_to_target)
              } for r in p.itertuples()
            }
            c=cr[(cr.rank_cap==cap)&(cr.period=="validation")&(cr.scale==scale)]
            receipt["validation_highlights"][f"top{cap}"][key]["feature_correlations"]={
              r.feature:{
                "rho_fwd10":None if pd.isna(r.rho_fwd10) else float(r.rho_fwd10),
                "rho_mfe20":None if pd.isna(r.rho_mfe20) else float(r.rho_mfe20),
                "rho_t60_win20":None if pd.isna(r.rho_t60_win20) else float(r.rho_t60_win20)
              } for r in c.itertuples()
            }

    (out/"summary.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
    print(json.dumps(receipt,indent=2))

if __name__=="__main__":
    main()
