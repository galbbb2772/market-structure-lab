#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np,pandas as pd
import research_pure_box_large_market_permission_year_v1 as large

TARGETS=(.60,.80)
FRESH={300:23,500:24}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--year",type=int,required=True);ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm,spy=large.load(a.indir,a.year);large.CALENDAR=cal
    c=large.confirmed(sig,cal,idx,nxt,bm,{})
    ci={d:i for i,d in enumerate(cal)}
    rows=[];receipts=[]
    for cap in (300,500):
        z=c[(c.liquidity_rank<=cap)&(c.box_age_sessions<=FRESH[cap])].copy()
        for r in z.to_dict("records"):
            width=float(r["upper"])-float(r["lower"])
            entry=float(r["entry_price"])
            geom={
              "box_width_pct":width/entry,
              "entry_box_position":(entry-float(r["lower"]))/max(width,1e-12),
              "stop_distance_pct":(entry-float(r["lower"]))/entry,
              "liquidity_rank":float(r["liquidity_rank"]),
              "adv20_prior":float(r.get("adv20_prior",r.get("adv20",np.nan))) if pd.notna(r.get("adv20_prior",r.get("adv20",np.nan))) else np.nan,
            }
            for target in TARGETS:
                rr=large.event_outcome(r,bm,ci,target)
                if rr is None:continue
                tpx=float(r["lower"])+target*width
                rows.append({
                  "year":a.year,"rank_cap":cap,"target_fraction":target,
                  "signal_date":r["signal_date"],"confirmation_date":r["confirmation_date"],
                  "entry_date":r["entry_date"],"symbol":r["symbol"],
                  "box_age_sessions":r["box_age_sessions"],
                  "target_distance_pct":(tpx-entry)/entry,
                  **geom,**rr
                })
        receipts.append({"rank_cap":cap,"source_dates":len(cal),"raw_large_signals":int(((sig.liquidity_rank<=cap)&(sig.scale=="large")).sum()),"confirmed_fresh":int(len(z)),"unique_confirmed_symbols":int(z.symbol.nunique())})
    pd.DataFrame(rows).to_csv(out/f"temporal_stability_events_{a.year}.csv.gz",index=False,compression="gzip")
    (out/f"receipt_{a.year}.json").write_text(json.dumps({"schema":"LARGE-TEMPORAL-STABILITY-YEAR-V1","year":a.year,"caps":receipts},indent=2))
    print(json.dumps({"year":a.year,"event_rows":len(rows),"caps":receipts},indent=2))
if __name__=="__main__":main()
