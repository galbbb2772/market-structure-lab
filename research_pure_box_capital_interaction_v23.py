#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd
import research_pure_box_core_geometry_simplicity_v13 as v13
import research_pure_box_capital_architecture_v22 as v22

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=v13.load(a.indir)
    rows=[];summary={"schema":"PURE-BOX-SIMPLE-CORE-CAPITAL-INTERACTION-V23","results":{}}
    lanes=[
      ("BASE_R125_H20","FIXED_R125","H20"),
      ("EXPOSURE_AWARE_H20","EXPOSURE_AWARE","H20"),
      ("R125_H15","FIXED_R125","H15"),
      ("EXPOSURE_AWARE_H15","EXPOSURE_AWARE","H15"),
    ]
    for cap in (300,500):
        base=v22.bottom20(v13.strict_signals(sig,cap,cal,idx,nxt,bm))
        for name,pol,ex in lanes:
            r=v22.run(base,cal,bm,pol,ex)
            key=f"top{cap}__{name}"
            row={**r,"rank_cap":cap,"lane":name,"policy":pol,"exit_mode":ex,"candidate_n":len(base)}
            summary["results"][key]=row;rows.append(row)
    pd.DataFrame(rows).to_csv(out/"results.csv",index=False)
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    cols=["rank_cap","lane","total_return","cagr","max_drawdown","daily_sharpe","avg_exposure",
          "idle_day_share","risk_realization_ratio","completed_trades","rolling_12m_min_return",
          "rolling_12m_positive_share","rolling_12m_median_return"]
    print(pd.DataFrame(rows)[cols].to_string(index=False))

if __name__=="__main__":main()
