#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,math
from pathlib import Path
import numpy as np
import pandas as pd
import research_pure_box_large_market_permission_year_v1 as large

TARGETS={"60":.60,"80":.80}
FRESH={300:23,500:24}
FEATURES=["signal_clv","signal_lower_wick","signal_body_recovery","deceleration_1v3","deceleration_2v5","down_day_count_5","signal_volume_ratio20"]

def feature_maps(bm):
    out={}
    for sym,mp in bm.items():
        if sym=="SPY": continue
        rows=sorted(mp.values(),key=lambda r:str(r["date"]))
        if not rows: continue
        dates=[str(r["date"]) for r in rows]
        o=np.asarray([float(r["open"]) for r in rows],float)
        h=np.asarray([float(r["high"]) for r in rows],float)
        l=np.asarray([float(r["low"]) for r in rows],float)
        c=np.asarray([float(r["close"]) for r in rows],float)
        v=np.asarray([float(r["volume"]) for r in rows],float)
        lr=np.full(len(rows),np.nan)
        for i in range(1,len(rows)):
            if c[i-1]>0 and c[i]>0: lr[i]=math.log(c[i]/c[i-1])
        vals={}
        for i,d in enumerate(dates):
            f={k:np.nan for k in FEATURES}
            rng=max(h[i]-l[i],1e-12)
            f["signal_clv"]=(c[i]-l[i])/rng
            f["signal_lower_wick"]=(min(o[i],c[i])-l[i])/rng
            f["signal_body_recovery"]=(c[i]-o[i])/rng
            if i>=2 and np.isfinite(lr[i-2:i+1]).all():
                f["deceleration_1v3"]=lr[i]-float(np.mean(lr[i-2:i]))
            if i>=4 and np.isfinite(lr[i-4:i+1]).all():
                f["deceleration_2v5"]=float(np.mean(lr[i-1:i+1]))-float(np.mean(lr[i-4:i-1]))
                f["down_day_count_5"]=int(np.sum(lr[i-4:i+1]<0))
            if i>=20:
                med=float(np.nanmedian(v[i-20:i]))
                if med>0:f["signal_volume_ratio20"]=v[i]/med
            vals[d]=f
        out[sym]=vals
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--year",type=int,required=True);ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm,spy=large.load(a.indir,a.year);large.CALENDAR=cal
    c=large.confirmed(sig,cal,idx,nxt,bm,{})
    fm=feature_maps(bm)
    rows=[]
    for r in c.to_dict("records"):
        feat=fm.get(str(r["symbol"]),{}).get(str(r["signal_date"]),{})
        rows.append({**r,**{k:feat.get(k,np.nan) for k in FEATURES}})
    c=pd.DataFrame(rows);ci={d:i for i,d in enumerate(cal)}
    rec={"schema":"LARGE-SELLOFF-PATH-YEAR-V2","year":a.year,"caps":{}}
    for cap in (300,500):
        z=c[(c.liquidity_rank<=cap)&(c.box_age_sessions<=FRESH[cap])].copy();z["year"]=a.year;z["rank_cap"]=cap
        z.to_csv(out/f"selloff_path_candidates_{cap}_{a.year}.csv.gz",index=False,compression="gzip")
        ens={}
        for label,frac in TARGETS.items():
            ev=[]
            for row in z.to_dict("records"):
                rr=large.event_outcome(row,bm,ci,frac)
                if rr is not None:ev.append({**row,"target_fraction":frac,**rr})
            e=pd.DataFrame(ev);ens[label]=len(e)
            if len(e):e.to_csv(out/f"selloff_path_events_{cap}_{label}_{a.year}.csv.gz",index=False,compression="gzip")
        rec["caps"][str(cap)]={"confirmed_fresh_large":len(z),"events":ens,"feature_nonnull":{f:int(z[f].notna().sum()) for f in FEATURES}}
    (out/f"summary_{a.year}.json").write_text(json.dumps(rec,indent=2))
    print(json.dumps(rec,indent=2))
if __name__=="__main__":main()
