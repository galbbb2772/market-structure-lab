#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd
import research_pure_box_core_geometry_simplicity_v13 as v13
import research_pure_box_simple_core_stress_v18 as v18

def base_bottom20(sig,cap,cal,idx,nxt,bm):
    out=[]
    for c in v13.strict_signals(sig,cap,cal,idx,nxt,bm):
        lo=float(c["lower"]);hi=float(c["upper"]);op=float(c["direct_entry_price"])
        if hi<=lo:continue
        if (op-lo)/(hi-lo)<=.20:out.append(dict(c))
    return out

def split(base,nxt,bm):
    surv=[];skip=[]
    for c in base:
        d=nxt.get(str(c["direct_entry_date"]))
        b=bm.get(str(c["symbol"]),{}).get(d) if d else None
        if b is None:
            skip.append(c);continue
        lo=float(c["lower"]);hi=float(c["upper"]);op=float(b["open"]);target=lo+.60*(hi-lo)
        ef=(op-lo)/(hi-lo) if hi>lo else 9
        if lo<op<target and ef<=.20:
            z=dict(c);z["stress_entry_date"]=d;z["stress_entry_price"]=op;surv.append(z)
        else:
            skip.append(c)
    return surv,skip

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=v13.load(a.indir)
    rows=[];summary={"schema":"PURE-BOX-SAME-COHORT-TIMING-V21","results":{}}
    for cap in (300,500):
        base=base_bottom20(sig,cap,cal,idx,nxt,bm)
        surv,skip=split(base,nxt,bm)
        for cost in (.0005,.002):
            for rb in (.0125,.015):
                tests=[
                  ("survivor_direct",surv,0),
                  ("survivor_delay",surv,1),
                  ("skipped_direct",skip,0),
                ]
                for name,cs,delay in tests:
                    r=v18.run(cs,cal,bm,rb,cost,delay)
                    key=f"top{cap}__{name}__c{cost:.4f}__r{rb:.4f}"
                    summary["results"][key]={**r,"rank_cap":cap,"variant":name,"cost":cost,"risk_budget":rb,
                                             "candidate_n":len(cs),"base_n":len(base),
                                             "cohort_share":len(cs)/len(base) if base else None}
                    rows.append(summary["results"][key])
    pd.DataFrame(rows).to_csv(out/"results.csv",index=False)
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(pd.DataFrame(rows)[["rank_cap","variant","cost","risk_budget","candidate_n","cohort_share","total_return","max_drawdown","daily_sharpe","rolling_12m_min_return","rolling_12m_positive_share"]].to_string(index=False))
if __name__=="__main__":main()
