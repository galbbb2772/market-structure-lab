#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd
import research_pure_box_core_geometry_simplicity_v13 as v13
import research_pure_box_capital_architecture_v22 as v22
import research_pure_box_capital_displacement_v35 as v35

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=v13.load(a.indir)
    rows=[];summary={"schema":"PURE-BOX-SIMPLE-CORE-STALE-REPLACEMENT-ROBUSTNESS-V36","results":{}}
    for cap in (300,500):
        cs=v22.bottom20(v13.strict_signals(sig,cap,cal,idx,nxt,bm))
        for bps in (5,10,20):
            v35.EC=v35.XC=bps/10000.0
            for pol in ("NO_DISPLACEMENT","AGE10_STALE_REPLACE"):
                r=v35.run(cs,cal,bm,pol)
                key=f"top{cap}__{bps}bps__{pol}"
                row={"rank_cap":cap,"bps":bps,"policy":pol,**r}
                summary["results"][key]=row;rows.append(row)
    df=pd.DataFrame(rows)
    # paired deltas
    deltas=[]
    for cap in (300,500):
        for bps in (5,10,20):
            a=df[(df.rank_cap==cap)&(df.bps==bps)&(df.policy=="NO_DISPLACEMENT")].iloc[0]
            b=df[(df.rank_cap==cap)&(df.bps==bps)&(df.policy=="AGE10_STALE_REPLACE")].iloc[0]
            deltas.append({
              "rank_cap":cap,"bps":bps,
              "return_delta":float(b.total_return-a.total_return),
              "mdd_delta":float(b.max_drawdown-a.max_drawdown),
              "sharpe_delta":float(b.daily_sharpe-a.daily_sharpe),
              "roll12m_min_delta":float(b.rolling_12m_min_return-a.rolling_12m_min_return),
              "replacement_count":int(b.replacement_count),
              "mean_displaced_realized_return":float(b.mean_displaced_realized_return) if pd.notna(b.mean_displaced_realized_return) else None
            })
    pd.DataFrame(deltas).to_csv(out/"deltas.csv",index=False)
    df.to_csv(out/"results.csv",index=False)
    summary["deltas"]=deltas
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(pd.DataFrame(deltas).to_string(index=False))
if __name__=="__main__": main()
