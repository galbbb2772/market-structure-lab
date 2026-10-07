#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd

CUTS={
  300:{
    "rebound_from_low_box":[0.08364372922571084,0.11844051909799756,0.15965078376613945,0.21709207759749272],
    "low_progress_box":[0.021269080980415862,0.04204723167148728,0.07028245996254273,0.10913893391875304],
  },
  500:{
    "rebound_from_low_box":[0.0851900393184794,0.1220014992503746,0.1639344262295076,0.2204325816843076],
    "low_progress_box":[0.0206461895102862,0.0418768920282542,0.0704091341579447,0.1100164203612482],
  }
}
TARGETS=(60,80)

def qassign(v,cuts):
    if pd.isna(v): return np.nan
    return int(np.searchsorted(np.asarray(cuts,float),float(v),side="right")+1)

def asbool(s):
    if s.dtype==bool:return s
    return s.astype(str).str.lower().isin(["true","1","yes"])

def outcome(z,label):
    elig=asbool(z[f"t{label}_eligible"])
    event=z[f"t{label}_event"].astype(str)
    day=pd.to_numeric(z[f"t{label}_event_day"],errors="coerce")
    complete=asbool(z["h20_complete"])
    usable=elig & ((day.notna()&(day<=20)) | complete)
    out=pd.Series("censored",index=z.index,dtype=object)
    out.loc[usable]="unresolved"
    out.loc[usable & day.notna() & (day<=20) & (event=="target")]="target"
    out.loc[usable & day.notna() & (day<=20) & (event=="stop")]="stop"
    out.loc[~elig]="ineligible"
    return out

def corner(qr,ql):
    hi=lambda q:q in (4,5)
    lo=lambda q:q in (1,2)
    if hi(qr) and hi(ql):return "BOTH_HIGH"
    if hi(qr) and lo(ql):return "REBOUND_ONLY"
    if lo(qr) and hi(ql):return "LOW_PROGRESS_ONLY"
    if lo(qr) and lo(ql):return "BOTH_LOW"
    return None

def rate_summary(g,label):
    oc=outcome(g,label)
    use=oc.isin(["target","stop","unresolved"])
    u=oc[use]
    gg=g.loc[use]
    return {
      "n":int(len(gg)),
      "target_rate":float((u=="target").mean()) if len(u) else None,
      "stop_rate":float((u=="stop").mean()) if len(u) else None,
      "unresolved_rate":float((u=="unresolved").mean()) if len(u) else None,
      "mean_fwd10":float(gg.fwd10_return.mean()) if len(gg) else None,
      "mean_mfe20":float(gg.mfe_progress_20.mean()) if len(gg) else None,
    }

def spear(a,b):
    z=pd.DataFrame({"a":a,"b":b}).dropna()
    if len(z)<10:return None
    v=z.a.rank(method="average").corr(z.b.rank(method="average"))
    return None if pd.isna(v) else float(v)

ap=argparse.ArgumentParser()
ap.add_argument("--indir",required=True)
ap.add_argument("--outdir",required=True)
a=ap.parse_args()
src=Path(a.indir);out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
files=sorted(src.glob("**/strategy_reconstruction_*.csv.gz"))
if len(files)<8:raise RuntimeError(f"expected 8 strategy reconstruction shards, got {len(files)}")
x=pd.concat([pd.read_csv(f) for f in files],ignore_index=True)
x["signal_date"]=x.signal_date.astype(str)
x["period"]=np.where(x.signal_date<="2022-12-31","discovery","validation")
x=x[(x.stage=="confirmed_no_new_low_green")&(x.scale=="large")].copy()

surface=[];corners=[];redundancy=[];checks=[]
for cap in (300,500):
    fresh=asbool(x[f"fresh_top{cap}"])
    z=x[(x.liquidity_rank<=cap)&fresh].copy()
    z["q_rebound"]=z.rebound_from_low_box.map(lambda v:qassign(v,CUTS[cap]["rebound_from_low_box"]))
    z["q_lowprog"]=z.low_progress_box.map(lambda v:qassign(v,CUTS[cap]["low_progress_box"]))
    z["corner"]=[corner(a,b) for a,b in zip(z.q_rebound,z.q_lowprog)]

    for period in ("discovery","validation"):
        p=z[z.period==period].copy()
        redundancy.append({
          "rank_cap":cap,"period":period,"n":int(len(p)),
          "rho_features":spear(p.rebound_from_low_box,p.low_progress_box)
        })
        for qr in range(1,6):
            for ql in range(1,6):
                g=p[(p.q_rebound==qr)&(p.q_lowprog==ql)]
                if g.empty:continue
                row={"rank_cap":cap,"period":period,"q_rebound":qr,"q_low_progress":ql,"n_total":int(len(g))}
                for label in TARGETS:
                    s=rate_summary(g,label)
                    for k,v in s.items():row[f"t{label}_{k}"]=v
                surface.append(row)

        for label in TARGETS:
            cstats={}
            for c in ["BOTH_HIGH","REBOUND_ONLY","LOW_PROGRESS_ONLY","BOTH_LOW"]:
                g=p[p.corner==c]
                s=rate_summary(g,label)
                cstats[c]=s
                corners.append({"rank_cap":cap,"period":period,"target":label,"corner":c,**s})

            bh=cstats["BOTH_HIGH"];ro=cstats["REBOUND_ONLY"];lo=cstats["LOW_PROGRESS_ONLY"];bl=cstats["BOTH_LOW"]
            enough=all(v["n"]>=30 for v in (bh,ro,lo,bl))
            ordering=bool(
              bh["target_rate"] is not None and ro["target_rate"] is not None and lo["target_rate"] is not None and bl["target_rate"] is not None and
              bh["target_rate"]>ro["target_rate"] and bh["target_rate"]>lo["target_rate"] and bh["target_rate"]>bl["target_rate"] and
              bh["stop_rate"]<ro["stop_rate"] and bh["stop_rate"]<lo["stop_rate"] and bh["stop_rate"]<bl["stop_rate"]
            )
            checks.append({
              "rank_cap":cap,"period":period,"target":label,
              "enough_n":enough,"ordering_pass":ordering,"passed":bool(enough and ordering),
              "both_high_n":bh["n"],"rebound_only_n":ro["n"],"low_progress_only_n":lo["n"],"both_low_n":bl["n"],
              "both_high_target_rate":bh["target_rate"],"rebound_only_target_rate":ro["target_rate"],
              "low_progress_only_target_rate":lo["target_rate"],"both_low_target_rate":bl["target_rate"],
              "both_high_stop_rate":bh["stop_rate"],"rebound_only_stop_rate":ro["stop_rate"],
              "low_progress_only_stop_rate":lo["stop_rate"],"both_low_stop_rate":bl["stop_rate"],
            })

sdf=pd.DataFrame(surface);cdf=pd.DataFrame(corners);rdf=pd.DataFrame(redundancy);kdf=pd.DataFrame(checks)
sdf.to_csv(out/"surface_5x5.csv",index=False)
cdf.to_csv(out/"corner_summary.csv",index=False)
rdf.to_csv(out/"redundancy.csv",index=False)
kdf.to_csv(out/"support_checks.csv",index=False)

summary={
 "schema":"LARGE-STOCK-EXHAUSTION-SURFACE-V2",
 "cutpoints":CUTS,
 "support":{
   "passed_checks":int(kdf.passed.sum()),
   "total_checks":int(len(kdf)),
   "all_checks_passed":bool(len(kdf) and kdf.passed.all())
 },
 "checks":checks,
 "redundancy":redundancy
}
(out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
print(json.dumps({"schema":summary["schema"],"support":summary["support"],"redundancy":redundancy},indent=2))
