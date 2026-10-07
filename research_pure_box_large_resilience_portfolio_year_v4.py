#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd
import research_pure_box_large_market_permission_year_v1 as base

FRESH={300:23,500:24}
TARGETS=(0.60,0.80)
ALLOCS=(0.05,0.10,0.20)
LANES=("OBSERVABLE_BASELINE","RESILIENT_ONLY","UNDERPERFORM_ONLY")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--year",type=int,required=True)
    ap.add_argument("--bars-dir",required=True)
    ap.add_argument("--features-dir",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

    # Use the original Pure Box source only to reconstruct the calendar + OHLC maps.
    _,cal,idx,nxt,bm,spy=base.load(a.bars_dir,a.year)
    base.CALENDAR=cal

    fp=next(Path(a.features_dir).glob(f"**/resilience_exhaustion_features_{a.year}.csv.gz"))
    f=pd.read_csv(fp)
    rows=[]
    for cap in (300,500):
        z=f[(f.liquidity_rank<=cap)&(f.box_age_sessions<=FRESH[cap])].copy()
        for lane in LANES:
            if lane=="RESILIENT_ONLY":
                q=z[z.relative_resilience_5d>=0].copy()
            elif lane=="UNDERPERFORM_ONLY":
                q=z[z.relative_resilience_5d<0].copy()
            else:
                q=z.copy()
            for target in TARGETS:
                for alloc in ALLOCS:
                    base.ALLOC=alloc
                    r=base.run_portfolio(q,bm,cal,a.year,target)
                    rows.append({
                      "year":a.year,"rank_cap":cap,"target_fraction":target,
                      "allocation":alloc,"lane":lane,
                      "eligible_events":int(len(q)),
                      **r
                    })
    df=pd.DataFrame(rows)
    df.to_csv(out/f"resilience_portfolio_{a.year}.csv",index=False)
    receipt={
      "schema":"LARGE-RESILIENCE-PORTFOLIO-YEAR-V4",
      "year":a.year,
      "feature_rows":int(len(f)),
      "rows":int(len(df))
    }
    (out/f"summary_{a.year}.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
    print(json.dumps(receipt,indent=2))

if __name__=="__main__":
    main()
