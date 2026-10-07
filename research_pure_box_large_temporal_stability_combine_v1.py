#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,math
from pathlib import Path
import numpy as np,pandas as pd

def pf(rs):
    rs=[float(x) for x in rs if pd.notna(x)]
    w=sum(x for x in rs if x>0);l=-sum(x for x in rs if x<0)
    return w/l if l>0 else None
def qcuts(s):
    x=pd.to_numeric(s,errors="coerce").dropna()
    return [float(x.quantile(q)) for q in (.2,.4,.6,.8)]
def qassign(v,c):
    if pd.isna(v):return np.nan
    return int(np.searchsorted(np.asarray(c,float),float(v),side="right")+1)
def summarize(g):
    rs=g.net_return.astype(float).tolist();re=g.exit_reason.astype(str)
    return {
      "n":int(len(g)),
      "mean_trade":float(g.net_return.mean()) if len(g) else None,
      "median_trade":float(g.net_return.median()) if len(g) else None,
      "profit_factor":pf(rs),
      "win_rate":float((g.net_return>0).mean()) if len(g) else None,
      "target_share":float(re.isin(["target","target_gap"]).mean()) if len(g) else None,
      "stop_share":float(re.isin(["stop","stop_gap"]).mean()) if len(g) else None,
      "max_hold_share":float(re.str.startswith("max_hold").mean()) if len(g) else None,
      "mean_holding_sessions":float(g.holding_sessions.mean()) if len(g) else None,
      "mean_mfe_return":float(g.mfe_return.mean()) if len(g) else None,
      "mean_mae_return":float(g.mae_return.mean()) if len(g) else None,
      "unique_symbols":int(g.symbol.nunique()) if len(g) else 0,
      "mean_box_width_pct":float(g.box_width_pct.mean()) if len(g) else None,
      "mean_box_age":float(g.box_age_sessions.mean()) if len(g) else None,
      "mean_entry_box_position":float(g.entry_box_position.mean()) if len(g) else None,
      "mean_stop_distance_pct":float(g.stop_distance_pct.mean()) if len(g) else None,
      "mean_target_distance_pct":float(g.target_distance_pct.mean()) if len(g) else None,
      "median_liquidity_rank":float(g.liquidity_rank.median()) if len(g) else None,
      "median_adv20_prior":float(g.adv20_prior.median()) if len(g) and g.adv20_prior.notna().any() else None,
    }

ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
src=Path(a.indir);out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
files=sorted(src.glob("**/temporal_stability_events_*.csv.gz"))
if len(files)<8:raise RuntimeError(f"expected 8 shards got {len(files)}")
x=pd.concat([pd.read_csv(f) for f in files],ignore_index=True)
x["entry_date"]=x.entry_date.astype(str)
x["quarter"]=x.entry_date.str[:4]+"Q"+(((x.entry_date.str[5:7].astype(int)-1)//3)+1).astype(str)
x["period"]=np.where(x.year<=2022,"discovery","validation")
x.to_csv(out/"all_events.csv.gz",index=False,compression="gzip")

# Discovery-fixed geometry bins.
thresholds={}
for cap in (300,500):
    thresholds[f"top{cap}"]={}
    d=x[(x.rank_cap==cap)&(x.period=="discovery")&(x.target_fraction==.60)]
    for feat in ("box_width_pct","box_age_sessions"):
        cuts=qcuts(d[feat]);thresholds[f"top{cap}"][feat]=cuts
        mask=x.rank_cap==cap
        x.loc[mask,f"q__{feat}"]=x.loc[mask,feat].map(lambda v:qassign(v,cuts))
(out/"geometry_thresholds.json").write_text(json.dumps(thresholds,indent=2))

annual=[];quarterly=[]
for (cap,target,year),g in x.groupby(["rank_cap","target_fraction","year"]):
    annual.append({"rank_cap":int(cap),"target_fraction":float(target),"year":int(year),**summarize(g)})
for (cap,target,qtr),g in x.groupby(["rank_cap","target_fraction","quarter"]):
    quarterly.append({"rank_cap":int(cap),"target_fraction":float(target),"quarter":qtr,**summarize(g)})
adf=pd.DataFrame(annual);qdf=pd.DataFrame(quarterly)
adf.to_csv(out/"annual_stability.csv",index=False);qdf.to_csv(out/"quarterly_stability.csv",index=False)

# Rolling trailing 4-quarter event economics, pooled events.
roll=[]
for cap in (300,500):
  for target in (.60,.80):
    z=x[(x.rank_cap==cap)&(x.target_fraction==target)].copy()
    quarters=sorted(z.quarter.unique())
    for i in range(3,len(quarters)):
      qs=quarters[i-3:i+1];g=z[z.quarter.isin(qs)]
      roll.append({"rank_cap":cap,"target_fraction":target,"end_quarter":quarters[i],"quarters":";".join(qs),**summarize(g)})
pd.DataFrame(roll).to_csv(out/"rolling_4q_stability.csv",index=False)

# Geometry-bin stability and central common-geometry subset.
geom=[]
for cap in (300,500):
  for target in (.60,.80):
    for period in ("discovery","validation"):
      z=x[(x.rank_cap==cap)&(x.target_fraction==target)&(x.period==period)]
      for feat in ("box_width_pct","box_age_sessions"):
        qcol=f"q__{feat}"
        for q in range(1,6):
          g=z[z[qcol]==q]
          geom.append({"rank_cap":cap,"target_fraction":target,"period":period,"dimension":feat,"bin":f"Q{q}",**summarize(g)})
      central=z[z["q__box_width_pct"].isin([2,3,4])&z["q__box_age_sessions"].isin([2,3,4])]
      geom.append({"rank_cap":cap,"target_fraction":target,"period":period,"dimension":"central_geometry","bin":"Q2_Q4_both",**summarize(central)})
gdf=pd.DataFrame(geom);gdf.to_csv(out/"geometry_control.csv",index=False)

summary={"schema":"LARGE-TEMPORAL-STABILITY-V1","thresholds":thresholds,
         "top500_t60_yearly":adf[(adf.rank_cap==500)&(adf.target_fraction==.60)].to_dict("records"),
         "top500_t80_yearly":adf[(adf.rank_cap==500)&(adf.target_fraction==.80)].to_dict("records"),
         "top300_t60_yearly":adf[(adf.rank_cap==300)&(adf.target_fraction==.60)].to_dict("records"),
         "central_geometry":gdf[gdf.dimension=="central_geometry"].to_dict("records")}
(out/"summary.json").write_text(json.dumps(summary,indent=2))
print(json.dumps({"schema":summary["schema"],"annual_rows":len(adf),"quarterly_rows":len(qdf),"geometry_rows":len(gdf)},indent=2))
