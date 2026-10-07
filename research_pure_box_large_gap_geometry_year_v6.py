#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd
import research_pure_box_large_market_permission_year_v1 as large

TARGETS=(.60,.80)
GAP_METHODS={"EXPANDING":"gap_expanding_lane","FIXED_-1PCT":"gap_fixed_lane"}
EXHAUSTION={"rebound_from_low_box":"rebound_strength","low_progress_box":"lowprog_strength"}

def pf(rs):
    w=sum(float(x) for x in rs if float(x)>0); l=-sum(float(x) for x in rs if float(x)<0)
    return w/l if l>0 else None

ap=argparse.ArgumentParser()
ap.add_argument("--year",type=int,required=True)
ap.add_argument("--indir",required=True)
ap.add_argument("--labels",required=True)
ap.add_argument("--outdir",required=True)
a=ap.parse_args()
out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

_,cal,_,_,bm,_=large.load(a.indir,a.year)
large.CALENDAR=cal
ci={d:i for i,d in enumerate(cal)}
lab=pd.read_csv(a.labels,compression="infer"); lab["year"]=lab.year.astype(int)

all_events=[]; group_rows=[]
for cap in (300,500):
    z=lab[(lab.year==a.year)&(lab.rank_cap==cap)].copy()
    for target in TARGETS:
        ev=[]
        for row in z.to_dict("records"):
            rr=large.event_outcome(row,bm,ci,target)
            if rr is not None:
                ev.append({**row,"target_fraction":target,**rr})
        e=pd.DataFrame(ev)
        if e.empty: continue
        all_events.append(e)
        key=str(int(target*100))
        for method,gcol in GAP_METHODS.items():
            qcol=f"entry_q__{method}"
            for feat,scol in EXHAUSTION.items():
                ex=e[e[gcol]=="EXTREME_GAP"].copy()
                for strength in ("STRONG","WEAK"):
                    g=ex[ex[scol]==strength].copy()
                    if g.empty: continue
                    rs=g.net_return.astype(float).tolist()
                    group_rows.append({
                      "year":a.year,"rank_cap":cap,"target_fraction":target,
                      "gap_method":method,"exhaustion_feature":feat,"strength":strength,
                      "n":int(len(g)),
                      "mean_trade":float(g.net_return.mean()),
                      "profit_factor":pf(rs),
                      "mean_entry_fraction":float(g.entry_fraction.mean()),
                      "mean_stop_distance":float(g.stop_distance.mean()),
                      "mean_target_upside":float(g[f"target_upside_{key}"].mean()),
                      "mean_rr":float(g[f"rr_{key}"].dropna().mean()) if g[f"rr_{key}"].notna().any() else None,
                    })
                # Geometry-stratified cells.
                for q in (1,2,3,4):
                    gg=ex[ex[qcol]==q]
                    for strength in ("STRONG","WEAK"):
                        g=gg[gg[scol]==strength]
                        if g.empty: continue
                        rs=g.net_return.astype(float).tolist()
                        group_rows.append({
                          "year":a.year,"rank_cap":cap,"target_fraction":target,
                          "gap_method":method,"exhaustion_feature":feat,
                          "strength":f"Q{q}__{strength}",
                          "n":int(len(g)),"mean_trade":float(g.net_return.mean()),
                          "profit_factor":pf(rs),
                          "mean_entry_fraction":float(g.entry_fraction.mean()),
                          "mean_stop_distance":float(g.stop_distance.mean()),
                          "mean_target_upside":float(g[f"target_upside_{key}"].mean()),
                          "mean_rr":float(g[f"rr_{key}"].dropna().mean()) if g[f"rr_{key}"].notna().any() else None,
                        })

if all_events:
    pd.concat(all_events,ignore_index=True).to_csv(out/f"gap_geometry_events_{a.year}.csv.gz",index=False,compression="gzip")
pd.DataFrame(group_rows).to_csv(out/f"gap_geometry_groups_{a.year}.csv",index=False)
summary={"schema":"LARGE-GAP-GEOMETRY-YEAR-V6","year":a.year,
         "event_rows":int(sum(len(x) for x in all_events)),"group_rows":len(group_rows)}
(out/f"summary_{a.year}.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
print(json.dumps(summary,indent=2))
