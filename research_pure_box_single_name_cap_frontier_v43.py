#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd
import research_pure_box_core_geometry_simplicity_v13 as v13
import research_pure_box_capital_architecture_v22 as v22
import research_pure_box_resignal_risk_refill_v40 as v40

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=v13.load(a.indir)
    rows=[];summary={"schema":"PURE-BOX-SIMPLE-CORE-SINGLE-NAME-CAP-FRONTIER-V43","results":{}}
    for capn in (300,500):
        cs=v22.bottom20(v13.strict_signals(sig,capn,cal,idx,nxt,bm))
        for name_cap in (.50,.60,.75,1.00):
            v40.CAP=name_cap;v40.EC=v13.ENTRY_COST;v40.XC=v13.EXIT_COST
            for pol in ("SKIP_OVERLAP","PYRAMID_TO_R250"):
                r=v40.run(cs,cal,bm,pol)
                row={"rank_cap":capn,"single_name_cap":name_cap,"policy":pol,**r}
                rows.append(row)
                summary["results"][f"top{capn}__cap{name_cap:.2f}__{pol}"]=row
    df=pd.DataFrame(rows)
    deltas=[]
    for capn in (300,500):
        for name_cap in (.50,.60,.75,1.00):
            a=df[(df.rank_cap==capn)&(df.single_name_cap==name_cap)&(df.policy=="SKIP_OVERLAP")].iloc[0]
            b=df[(df.rank_cap==capn)&(df.single_name_cap==name_cap)&(df.policy=="PYRAMID_TO_R250")].iloc[0]
            deltas.append({
              "rank_cap":capn,"single_name_cap":name_cap,
              "pyramid_return_delta":float(b.total_return-a.total_return),
              "pyramid_mdd_delta":float(b.max_drawdown-a.max_drawdown),
              "pyramid_sharpe_delta":float(b.daily_sharpe-a.daily_sharpe),
              "pyramid_roll12m_min_delta":float(b.rolling_12m_min_return-a.rolling_12m_min_return)
            })
    df.to_csv(out/"results.csv",index=False)
    pd.DataFrame(deltas).to_csv(out/"deltas.csv",index=False)
    summary["deltas"]=deltas
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(df[["rank_cap","single_name_cap","policy","total_return","cagr","max_drawdown","daily_sharpe",
              "rolling_12m_min_return","add_on_events","mean_position_risk_after_add","max_position_risk_after_add",
              "top5_abs_funded_pnl_share"]].to_string(index=False))
if __name__=="__main__":main()
