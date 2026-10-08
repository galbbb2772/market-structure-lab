#!/usr/bin/env python3
import argparse, json
from pathlib import Path
import pandas as pd
import research_pure_box_core_geometry_simplicity_v13 as v13
import research_pure_box_capital_architecture_v22 as v22

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=v13.load(a.indir)
    rows=[]
    for cap in (300,500):
        cs=v22.bottom20(v13.strict_signals(sig,cap,cal,idx,nxt,bm))
        for s,g in pd.DataFrame(cs).groupby("symbol"):
            rows.append({"rank_cap":cap,"symbol":str(s),"candidate_events":int(len(g)),
                         "min_liquidity_rank":int(g.liquidity_rank.min()) if "liquidity_rank" in g else None})
    df=pd.DataFrame(rows).sort_values(["rank_cap","symbol"])
    df.to_csv(out/"candidate_symbols.csv",index=False)
    uniq=sorted(df[df.rank_cap==500].symbol.unique().tolist())
    (out/"top500_symbols.json").write_text(json.dumps(uniq,indent=2),encoding="utf-8")
    print("top500 unique",len(uniq))
    print(df[df.rank_cap==500].to_string(index=False))
if __name__=="__main__":main()
