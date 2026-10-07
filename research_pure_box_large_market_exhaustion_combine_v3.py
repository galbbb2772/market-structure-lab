#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd

FEATURES=[
 "pct_up_1d",
 "new_low_relief_1d",
 "new_low_relief_3d",
 "ma50_recovery_3d",
 "ret20_recovery_3d",
 "median_ret20_recovery_3d",
]

def qcuts(s):
    x=pd.to_numeric(s,errors="coerce").dropna()
    return [float(x.quantile(q)) for q in (.2,.4,.6,.8)]

def qassign(v,cuts):
    if pd.isna(v): return np.nan
    return int(np.searchsorted(np.asarray(cuts,float),float(v),side="right")+1)

def pf(rs):
    rs=[float(x) for x in rs if pd.notna(x)]
    w=sum(x for x in rs if x>0);l=-sum(x for x in rs if x<0)
    return w/l if l>0 else None

def spearman(a,b):
    z=pd.DataFrame({"a":a,"b":b}).dropna()
    if len(z)<10:return None
    v=z.a.rank(method="average").corr(z.b.rank(method="average"))
    return None if pd.isna(v) else float(v)

ap=argparse.ArgumentParser()
ap.add_argument("--indir",required=True)
ap.add_argument("--outdir",required=True)
a=ap.parse_args()
src=Path(a.indir);out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

cfiles=sorted(src.glob("**/candidates_*.csv.gz"))
efiles=sorted(src.glob("**/events_*.csv.gz"))
if len(cfiles)<16 or len(efiles)<32:
    raise RuntimeError(f"expected >=16 candidate and >=32 event shards, got {len(cfiles)} {len(efiles)}")

cand=pd.concat([pd.read_csv(f) for f in cfiles],ignore_index=True)
events=pd.concat([pd.read_csv(f) for f in efiles],ignore_index=True)
cand["year"]=cand.year.astype(int)
events["year"]=events.year.astype(int)
cand["period"]=np.where(cand.year<=2022,"discovery","validation")
events["period"]=np.where(events.year<=2022,"discovery","validation")

thresholds={}
for cap in (300,500):
    thresholds[f"top{cap}"]={}
    d=cand[(cand.rank_cap==cap)&(cand.period=="discovery")]
    for feat in FEATURES:
        cuts=qcuts(d[feat])
        thresholds[f"top{cap}"][feat]=cuts
        mask=cand.rank_cap==cap
        cand.loc[mask,f"q__{feat}"]=cand.loc[mask,feat].map(lambda v:qassign(v,cuts))
        emask=events.rank_cap==cap
        events.loc[emask,f"q__{feat}"]=events.loc[emask,feat].map(lambda v:qassign(v,cuts))

(out/"thresholds.json").write_text(json.dumps(thresholds,indent=2),encoding="utf-8")
cand.to_csv(out/"labeled_candidates.csv.gz",index=False,compression="gzip")

qrows=[];crows=[]
for cap in (300,500):
    for target in (.60,.80):
        base=events[(events.rank_cap==cap)&(events.target_fraction==target)]
        for feat in FEATURES:
            for period in ("discovery","validation"):
                z=base[base.period==period].copy()
                yy_target=z.exit_reason.astype(str).isin(["target","target_gap"]).astype(float)
                yy_stop=z.exit_reason.astype(str).isin(["stop","stop_gap"]).astype(float)
                crows.append({
                  "rank_cap":cap,"target_fraction":target,"feature":feat,"period":period,
                  "n":int(z[feat].notna().sum()),
                  "rho_return":spearman(z[feat],z.net_return),
                  "rho_target":spearman(z[feat],yy_target),
                  "rho_stop":spearman(z[feat],yy_stop),
                })
                qcol=f"q__{feat}"
                for q in range(1,6):
                    g=z[z[qcol]==q].copy()
                    if g.empty:continue
                    rs=g.net_return.astype(float).tolist()
                    reasons=g.exit_reason.astype(str)
                    qrows.append({
                      "rank_cap":cap,"target_fraction":target,"feature":feat,"period":period,
                      "quintile":q,"n":int(len(g)),
                      "mean_feature":float(g[feat].mean()),
                      "mean_trade":float(g.net_return.mean()),
                      "median_trade":float(g.net_return.median()),
                      "profit_factor":pf(rs),
                      "win_rate":float((g.net_return>0).mean()),
                      "target_share":float(reasons.isin(["target","target_gap"]).mean()),
                      "stop_share":float(reasons.isin(["stop","stop_gap"]).mean()),
                      "max_hold_share":float(reasons.str.startswith("max_hold").mean()),
                      "mean_holding_sessions":float(g.holding_sessions.mean()),
                      "mean_mfe_return":float(g.mfe_return.mean()),
                      "mean_mae_return":float(g.mae_return.mean()),
                      "yearly_mean_trade":json.dumps({
                        str(int(y)):float(gg.net_return.mean()) for y,gg in g.groupby("year")
                      },sort_keys=True),
                      "yearly_pf":json.dumps({
                        str(int(y)):pf(gg.net_return.astype(float).tolist()) for y,gg in g.groupby("year")
                      },sort_keys=True),
                      "yearly_n":json.dumps({
                        str(int(y)):int(len(gg)) for y,gg in g.groupby("year")
                      },sort_keys=True),
                    })

qdf=pd.DataFrame(qrows)
cdf=pd.DataFrame(crows)
qdf.to_csv(out/"event_quintiles.csv",index=False)
cdf.to_csv(out/"continuous_summary.csv",index=False)

# Compact pre-portfolio mechanism readout.
summary={
 "schema":"LARGE-MARKET-EXHAUSTION-MECHANISM-V3",
 "discovery":"2019-2022","validation":"2023-2026Q1",
 "thresholds":thresholds,
 "features":{}
}
for feat in FEATURES:
    summary["features"][feat]={}
    for cap in (300,500):
        summary["features"][feat][f"top{cap}"]={}
        for target in (.60,.80):
            tk=f"t{int(target*100)}"
            summary["features"][feat][f"top{cap}"][tk]={}
            for period in ("discovery","validation"):
                q=qdf[(qdf.feature==feat)&(qdf.rank_cap==cap)&
                      (qdf.target_fraction==target)&(qdf.period==period)]
                c=cdf[(cdf.feature==feat)&(cdf.rank_cap==cap)&
                      (cdf.target_fraction==target)&(cdf.period==period)]
                item={"correlation":None,"q1":None,"q5":None}
                if len(c):
                    rr=c.iloc[0]
                    item["correlation"]={
                      "n":int(rr.n),
                      "rho_return":None if pd.isna(rr.rho_return) else float(rr.rho_return),
                      "rho_target":None if pd.isna(rr.rho_target) else float(rr.rho_target),
                      "rho_stop":None if pd.isna(rr.rho_stop) else float(rr.rho_stop),
                    }
                for qn,name in [(1,"q1"),(5,"q5")]:
                    z=q[q.quintile==qn]
                    if len(z):
                        rr=z.iloc[0]
                        item[name]={
                          "n":int(rr.n),"mean_trade":float(rr.mean_trade),
                          "profit_factor":None if pd.isna(rr.profit_factor) else float(rr.profit_factor),
                          "target_share":float(rr.target_share),"stop_share":float(rr.stop_share),
                          "mean_holding_sessions":float(rr.mean_holding_sessions),
                          "yearly_mean_trade":json.loads(rr.yearly_mean_trade),
                          "yearly_pf":json.loads(rr.yearly_pf),
                        }
                summary["features"][feat][f"top{cap}"][tk][period]=item

(out/"mechanism_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
print(json.dumps({"schema":summary["schema"],"rows":{"candidates":len(cand),"events":len(events),"quintiles":len(qdf),"continuous":len(cdf)}},indent=2))
