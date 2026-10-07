#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np, pandas as pd

FEATURES=["gap_component","intraday_component","close_recovery_from_low","downside_wick_fraction","volume_ratio20","gap_share_of_negative_move"]

def qcuts(s):
    x=pd.to_numeric(s,errors="coerce").dropna()
    return [float(x.quantile(q)) for q in (.2,.4,.6,.8)]
def qassign(v,c):
    if pd.isna(v): return np.nan
    return int(np.searchsorted(np.asarray(c,float),float(v),side="right")+1)
def pf(rs):
    rs=[float(x) for x in rs if pd.notna(x)]
    w=sum(x for x in rs if x>0);l=-sum(x for x in rs if x<0)
    return w/l if l>0 else None
def rho(a,b):
    z=pd.DataFrame({"a":a,"b":b}).dropna()
    if len(z)<10:return None
    v=z.a.rank().corr(z.b.rank())
    return None if pd.isna(v) else float(v)

ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
src=Path(a.indir);out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
cf=sorted(src.glob("**/selloff_anatomy_candidates_*.csv.gz"));ef=sorted(src.glob("**/selloff_anatomy_events_*.csv.gz"))
if len(cf)<16 or len(ef)<32:raise RuntimeError(f"shards {len(cf)} {len(ef)}")
cand=pd.concat([pd.read_csv(f) for f in cf],ignore_index=True);ev=pd.concat([pd.read_csv(f) for f in ef],ignore_index=True)
cand["period"]=np.where(cand.year<=2022,"discovery","validation");ev["period"]=np.where(ev.year<=2022,"discovery","validation")

thresholds={}
for cap in (300,500):
    thresholds[f"top{cap}"]={}
    d=cand[(cand.rank_cap==cap)&(cand.period=="discovery")]
    for feat in FEATURES:
        cuts=qcuts(d[feat]);thresholds[f"top{cap}"][feat]=cuts
        cand.loc[cand.rank_cap==cap,f"q__{feat}"]=cand.loc[cand.rank_cap==cap,feat].map(lambda v:qassign(v,cuts))
        ev.loc[ev.rank_cap==cap,f"q__{feat}"]=ev.loc[ev.rank_cap==cap,feat].map(lambda v:qassign(v,cuts))
cand.to_csv(out/"labeled_candidates.csv.gz",index=False,compression="gzip")
(out/"thresholds.json").write_text(json.dumps(thresholds,indent=2))

qrows=[];crows=[]
for cap in (300,500):
  for target in (.6,.8):
    b=ev[(ev.rank_cap==cap)&(ev.target_fraction==target)]
    for feat in FEATURES:
      for period in ("discovery","validation"):
        z=b[b.period==period].copy()
        targ=z.exit_reason.astype(str).isin(["target","target_gap"]).astype(float)
        stop=z.exit_reason.astype(str).isin(["stop","stop_gap"]).astype(float)
        crows.append({"rank_cap":cap,"target_fraction":target,"feature":feat,"period":period,"n":int(z[feat].notna().sum()),"rho_return":rho(z[feat],z.net_return),"rho_target":rho(z[feat],targ),"rho_stop":rho(z[feat],stop)})
        qcol=f"q__{feat}"
        for qn in range(1,6):
          g=z[z[qcol]==qn]
          if g.empty:continue
          rs=g.net_return.tolist();re=g.exit_reason.astype(str)
          qrows.append({"rank_cap":cap,"target_fraction":target,"feature":feat,"period":period,"quintile":qn,"n":len(g),"mean_trade":float(g.net_return.mean()),"median_trade":float(g.net_return.median()),"profit_factor":pf(rs),"win_rate":float((g.net_return>0).mean()),"target_share":float(re.isin(["target","target_gap"]).mean()),"stop_share":float(re.isin(["stop","stop_gap"]).mean()),"max_hold_share":float(re.str.startswith("max_hold").mean()),"mean_holding_sessions":float(g.holding_sessions.mean()),"mean_mfe_return":float(g.mfe_return.mean()),"mean_mae_return":float(g.mae_return.mean()),"yearly_mean_trade":json.dumps({str(int(y)):float(gg.net_return.mean()) for y,gg in g.groupby("year")},sort_keys=True),"yearly_pf":json.dumps({str(int(y)):pf(gg.net_return.tolist()) for y,gg in g.groupby("year")},sort_keys=True)})
pd.DataFrame(qrows).to_csv(out/"event_quintiles.csv",index=False)
pd.DataFrame(crows).to_csv(out/"continuous_summary.csv",index=False)
(out/"mechanism_summary.json").write_text(json.dumps({"schema":"LARGE-SELLOFF-ANATOMY-MECHANISM-V2","thresholds":thresholds},indent=2))
print(json.dumps({"qrows":len(qrows),"crows":len(crows),"candidates":len(cand)},indent=2))
