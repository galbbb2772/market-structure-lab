#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd
import research_pure_box_core_geometry_simplicity_v13 as v13
import research_pure_box_capital_architecture_v22 as v22
import research_pure_box_age3_resignal_addon_v48 as v48

NON_STOCK={
"ARKK","ETHA","FBTC","GBTC","GDX","GDXJ","IBIT","KRE","KWEB","NVDL","QID",
"SDOW","SDS","SLV","SPXS","SPXU","SQQQ","SSO","SVXY","TMF","TNA","TZA",
"UDOW","USO","VXX","XME"
}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=v13.load(a.indir)
    policies=("SKIP_OVERLAP","EARLY_R250","AGE3_ONLY_R250")
    rows=[];summary={"schema":"PURE-BOX-SIMPLE-CORE-INSTRUMENT-PURITY-V50-STAGE2","results":{},"audit":{}}
    for cap in (300,500):
        mixed=v22.bottom20(v13.strict_signals(sig,cap,cal,idx,nxt,bm))
        stock=[c for c in mixed if str(c["symbol"]) not in NON_STOCK]
        ex=[c for c in mixed if str(c["symbol"]) in NON_STOCK]
        summary["audit"][f"top{cap}"]={
          "mixed_candidate_events":len(mixed),
          "stock_only_candidate_events":len(stock),
          "excluded_candidate_events":len(ex),
          "excluded_symbols":sorted(set(str(c["symbol"]) for c in ex)),
          "excluded_symbol_count":len(set(str(c["symbol"]) for c in ex))
        }
        for bps in (5,10,20):
            v48.EC=v48.XC=bps/10000.0
            for label,cands in (("MIXED_UNIVERSE",mixed),("STOCK_ONLY",stock)):
                for p in policies:
                    r=v48.run(cands,cal,bm,p)
                    key=f"top{cap}__{bps}bps__{label}__{p}"
                    row={"rank_cap":cap,"bps":bps,"instrument_scope":label,"policy":p,**r}
                    rows.append(row);summary["results"][key]=row
    df=pd.DataFrame(rows)
    deltas=[]
    for cap in (300,500):
        for bps in (5,10,20):
            for p in policies:
                a=df[(df.rank_cap==cap)&(df.bps==bps)&(df.instrument_scope=="MIXED_UNIVERSE")&(df.policy==p)].iloc[0]
                b=df[(df.rank_cap==cap)&(df.bps==bps)&(df.instrument_scope=="STOCK_ONLY")&(df.policy==p)].iloc[0]
                deltas.append({
                  "rank_cap":cap,"bps":bps,"policy":p,
                  "return_delta_stock_minus_mixed":float(b.total_return-a.total_return),
                  "mdd_delta_stock_minus_mixed":float(b.max_drawdown-a.max_drawdown),
                  "sharpe_delta_stock_minus_mixed":float(b.daily_sharpe-a.daily_sharpe),
                  "rollmin_delta_stock_minus_mixed":float(b.rolling_12m_min_return-a.rolling_12m_min_return),
                  "addon_event_delta_stock_minus_mixed":int(b.add_on_events-a.add_on_events)
                })
    summary["deltas"]=deltas
    df.to_csv(out/"results.csv",index=False)
    pd.DataFrame(deltas).to_csv(out/"deltas.csv",index=False)
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(pd.DataFrame(deltas).to_string(index=False))
    print(df[["rank_cap","bps","instrument_scope","policy","total_return","max_drawdown","daily_sharpe","rolling_12m_min_return","add_on_events"]].to_string(index=False))
if __name__=="__main__":main()
