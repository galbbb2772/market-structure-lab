#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math
from pathlib import Path
import numpy as np
import pandas as pd

def pf_from_hits(g):
    return None

def bin_ep(v):
    v=int(v)
    return "0" if v<=0 else "1" if v==1 else "2" if v==2 else "3+"
def bin_touch10(v):
    v=int(v)
    return "0" if v<=0 else "1" if v==1 else "2" if v==2 else "3+"
def bin_streak(v):
    v=int(v)
    return "1" if v<=1 else "2" if v==2 else "3+"
def bin_accel(v):
    v=float(v)
    return "<=0" if v<=0 else "+1" if v==1 else "+2+"

def stats(g):
    if g.empty:return {"n":0}
    return {
      "n":int(len(g)),
      "mean_fwd5":float(g["fwd5"].mean()),
      "median_fwd5":float(g["fwd5"].median()),
      "mean_fwd10":float(g["fwd10"].mean()),
      "median_fwd10":float(g["fwd10"].median()),
      "target_rate20":float((g["first_hit20"]=="target").mean()),
      "stop_rate20":float((g["first_hit20"]=="stop").mean()),
      "unresolved_rate20":float((g["first_hit20"]=="none").mean()),
      "mean_mfe20":float(g["mfe20"].mean()),
      "mean_mae20":float(g["mae20"].mean()),
      "mean_age":float(g["age_sessions"].mean()),
      "mean_width":float(g["box_width_pct"].mean()),
    }

def ols_touch(g):
    z=g[["fwd10","touch_episodes","age_sessions","box_width_pct","scale"]].dropna().copy()
    if len(z)<50:return {"n":int(len(z)),"touch_episode_coef":None}
    y=z["fwd10"].to_numpy(float)
    X=np.column_stack([
        np.ones(len(z)),
        z["touch_episodes"].to_numpy(float),
        np.log1p(z["age_sessions"].to_numpy(float)),
        z["box_width_pct"].to_numpy(float),
        (z["scale"].astype(str)=="large").astype(float).to_numpy(),
    ])
    beta=np.linalg.lstsq(X,y,rcond=None)[0]
    return {"n":int(len(z)),"touch_episode_coef":float(beta[1]),
            "log_age_coef":float(beta[2]),"width_coef":float(beta[3]),"large_coef":float(beta[4])}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True)
    a=ap.parse_args();src=Path(a.indir);out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    files=sorted(src.glob("**/structure_decay_*.csv.gz"))
    if len(files)<8: raise RuntimeError(f"expected 8 yearly shards, got {len(files)}")
    x=pd.concat([pd.read_csv(f) for f in files],ignore_index=True)
    x["signal_date"]=x["signal_date"].astype(str)
    x["period"]=np.where(x["signal_date"]<="2022-12-31","discovery","validation")

    disc=x[x.period=="discovery"]
    thresholds={}
    for scale in ("small","large"):
        g=disc[disc.scale==scale]
        thresholds[scale]={
          "age_median":float(g.age_sessions.median()),
          "width_median":float(g.box_width_pct.median())
        }

    def sleeve_mask(df,name):
        if name=="all":return pd.Series(True,index=df.index)
        age=np.array([thresholds[str(s)]["age_median"] for s in df.scale])
        fresh=df.age_sessions.to_numpy(float)<=age
        if name=="fresh":return pd.Series(fresh,index=df.index)
        width=np.array([thresholds[str(s)]["width_median"] for s in df.scale])
        return pd.Series(fresh & (df.box_width_pct.to_numpy(float)>=width),index=df.index)

    x["episode_bin"]=x.touch_episodes.map(bin_ep)
    x["touch10_bin"]=x.touch_last10.map(bin_touch10)
    x["streak_bin"]=x.bottom_streak.map(bin_streak)
    x["accel_bin"]=x.touch_accel10.map(bin_accel)

    rows=[]
    dims=[("episode","episode_bin"),("touch_last10","touch10_bin"),("bottom_streak","streak_bin"),("touch_accel10","accel_bin")]
    for cap in (300,500):
      capdf=x[x.liquidity_rank<=cap]
      for period in ("discovery","validation"):
        pdf=capdf[capdf.period==period]
        for sleeve in ("all","fresh","wide_fresh"):
          sdf=pdf[sleeve_mask(pdf,sleeve)]
          for scale in ("all","small","large"):
            z=sdf if scale=="all" else sdf[sdf.scale==scale]
            for dim,col in dims:
              for level,g in z.groupby(col,dropna=False):
                rows.append({"rank_cap":cap,"period":period,"sleeve":sleeve,"scale":scale,
                             "dimension":dim,"level":str(level),**stats(g)})
    summary_df=pd.DataFrame(rows)
    summary_df.to_csv(out/"decay_bins.csv",index=False)

    yearly=[]
    for cap in (300,500):
      capdf=x[x.liquidity_rank<=cap]
      for y in sorted(x.year.unique()):
        yy=capdf[capdf.year==y]
        for sleeve in ("all","fresh","wide_fresh"):
          z=yy[sleeve_mask(yy,sleeve)]
          for ep in ("0","1","2","3+"):
            g=z[z.episode_bin==ep]
            yearly.append({"rank_cap":cap,"year":int(y),"sleeve":sleeve,"episode_bin":ep,**stats(g)})
    pd.DataFrame(yearly).to_csv(out/"yearly_episode_bins.csv",index=False)

    regressions={}
    for cap in (300,500):
      regressions[f"top{cap}"]={}
      for period in ("discovery","validation"):
        pdf=x[(x.liquidity_rank<=cap)&(x.period==period)]
        regressions[f"top{cap}"][period]={}
        for sleeve in ("all","fresh","wide_fresh"):
          z=pdf[sleeve_mask(pdf,sleeve)]
          regressions[f"top{cap}"][period][sleeve]=ols_touch(z)

    # compact validation receipt for episode monotonicity / tail damage
    receipt={}
    for cap in (300,500):
      receipt[f"top{cap}"]={}
      for sleeve in ("all","fresh","wide_fresh"):
        z=x[(x.liquidity_rank<=cap)&(x.period=="validation")]
        z=z[sleeve_mask(z,sleeve)]
        levels={}
        for ep in ("0","1","2","3+"):
          levels[ep]=stats(z[z.episode_bin==ep])
        receipt[f"top{cap}"][sleeve]=levels

    result={
      "schema":"STRUCTURE-DECAY-V1",
      "discovery":"2019-2022",
      "validation":"2023-2026Q1",
      "thresholds_from_discovery":thresholds,
      "regressions":regressions,
      "validation_episode_receipt":receipt,
      "warnings":[
        "V1 is diagnostic only; no production promotion.",
        "Source universe is the causal high-liquidity proxy from Pure Box Liquid Leaders V1 and is not a perfect PIT common-stock master.",
        "Touch threshold is preregistered at lower 12% of box width; V1 does not optimize it."
      ]
    }
    (out/"summary.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    x.to_csv(out/"episode_observations.csv.gz",index=False,compression="gzip")
    print(json.dumps(result,indent=2))

if __name__=="__main__":main()
