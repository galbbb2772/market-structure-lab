#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd
import research_pure_box_core_geometry_simplicity_v13 as core

def add_entry_fraction(cands):
    out=[]
    for c in cands:
        w=float(c["upper"])-float(c["lower"])
        if w<=0:continue
        ef=(float(c["direct_entry_price"])-float(c["lower"]))/w
        out.append({**c,"entry_fraction":ef})
    return out

def lane_map(cands):
    def f(pred): return [c for c in cands if pred(c)]
    return {
      "ALL":cands,
      "SMALL_ONLY":f(lambda c:c["scale"]=="small"),
      "LARGE_ONLY":f(lambda c:c["scale"]=="large"),
      "BOTTOM_0_10":f(lambda c:0<=c["entry_fraction"]<=0.10),
      "BOTTOM_10_20":f(lambda c:0.10<c["entry_fraction"]<=0.20),
      "BOTTOM_20_30":f(lambda c:0.20<c["entry_fraction"]<=0.30),
      "ABOVE_30":f(lambda c:c["entry_fraction"]>0.30),
      "BOTTOM_LE_10":f(lambda c:c["entry_fraction"]<=0.10),
      "BOTTOM_LE_20":f(lambda c:c["entry_fraction"]<=0.20),
      "BOTTOM_LE_30":f(lambda c:c["entry_fraction"]<=0.30),
      "LARGE_BOTTOM_LE_20":f(lambda c:c["scale"]=="large" and c["entry_fraction"]<=0.20),
      "SMALL_BOTTOM_LE_20":f(lambda c:c["scale"]=="small" and c["entry_fraction"]<=0.20),
    }

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=core.load(a.indir)
    rows=[];results={}
    for cap in (300,500):
        cands=add_entry_fraction(core.strict_signals(sig,cap,cal,idx,nxt,bm))
        for lane,q in lane_map(cands).items():
            if not q:continue
            r=core.run(q,cal,bm,"direct",0.60,20,"fixed")
            efs=[float(c["entry_fraction"]) for c in q]
            rec={**r,"candidate_n":len(q),"mean_entry_fraction":sum(efs)/len(efs),
                 "median_entry_fraction":float(pd.Series(efs).median())}
            key=f"top{cap}__{lane}"
            results[key]=rec
            rows.append({"rank_cap":cap,"lane":lane,**rec})
    df=pd.DataFrame(rows)
    df.to_csv(out/"results.csv",index=False)
    summary={
      "schema":"PURE-BOX-CORE-GEOMETRY-ANATOMY-V15",
      "window":[core.VAL_START,core.VAL_END],
      "contract":"Strict Wide+Fresh / direct / t60 / H20 / fixed20",
      "results":results,
      "automatic_production_change":False
    }
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))

if __name__=="__main__":main()
