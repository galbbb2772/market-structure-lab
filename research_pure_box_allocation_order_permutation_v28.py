#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,hashlib,statistics
from pathlib import Path
import pandas as pd
import research_pure_box_core_geometry_simplicity_v13 as v13
import research_pure_box_capital_architecture_v22 as v22
import research_pure_box_capital_priority_v26 as v26

def randomize_order(cands,seed):
    out=[]
    for c in cands:
        z=dict(c)
        key=f"{seed}|{z['direct_entry_date']}|{z['symbol']}".encode()
        h=int(hashlib.sha256(key).hexdigest()[:12],16)
        z["liquidity_rank"]=h
        out.append(z)
    return out

def pct(values,x):
    if not values:return None
    return sum(v<=x for v in values)/len(values)

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=v13.load(a.indir)
    summary={"schema":"PURE-BOX-SIMPLE-CORE-ALLOCATION-ORDER-PERMUTATION-V28","results":{}}
    random_rows=[];anchor_rows=[]
    for cap in (300,500):
        cs=v22.bottom20(v13.strict_signals(sig,cap,cal,idx,nxt,bm))
        anchors={}
        for pol in ("PRO_RATA","LIQUIDITY_FIRST","LOW_ENTRY_FRACTION_FIRST"):
            r=v26.run(cs,cal,bm,pol);anchors[pol]=r
            anchor_rows.append({"rank_cap":cap,"policy":pol,**r})
        rr=[]
        for seed in range(40):
            rz=randomize_order(cs,seed)
            r=v26.run(rz,cal,bm,"LIQUIDITY_FIRST")
            row={"rank_cap":cap,"seed":seed,**r};rr.append(row);random_rows.append(row)
        tr=[x["total_return"] for x in rr];mdd=[x["max_drawdown"] for x in rr]
        sh=[x["daily_sharpe"] for x in rr];roll=[x["rolling_12m_min_return"] for x in rr]
        summary["results"][f"top{cap}"]={
          "candidate_n":len(cs),
          "anchors":anchors,
          "random_distribution":{
            "n":len(rr),
            "total_return_min":min(tr),"total_return_median":statistics.median(tr),"total_return_max":max(tr),
            "mdd_median":statistics.median(mdd),
            "sharpe_median":statistics.median(sh),
            "rolling12m_min_median":statistics.median(roll),
          },
          "empirical_percentiles":{
            "LIQUIDITY_FIRST_total_return":pct(tr,anchors["LIQUIDITY_FIRST"]["total_return"]),
            "LOW_ENTRY_FRACTION_FIRST_total_return":pct(tr,anchors["LOW_ENTRY_FRACTION_FIRST"]["total_return"]),
            "LIQUIDITY_FIRST_sharpe":pct(sh,anchors["LIQUIDITY_FIRST"]["daily_sharpe"]),
            "LOW_ENTRY_FRACTION_FIRST_sharpe":pct(sh,anchors["LOW_ENTRY_FRACTION_FIRST"]["daily_sharpe"]),
          }
        }
    pd.DataFrame(random_rows).to_csv(out/"random_results.csv",index=False)
    pd.DataFrame(anchor_rows).to_csv(out/"anchor_results.csv",index=False)
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
