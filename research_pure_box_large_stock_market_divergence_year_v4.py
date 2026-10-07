#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd

import research_pure_box_large_market_permission_year_v1 as large
import research_pure_box_breadth_permission_v1 as breadthmod

TARGETS=(.60,.80)
FRESH={300:23,500:24}
STOCK_FEATURES=["rebound_from_low_box","low_progress_box"]

def load_bars(indir):
    p=Path(indir);parts=[]
    for bp in sorted(p.glob("**/bars_*.csv.gz")):
        for ch in pd.read_csv(bp,chunksize=300000):
            ch["date"]=ch.date.astype(str);ch["ticker"]=ch.ticker.astype(str)
            parts.append(ch)
    x=pd.concat(parts,ignore_index=True)
    return x.sort_values(["ticker","date"]).drop_duplicates(["ticker","date"],keep="last")

def stock_features(row,bm):
    sm=bm.get(str(row["symbol"]),{})
    b0=sm.get(str(row["signal_date"]))
    b1=sm.get(str(row["confirmation_date"]))
    if b0 is None or b1 is None:return None
    lo=float(row["lower"]);hi=float(row["upper"]);w=max(hi-lo,1e-12)
    s_low=float(b0["low"]);c_low=float(b1["low"]);c_close=float(b1["close"])
    return {
      "rebound_from_low_box":(c_close-min(s_low,c_low))/w,
      "low_progress_box":(c_low-s_low)/w,
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--year",type=int,required=True)
    ap.add_argument("--indir",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

    sig,cal,idx,nxt,bm,_=large.load(a.indir,a.year)
    large.CALENDAR=cal
    bars=load_bars(a.indir)
    c=large.confirmed(sig,cal,idx,nxt,bm,{})
    c=c[c.scale=="large"].copy()
    ci={d:i for i,d in enumerate(cal)}

    receipt={"schema":"LARGE-STOCK-MARKET-DIVERGENCE-YEAR-V4","year":a.year,"caps":{}}

    for cap in (300,500):
        b=breadthmod.build_breadth(bars,cap)
        bmap={str(r["date"]):r for r in b.to_dict("records")}
        z=c[(c.liquidity_rank<=cap)&(c.box_age_sessions<=FRESH[cap])].copy()
        feats=[]
        for r in z.to_dict("records"):
            f=stock_features(r,bm)
            feats.append(f or {k:np.nan for k in STOCK_FEATURES})
        for feat in STOCK_FEATURES:
            z[feat]=[f[feat] for f in feats]
        z["pct_up_1d"]=z.confirmation_date.map(lambda d:bmap.get(str(d),{}).get("pct_up_1d",np.nan))
        z["market_state"]=np.where(
            z.pct_up_1d.notna(),
            np.where(z.pct_up_1d>=.50,"STRONG_MARKET_DAY","WEAK_MARKET_DAY"),
            None
        )
        keep=["year","rank_cap","symbol","signal_date","confirmation_date","entry_date","entry_price",
              "lower","upper","liquidity_rank","box_age_sessions","pct_up_1d","market_state"]+STOCK_FEATURES
        zz=z.copy();zz["year"]=a.year;zz["rank_cap"]=cap
        zz[keep].to_csv(out/f"candidates_{cap}_{a.year}.csv.gz",index=False,compression="gzip")

        receipt["caps"][str(cap)]={
          "confirmed_fresh_large":int(len(z)),
          "market_classified":int(z.market_state.notna().sum()),
          "stock_feature_nonnull":{f:int(z[f].notna().sum()) for f in STOCK_FEATURES}
        }

        for target in TARGETS:
            ev=[]
            for r in z.to_dict("records"):
                x=large.event_outcome(r,bm,ci,target)
                if x is not None:ev.append({**r,"year":a.year,"rank_cap":cap,"target_fraction":target,**x})
            e=pd.DataFrame(ev)
            if len(e):
                cols=["year","rank_cap","target_fraction","symbol","signal_date","confirmation_date","entry_date",
                      "entry_price","lower","upper","liquidity_rank","box_age_sessions","pct_up_1d","market_state",
                      "rebound_from_low_box","low_progress_box","exit_reason","holding_sessions","net_return",
                      "mfe_return","mae_return"]
                e[cols].to_csv(out/f"events_{cap}_{int(target*100)}_{a.year}.csv.gz",
                               index=False,compression="gzip")

    (out/f"summary_{a.year}.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
    print(json.dumps(receipt,indent=2))

if __name__=="__main__":
    main()
