#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd

FEATURES=("idio_dislocation_5d","idio_dislocation_20d")
TARGETS=(0.60,0.80)
FRESH={300:23,500:24}

def qcuts(s):
    x=pd.to_numeric(s,errors="coerce").dropna()
    if len(x)<20:return None
    return [float(x.quantile(q)) for q in (.2,.4,.6,.8)]

def qassign(v,cuts):
    if cuts is None or pd.isna(v):return np.nan
    return int(np.searchsorted(np.asarray(cuts,float),float(v),side="right")+1)

def spearman(a,b):
    z=pd.DataFrame({"a":pd.to_numeric(a,errors="coerce"),"b":pd.to_numeric(b,errors="coerce")}).dropna()
    if len(z)<20:return None
    v=z.a.rank(method="average").corr(z.b.rank(method="average"))
    return None if pd.isna(v) else float(v)

def pf(rs):
    x=pd.to_numeric(rs,errors="coerce").dropna()
    gp=float(x[x>0].sum());gl=float(-x[x<0].sum())
    return gp/gl if gl>0 else None

def summarize(g):
    if g.empty:return None
    reasons=g.exit_reason.astype(str)
    return {
      "n":int(len(g)),
      "mean_feature":None,
      "mean_trade":float(g.net_return.mean()),
      "median_trade":float(g.net_return.median()),
      "profit_factor":pf(g.net_return),
      "win_rate":float((g.net_return>0).mean()),
      "target_share":float(reasons.isin(["target","target_gap"]).mean()),
      "stop_share":float(reasons.isin(["stop","stop_gap"]).mean()),
      "max_hold_share":float(reasons.str.startswith("max_hold").mean()),
      "mean_holding_sessions":float(g.holding_sessions.mean()),
      "mean_mfe_return":float(g.mfe_return.mean()),
      "mean_mae_return":float(g.mae_return.mean()),
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--indir",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    src=Path(a.indir);out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

    files=sorted(src.glob("**/idio_dislocation_*.csv.gz"))
    if len(files)<8:raise RuntimeError(f"expected 8 yearly shards, got {len(files)}")
    x=pd.concat([pd.read_csv(f) for f in files],ignore_index=True)
    x["period"]=np.where(x.year.astype(int)<=2022,"discovery","validation")
    x.to_csv(out/"observations.csv.gz",index=False,compression="gzip")

    qrows=[];crows=[];thresholds={}
    for cap in (300,500):
      thresholds[f"top{cap}"]={}
      base=x[(x.liquidity_rank<=cap)&(x.box_age_sessions<=FRESH[cap])].copy()
      for target in TARGETS:
        bt=base[base.target_fraction==target].copy()
        for feat in FEATURES:
          disc=bt[bt.period=="discovery"]
          cuts=qcuts(disc[feat])
          thresholds[f"top{cap}"][f"t{int(target*100)}_{feat}"]=cuts
          for period in ("discovery","validation"):
            z=bt[bt.period==period].copy()
            z["q"]=z[feat].map(lambda v:qassign(v,cuts))
            target_y=z.exit_reason.astype(str).isin(["target","target_gap"]).astype(float)
            stop_y=z.exit_reason.astype(str).isin(["stop","stop_gap"]).astype(float)
            crows.append({
              "rank_cap":cap,"target_fraction":target,"period":period,"feature":feat,
              "n":int(z[feat].notna().sum()),
              "rho_net_return":spearman(z[feat],z.net_return),
              "rho_target":spearman(z[feat],target_y),
              "rho_stop":spearman(z[feat],stop_y),
              "rho_mfe":spearman(z[feat],z.mfe_return),
              "rho_mae":spearman(z[feat],z.mae_return),
            })
            for q in range(1,6):
              g=z[z.q==q]
              if g.empty:continue
              s=summarize(g)
              s["mean_feature"]=float(g[feat].mean())
              s.update({
                "rank_cap":cap,"target_fraction":target,"period":period,
                "feature":feat,"quintile":q,
                "yearly_mean_trade":{
                  str(int(y)):float(gg.net_return.mean())
                  for y,gg in g.groupby("year")
                },
                "yearly_n":{
                  str(int(y)):int(len(gg))
                  for y,gg in g.groupby("year")
                },
              })
              qrows.append(s)

    qdf=pd.DataFrame(qrows)
    cdf=pd.DataFrame(crows)
    qdf.to_csv(out/"quintile_summary.csv",index=False)
    cdf.to_csv(out/"correlations.csv",index=False)

    # Compact endpoint/monotonicity diagnostics.
    screen=[]
    for (cap,target,feat,period),g in qdf.groupby(
      ["rank_cap","target_fraction","feature","period"]
    ):
      q1=g[g.quintile==1];q5=g[g.quintile==5]
      if q1.empty or q5.empty:continue
      qm=g.sort_values("quintile")
      screen.append({
        "rank_cap":int(cap),"target_fraction":float(target),"feature":feat,"period":period,
        "q1_n":int(q1.iloc[0].n),"q5_n":int(q5.iloc[0].n),
        "q1_mean_trade":float(q1.iloc[0].mean_trade),
        "q5_mean_trade":float(q5.iloc[0].mean_trade),
        "q1_pf":None if pd.isna(q1.iloc[0].profit_factor) else float(q1.iloc[0].profit_factor),
        "q5_pf":None if pd.isna(q5.iloc[0].profit_factor) else float(q5.iloc[0].profit_factor),
        "q1_target_share":float(q1.iloc[0].target_share),
        "q5_target_share":float(q5.iloc[0].target_share),
        "q1_stop_share":float(q1.iloc[0].stop_share),
        "q5_stop_share":float(q5.iloc[0].stop_share),
        "q1_mfe":float(q1.iloc[0].mean_mfe_return),
        "q5_mfe":float(q5.iloc[0].mean_mfe_return),
        "quintile_rho_mean_trade":spearman(qm.quintile,qm.mean_trade),
        "quintile_rho_target_share":spearman(qm.quintile,qm.target_share),
        "quintile_rho_stop_share":spearman(qm.quintile,qm.stop_share),
      })
    sdf=pd.DataFrame(screen)
    sdf.to_csv(out/"mechanism_screen.csv",index=False)

    summary={
      "schema":"LARGE-IDIO-DISLOCATION-V1",
      "discovery":"2019-2022","validation":"2023-2026Q1",
      "features":list(FEATURES),
      "thresholds":thresholds,
      "screens":{}
    }
    for cap in (300,500):
      summary["screens"][f"top{cap}"]={}
      for target in TARGETS:
        tk=f"t{int(target*100)}"
        summary["screens"][f"top{cap}"][tk]={}
        for feat in FEATURES:
          item={}
          for period in ("discovery","validation"):
            z=sdf[(sdf.rank_cap==cap)&(sdf.target_fraction==target)&
                  (sdf.feature==feat)&(sdf.period==period)]
            cc=cdf[(cdf.rank_cap==cap)&(cdf.target_fraction==target)&
                   (cdf.feature==feat)&(cdf.period==period)]
            if len(z):
              rr=z.iloc[0]
              item[period]={
                "q1_n":int(rr.q1_n),"q5_n":int(rr.q5_n),
                "q1_mean_trade":float(rr.q1_mean_trade),
                "q5_mean_trade":float(rr.q5_mean_trade),
                "q1_pf":None if pd.isna(rr.q1_pf) else float(rr.q1_pf),
                "q5_pf":None if pd.isna(rr.q5_pf) else float(rr.q5_pf),
                "q1_target_share":float(rr.q1_target_share),
                "q5_target_share":float(rr.q5_target_share),
                "q1_stop_share":float(rr.q1_stop_share),
                "q5_stop_share":float(rr.q5_stop_share),
                "q1_mfe":float(rr.q1_mfe),"q5_mfe":float(rr.q5_mfe),
                "rho_net_return":None if cc.empty or pd.isna(cc.iloc[0].rho_net_return) else float(cc.iloc[0].rho_net_return),
                "rho_target":None if cc.empty or pd.isna(cc.iloc[0].rho_target) else float(cc.iloc[0].rho_target),
                "rho_stop":None if cc.empty or pd.isna(cc.iloc[0].rho_stop) else float(cc.iloc[0].rho_stop),
                "rho_mfe":None if cc.empty or pd.isna(cc.iloc[0].rho_mfe) else float(cc.iloc[0].rho_mfe),
              }
          summary["screens"][f"top{cap}"][tk][feat]=item

    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))

if __name__=="__main__":
    main()
