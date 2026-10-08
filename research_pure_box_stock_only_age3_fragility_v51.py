#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd
import research_pure_box_core_geometry_simplicity_v13 as v13
import research_pure_box_capital_architecture_v22 as v22
import research_pure_box_age3_resignal_addon_v48 as v48
import research_pure_box_age3_addon_fragility_v49 as v49

NON_STOCK={
"ARKK","ETHA","FBTC","GBTC","GDX","GDXJ","IBIT","KRE","KWEB","NVDL","QID",
"SDOW","SDS","SLV","SPXS","SPXU","SQQQ","SSO","SVXY","TMF","TNA","TZA",
"UDOW","USO","VXX","XME"
}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=v13.load(a.indir)

    summary={"schema":"PURE-BOX-SIMPLE-CORE-STOCK-ONLY-AGE3-FRAGILITY-V51","results":{}}
    frames=[]
    for cap in (300,500):
        mixed=v22.bottom20(v13.strict_signals(sig,cap,cal,idx,nxt,bm))
        stock=[c for c in mixed if str(c["symbol"]) not in NON_STOCK]

        # Exact 5bps portfolio block returns for STOCK_ONLY controls.
        v48.EC=v48.XC=.0005
        block={}
        for p in ("SKIP_OVERLAP","AGE3_ONLY_R250"):
            r=v48.run(stock,cal,bm,p)
            yr=r["yearly_return"]
            block[p]={
              "portfolio":r,
              "all_block_compound":v49.compound_years(yr),
              "ex_2025_block_compound":v49.compound_years(yr,"2025"),
              "leave_one_year_out":{y:v49.compound_years(yr,y) for y in yr}
            }

        # Event-level AGE3 add-on fragility on STOCK_ONLY.
        df=v49.run_events(stock,cal,bm)
        df["rank_cap"]=cap;frames.append(df)
        overall=v49.stats(df)
        ex25=v49.stats(df[df.year!="2025"])
        summary["results"][f"top{cap}"]={
          "candidate_events":len(stock),
          "block_compounding":block,
          "addon_overall":overall,
          "addon_ex_2025":ex25
        }

    if frames:
        pd.concat(frames,ignore_index=True).to_csv(out/"stock_only_age3_addon_events.csv",index=False)
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
