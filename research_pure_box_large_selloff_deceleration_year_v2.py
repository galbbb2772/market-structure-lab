#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math
from pathlib import Path
import numpy as np
import pandas as pd
import research_pure_box_large_market_permission_year_v1 as large

TARGETS={"60":.60,"80":.80}
FRESH={300:23,500:24}
FEATURES=[
 "ret3_deceleration","downside_body_decay","signal_clv","signal_lower_wick",
 "low_extension_deceleration","close_reclaim_acceleration"
]

def body_frac(b):
    rng=max(float(b["high"])-float(b["low"]),1e-12)
    return max(float(b["open"])-float(b["close"]),0.0)/rng

def extract_features(r,cal,ci,bm):
    sym=str(r["symbol"]);d0=str(r["signal_date"]);d1=str(r["confirmation_date"])
    sm=bm.get(sym,{})
    i=ci.get(d0)
    if i is None or i<6:return None
    needed=[cal[i-k] for k in range(0,7)]
    if any(d not in sm for d in needed) or d1 not in sm:return None
    s=sm[d0];c=sm[d1];p1=sm[cal[i-1]]
    p3=sm[cal[i-3]];p6=sm[cal[i-6]]
    width=max(float(r["upper"])-float(r["lower"]),1e-12)

    recent3=math.log(float(s["close"])/float(p3["close"]))
    prev3=math.log(float(p3["close"])/float(p6["close"]))
    prev_body=np.mean([body_frac(sm[cal[i-k]]) for k in (1,2,3)])
    sig_body=body_frac(s)
    srng=max(float(s["high"])-float(s["low"]),1e-12)

    return {
      "ret3_deceleration":recent3-prev3,
      "downside_body_decay":float(prev_body-sig_body),
      "signal_clv":(float(s["close"])-float(s["low"]))/srng,
      "signal_lower_wick":(min(float(s["open"]),float(s["close"]))-float(s["low"]))/srng,
      "low_extension_deceleration":((float(c["low"])-float(s["low"]))-(float(s["low"])-float(p1["low"])))/width,
      "close_reclaim_acceleration":((float(c["close"])-float(s["close"]))-(float(s["close"])-float(p1["close"])))/width,
    }

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
    ci={d:i for i,d in enumerate(cal)}
    rows=[]
    for r in c.to_dict("records"):
        f=extract_features(r,cal,ci,bm)
        if f is not None: rows.append({**r,**f})
    c=pd.DataFrame(rows)

    receipt={"schema":"LARGE-SELLOFF-DECELERATION-YEAR-V2","year":a.year,"caps":{}}
    for cap in (300,500):
        z=c[(c.liquidity_rank<=cap)&(c.box_age_sessions<=FRESH[cap])].copy()
        z["year"]=a.year;z["rank_cap"]=cap
        z.to_csv(out/f"deceleration_candidates_{cap}_{a.year}.csv.gz",index=False,compression="gzip")
        event_n={}
        for label,frac in TARGETS.items():
            ev=[]
            for row in z.to_dict("records"):
                rr=large.event_outcome(row,bm,ci,frac)
                if rr is not None:ev.append({**row,"target_fraction":frac,**rr})
            e=pd.DataFrame(ev);event_n[label]=int(len(e))
            if len(e):e.to_csv(out/f"deceleration_events_{cap}_{label}_{a.year}.csv.gz",index=False,compression="gzip")
        receipt["caps"][str(cap)]={"confirmed":int(len(z)),"events":event_n,"feature_nonnull":{f:int(z[f].notna().sum()) for f in FEATURES}}
    (out/f"summary_{a.year}.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
    print(json.dumps(receipt,indent=2))

if __name__=="__main__":
    main()
