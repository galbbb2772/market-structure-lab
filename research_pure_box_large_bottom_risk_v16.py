#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,statistics
from pathlib import Path
import pandas as pd
import research_pure_box_core_geometry_simplicity_v13 as v13
import research_pure_box_risk_to_invalidation_sizing_v14 as v14

RISK_BUDGETS=(.005,.0075,.01,.0125,.015,.0175,.02)

def filter_large_bottom(cands):
    out=[]
    for c in cands:
        if str(c["scale"])!="large": continue
        lo=float(c["lower"]); hi=float(c["upper"]); op=float(c["direct_entry_price"])
        if hi<=lo: continue
        ef=(op-lo)/(hi-lo)
        if ef<=.20:
            z=dict(c); z["entry_fraction"]=ef; out.append(z)
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--indir",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=v13.load(a.indir)

    rows=[]; summary={
      "schema":"PURE-BOX-LARGE-BOTTOM-RISK-SIZING-V16",
      "window":[v13.VAL_START,v13.VAL_END],
      "signal":"Strict Wide+Fresh / Large only / Bottom<=20% / direct",
      "results":{}
    }

    for cap in (300,500):
        base=v13.strict_signals(sig,cap,cal,idx,nxt,bm)
        cands=filter_large_bottom(base)
        for target in (.60,1.0):
            r=v14.run_risk(cands,cal,bm,target,20,fixed=True)
            key=f"top{cap}__t{int(target*100)}__fixed20"
            summary["results"][key]={**r,"candidate_n":len(cands)}
            rows.append({"rank_cap":cap,"target_fraction":target,"lane":"fixed20","risk_budget":None,"candidate_n":len(cands),**r})
            for rb in RISK_BUDGETS:
                r=v14.run_risk(cands,cal,bm,target,20,risk_budget=rb,fixed=False)
                key=f"top{cap}__t{int(target*100)}__risk{rb:.4f}"
                summary["results"][key]={**r,"candidate_n":len(cands)}
                rows.append({"rank_cap":cap,"target_fraction":target,"lane":"risk","risk_budget":rb,"candidate_n":len(cands),**r})

    df=pd.DataFrame(rows)
    df.to_csv(out/"results.csv",index=False)
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(df[["rank_cap","target_fraction","lane","risk_budget","candidate_n","total_return","max_drawdown","daily_sharpe","avg_exposure","profit_factor"]].to_string(index=False))

if __name__=="__main__":
    main()
