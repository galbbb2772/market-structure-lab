#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd

import research_pure_box_large_market_permission_year_v1 as large

TARGETS={"60":.60,"80":.80}
FRESH={300:23,500:24}
FEATURES=[
 "gap_component","intraday_component","close_recovery_from_low",
 "downside_wick_fraction","volume_ratio20","gap_share_of_negative_move"
]

def anatomy_map(bm):
    out={}
    for sym,mp in bm.items():
        if sym=="SPY": continue
        rows=sorted(mp.values(),key=lambda r:str(r["date"]))
        if not rows: continue
        vals={}
        for i,r in enumerate(rows):
            d=str(r["date"])
            f={k:np.nan for k in FEATURES}
            if i<1:
                vals[d]=f;continue
            prev_close=float(rows[i-1]["close"])
            op=float(r["open"]);hi=float(r["high"]);lo=float(r["low"]);cl=float(r["close"])
            rng=max(hi-lo,1e-12)
            gap=op/prev_close-1 if prev_close>0 else np.nan
            intra=cl/op-1 if op>0 else np.nan
            f["gap_component"]=gap
            f["intraday_component"]=intra
            f["close_recovery_from_low"]=(cl-lo)/rng
            f["downside_wick_fraction"]=(min(op,cl)-lo)/rng
            if i>=20:
                vols=[float(rows[j]["volume"]) for j in range(i-20,i)]
                med=float(np.median(vols))
                f["volume_ratio20"]=float(r["volume"])/med if med>0 else np.nan
            total=cl/prev_close-1 if prev_close>0 else np.nan
            if pd.notna(total) and total<0 and pd.notna(gap) and pd.notna(intra):
                ng=abs(min(gap,0.0));ni=abs(min(intra,0.0))
                f["gap_share_of_negative_move"]=ng/(ng+ni+1e-12)
            vals[d]=f
        out[sym]=vals
    return out

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
    amap=anatomy_map(bm)
    rows=[]
    for r in c.to_dict("records"):
        f=amap.get(str(r["symbol"]),{}).get(str(r["signal_date"]),{})
        rows.append({**r,**{k:f.get(k,np.nan) for k in FEATURES}})
    c=pd.DataFrame(rows)
    ci={d:i for i,d in enumerate(cal)}

    receipt={"schema":"LARGE-SELLOFF-ANATOMY-YEAR-V2","year":a.year,"caps":{}}
    for cap in (300,500):
        z=c[(c.liquidity_rank<=cap)&(c.box_age_sessions<=FRESH[cap])].copy()
        z["year"]=a.year;z["rank_cap"]=cap
        z.to_csv(out/f"selloff_anatomy_candidates_{cap}_{a.year}.csv.gz",index=False,compression="gzip")
        ens={}
        for label,frac in TARGETS.items():
            ev=[]
            for row in z.to_dict("records"):
                rr=large.event_outcome(row,bm,ci,frac)
                if rr is not None:ev.append({**row,"target_fraction":frac,**rr})
            e=pd.DataFrame(ev);ens[label]=int(len(e))
            if len(e):
                e.to_csv(out/f"selloff_anatomy_events_{cap}_{label}_{a.year}.csv.gz",index=False,compression="gzip")
        receipt["caps"][str(cap)]={
          "confirmed_fresh_large":int(len(z)),
          "events":ens,
          "feature_nonnull":{f:int(z[f].notna().sum()) for f in FEATURES},
        }
    (out/f"summary_{a.year}.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
    print(json.dumps(receipt,indent=2))

if __name__=="__main__":
    main()
