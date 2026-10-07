#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd

import research_pure_box_large_market_permission_year_v1 as large
import research_pure_box_breadth_permission_v1 as breadthmod

TARGETS={"60":.60,"80":.80}
FRESH={300:23,500:24}
STOCK_FEATURES=["rebound_from_low_box","low_progress_box"]
MARKET_FEATURES=["pct_up_1d","pct_new_20d_low"]

def load_full_bars(indir):
    p=Path(indir);parts=[]
    for bp in sorted(p.glob("**/bars_*.csv.gz")):
        for ch in pd.read_csv(bp,chunksize=300000):
            ch["date"]=ch.date.astype(str);ch["ticker"]=ch.ticker.astype(str)
            parts.append(ch)
    x=pd.concat(parts,ignore_index=True)
    return x.sort_values(["ticker","date"]).drop_duplicates(["ticker","date"],keep="last")

def add_stock_features(df,bm):
    rows=[]
    for r in df.to_dict("records"):
        sm=bm.get(r["symbol"],{})
        s=sm.get(str(r["signal_date"])); c=sm.get(str(r["confirmation_date"]))
        if s is None or c is None: continue
        lo=float(r["lower"]); hi=float(r["upper"]); width=max(hi-lo,1e-12)
        rebound=(float(c["close"])-min(float(s["low"]),float(c["low"])))/width
        lowprog=(float(c["low"])-float(s["low"]))/width
        rows.append({**r,
          "rebound_from_low_box":rebound,
          "low_progress_box":lowprog,
        })
    return pd.DataFrame(rows)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--year",type=int,required=True)
    ap.add_argument("--indir",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

    sig,cal,idx,nxt,bm,spy=large.load(a.indir,a.year)
    large.CALENDAR=cal
    c=large.confirmed(sig,cal,idx,nxt,bm,{})
    c=add_stock_features(c,bm)
    bars=load_full_bars(a.indir)
    ci={d:i for i,d in enumerate(cal)}

    receipt={"schema":"LARGE-RELATIVE-RESILIENCE-YEAR-V4","year":a.year,"caps":{}}
    for cap in (300,500):
        b=breadthmod.build_breadth(bars,cap)
        bmap={str(r["date"]):r for r in b.to_dict("records")}
        z=c[(c.liquidity_rank<=cap)&(c.box_age_sessions<=FRESH[cap])].copy()
        z["pct_up_1d"]=z.confirmation_date.map(lambda d:bmap.get(str(d),{}).get("pct_up_1d",np.nan))
        z["pct_new_20d_low"]=z.confirmation_date.map(lambda d:bmap.get(str(d),{}).get("pct_new_20d_low",np.nan))
        z["year"]=a.year;z["rank_cap"]=cap

        keep=[
          "year","rank_cap","symbol","signal_date","confirmation_date","entry_date","entry_price",
          "lower","upper","liquidity_rank","box_age_sessions",
          "rebound_from_low_box","low_progress_box","pct_up_1d","pct_new_20d_low"
        ]
        z[keep].to_csv(out/f"relative_resilience_candidates_{cap}_{a.year}.csv.gz",
                       index=False,compression="gzip")

        for label,frac in TARGETS.items():
            ev=[]
            for row in z.to_dict("records"):
                rr=large.event_outcome(row,bm,ci,frac)
                if rr is not None:ev.append({**row,"target_fraction":frac,**rr})
            e=pd.DataFrame(ev)
            if len(e):
                e.to_csv(out/f"relative_resilience_events_{cap}_{label}_{a.year}.csv.gz",
                         index=False,compression="gzip")

        receipt["caps"][str(cap)]={
          "confirmed_fresh_large":int(len(z)),
          "non_null":{
            f:int(z[f].notna().sum()) for f in STOCK_FEATURES+MARKET_FEATURES
          }
        }

    (out/f"summary_{a.year}.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
    print(json.dumps(receipt,indent=2))

if __name__=="__main__":
    main()
