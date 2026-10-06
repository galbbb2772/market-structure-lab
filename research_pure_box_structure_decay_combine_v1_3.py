#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd

def bin_ep(v):
    v=int(v)
    return "0" if v<=0 else "1" if v==1 else "2" if v==2 else "3+"

def stats(g):
    g=g[g.history_complete.astype(bool)].copy()
    if g.empty:return {"n":0,"n_fwd10":0,"n_h20":0}
    f10=g[g.fwd10.notna()]
    h=g[g.horizon20_complete.astype(bool)]
    return {
      "n":int(len(g)),
      "n_fwd10":int(len(f10)),
      "n_h20":int(len(h)),
      "mean_fwd5":float(g.fwd5.mean()),
      "median_fwd5":float(g.fwd5.median()),
      "mean_fwd10":float(f10.fwd10.mean()) if len(f10) else None,
      "median_fwd10":float(f10.fwd10.median()) if len(f10) else None,
      "target_rate20":float((h.first_hit20=="target").mean()) if len(h) else None,
      "stop_rate20":float((h.first_hit20=="stop").mean()) if len(h) else None,
      "unresolved_rate20":float((h.first_hit20=="none").mean()) if len(h) else None,
      "mean_mfe20":float(h.mfe20.mean()) if len(h) else None,
      "mean_mae20":float(h.mae20.mean()) if len(h) else None,
      "mean_age":float(g.age_sessions.mean()),
      "mean_width":float(g.box_width_pct.mean()),
    }

def ols(g,ycol,threeplus=False,need_h20=False):
    z=g[g.history_complete.astype(bool)].copy()
    if need_h20:z=z[z.horizon20_complete.astype(bool)]
    z=z[[ycol,"touch_episodes","age_sessions","box_width_pct","scale"]].dropna().copy()
    if len(z)<50:return {"n":int(len(z)),"coef":None}
    if threeplus:
        exposure=(z.touch_episodes>=3).astype(float).to_numpy()
    else:
        exposure=z.touch_episodes.astype(float).to_numpy()
    if len(np.unique(exposure))<2:return {"n":int(len(z)),"coef":None}
    y=z[ycol].to_numpy(float)
    X=np.column_stack([
      np.ones(len(z)),exposure,np.log1p(z.age_sessions.to_numpy(float)),
      z.box_width_pct.to_numpy(float),(z.scale.astype(str)=="large").astype(float).to_numpy()
    ])
    b=np.linalg.lstsq(X,y,rcond=None)[0]
    return {"n":int(len(z)),"coef":float(b[1]),"log_age_coef":float(b[2]),
            "width_coef":float(b[3]),"large_coef":float(b[4])}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True)
    a=ap.parse_args();src=Path(a.indir);out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    files=sorted(src.glob("**/structure_decay_audit_*.csv.gz"))
    if len(files)<8:raise RuntimeError(f"expected 8 shards, got {len(files)}")
    x=pd.concat([pd.read_csv(f) for f in files],ignore_index=True)
    x.signal_date=x.signal_date.astype(str)
    x["period"]=np.where(x.signal_date<="2022-12-31","discovery","validation")
    x["episode_bin"]=x.touch_episodes.map(bin_ep)
    x["stop20"]=(x.first_hit20=="stop").astype(int)

    # Discovery thresholds use complete history only.
    disc=x[(x.period=="discovery")&x.history_complete.astype(bool)]
    thresholds={}
    for scale in ("small","large"):
        g=disc[disc.scale==scale]
        thresholds[scale]={"age_median":float(g.age_sessions.median()),
                           "width_median":float(g.box_width_pct.median())}

    def sleeve_mask(df,name):
        if name=="all":return pd.Series(True,index=df.index)
        age=np.array([thresholds[str(s)]["age_median"] for s in df.scale])
        fresh=df.age_sessions.to_numpy(float)<=age
        if name=="fresh":return pd.Series(fresh,index=df.index)
        width=np.array([thresholds[str(s)]["width_median"] for s in df.scale])
        return pd.Series(fresh & (df.box_width_pct.to_numpy(float)>=width),index=df.index)

    rows=[]; yearly=[]
    regressions={}; cliff={}
    for cap in (300,500):
        regressions[f"top{cap}"]={};cliff[f"top{cap}"]={}
        capdf=x[x.liquidity_rank<=cap]
        for period in ("discovery","validation"):
            regressions[f"top{cap}"][period]={};cliff[f"top{cap}"][period]={}
            pdf=capdf[capdf.period==period]
            for sleeve in ("all","fresh","wide_fresh"):
                z=pdf[sleeve_mask(pdf,sleeve)]
                for ep,g in z.groupby("episode_bin"):
                    rows.append({"rank_cap":cap,"period":period,"sleeve":sleeve,"episode_bin":ep,**stats(g)})
                regressions[f"top{cap}"][period][sleeve]={
                    "linear_touch_fwd10":ols(z,"fwd10",threeplus=False),
                    "cliff3plus_fwd10":ols(z,"fwd10",threeplus=True),
                    "cliff3plus_stop20":ols(z,"stop20",threeplus=True,need_h20=True),
                }
                a3=stats(z[z.touch_episodes>=3]); ref=stats(z[z.touch_episodes<=2])
                cliff[f"top{cap}"][period][sleeve]={"three_plus":a3,"reference_0_2":ref}
        for y in sorted(x.year.unique()):
            yy=capdf[capdf.year==y]
            for sleeve in ("all","fresh","wide_fresh"):
                z=yy[sleeve_mask(yy,sleeve)]
                for ep in ("0","1","2","3+"):
                    yearly.append({"rank_cap":cap,"year":int(y),"sleeve":sleeve,"episode_bin":ep,
                                   **stats(z[z.episode_bin==ep])})

    pd.DataFrame(rows).to_csv(out/"audit_decay_bins.csv",index=False)
    pd.DataFrame(yearly).to_csv(out/"audit_yearly_episode_bins.csv",index=False)
    result={
      "schema":"STRUCTURE-DECAY-V1.3-AUDIT",
      "discovery":"2019-2022","validation":"2023-2026Q1",
      "thresholds_from_complete_history_discovery":thresholds,
      "regressions":regressions,
      "cliff_receipt":cliff,
      "coverage":{
        "total_observations":int(len(x)),
        "history_complete":int(x.history_complete.astype(bool).sum()),
        "horizon20_complete":int(x.horizon20_complete.astype(bool).sum()),
      },
      "notes":[
        "Primary statistics exclude observations without history reaching detected_at.",
        "20-session path statistics exclude right-censored observations.",
        "2019 can remain left-censored because no 2018 artifact is available."
      ]
    }
    (out/"summary.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))
if __name__=="__main__":main()
