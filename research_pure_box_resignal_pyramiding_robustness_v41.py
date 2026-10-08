#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd
import research_pure_box_core_geometry_simplicity_v13 as v13
import research_pure_box_capital_architecture_v22 as v22
import research_pure_box_resignal_risk_refill_v40 as v40

POLICIES=("SKIP_OVERLAP","REFILL_TO_R125","REFILL_TO_R150","PYRAMID_TO_R250")

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=v13.load(a.indir)
    rows=[];summary={"schema":"PURE-BOX-SIMPLE-CORE-RESIGNAL-PYRAMIDING-ROBUSTNESS-V41","results":{}}
    for cap in (300,500):
        cs=v22.bottom20(v13.strict_signals(sig,cap,cal,idx,nxt,bm))
        for bps in (5,10,20):
            v40.EC=v40.XC=bps/10000.0
            for pol in POLICIES:
                r=v40.run(cs,cal,bm,pol)
                row={"rank_cap":cap,"bps":bps,"policy":pol,**r}
                rows.append(row);summary["results"][f"top{cap}__{bps}bps__{pol}"]=row
    df=pd.DataFrame(rows)
    deltas=[]
    for cap in (300,500):
        for bps in (5,10,20):
            base=df[(df.rank_cap==cap)&(df.bps==bps)&(df.policy=="SKIP_OVERLAP")].iloc[0]
            pyr=df[(df.rank_cap==cap)&(df.bps==bps)&(df.policy=="PYRAMID_TO_R250")].iloc[0]
            bd=base.yearly_return; pdict=pyr.yearly_return
            # csv may hold dict in-memory as dict here
            yd={y:float(pdict[y]-bd[y]) for y in bd.keys()}
            positive=[max(0,x) for x in yd.values()]
            denom=sum(positive)
            share2025=max(0,yd.get("2025",0.0))/denom if denom>0 else None
            deltas.append({
              "rank_cap":cap,"bps":bps,
              "return_delta":float(pyr.total_return-base.total_return),
              "cagr_delta":float(pyr.cagr-base.cagr),
              "mdd_delta":float(pyr.max_drawdown-base.max_drawdown),
              "sharpe_delta":float(pyr.daily_sharpe-base.daily_sharpe),
              "roll12m_min_delta":float(pyr.rolling_12m_min_return-base.rolling_12m_min_return),
              "yearly_delta":yd,
              "positive_uplift_share_2025":share2025,
              "pyramid_add_on_events":int(pyr.add_on_events),
              "pyramid_max_position_risk_after_add":float(pyr.max_position_risk_after_add),
              "pyramid_top5_abs_funded_pnl_share":float(pyr.top5_abs_funded_pnl_share),
              "pyramid_top10_abs_funded_pnl_share":float(pyr.top10_abs_funded_pnl_share),
              "pyramid_turnover_proxy":float(pyr.turnover_proxy)
            })
    pd.DataFrame(deltas).to_csv(out/"deltas.csv",index=False)
    df.to_csv(out/"results.csv",index=False)
    summary["deltas"]=deltas
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(pd.DataFrame(deltas).to_string(index=False))
if __name__=="__main__":main()
