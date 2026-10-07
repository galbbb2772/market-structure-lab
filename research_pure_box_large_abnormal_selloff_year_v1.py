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
 "selloff_1d_atr",
 "selloff_3d_sigma",
 "selloff_5d_sigma",
 "spy_relative_3d_sigma",
 "spy_relative_5d_sigma",
 "own_history_5d_extreme",
]

def feature_maps(bm):
    spy=bm.get("SPY",{})
    spy_close={str(d):float(r["close"]) for d,r in spy.items()}
    out={}
    for sym,mp in bm.items():
        if sym=="SPY": continue
        rows=sorted(mp.values(),key=lambda r:str(r["date"]))
        if not rows: continue
        dates=[str(r["date"]) for r in rows]
        close=np.asarray([float(r["close"]) for r in rows],dtype=float)
        high=np.asarray([float(r["high"]) for r in rows],dtype=float)
        low=np.asarray([float(r["low"]) for r in rows],dtype=float)
        lr=np.full(len(rows),np.nan)
        tr=np.full(len(rows),np.nan)
        for i in range(1,len(rows)):
            lr[i]=math.log(close[i]/close[i-1])
            tr[i]=max(high[i]-low[i],abs(high[i]-close[i-1]),abs(low[i]-close[i-1]))

        vals={}
        for i,d in enumerate(dates):
            f={k:np.nan for k in FEATURES}
            # 1d selloff normalized by ATR14 known at previous close.
            if i>=15:
                atr14=float(np.nanmean(tr[i-14:i]))  # ends t-1
                atrpct=atr14/close[i-1] if close[i-1]>0 else np.nan
                r1=close[i]/close[i-1]-1
                if pd.notna(atrpct) and atrpct>0:
                    f["selloff_1d_atr"]=-r1/atrpct

            for w,name,relname in [
                (3,"selloff_3d_sigma","spy_relative_3d_sigma"),
                (5,"selloff_5d_sigma","spy_relative_5d_sigma"),
            ]:
                pre=i-w
                if pre>=20:
                    hist=lr[pre-19:pre+1]  # 20 returns ending at pre-window close.
                    rv=float(np.nanstd(hist,ddof=0))
                    scale=rv*math.sqrt(w)
                    stock_lr=math.log(close[i]/close[i-w])
                    if scale>0 and math.isfinite(scale):
                        f[name]=-stock_lr/scale
                        sd0=dates[i-w];sd1=d
                        if sd0 in spy_close and sd1 in spy_close and spy_close[sd0]>0:
                            spy_lr=math.log(spy_close[sd1]/spy_close[sd0])
                            f[relname]=-(stock_lr-spy_lr)/scale

            # Current 5d return vs prior non-overlapping own-history 5d returns.
            if i>=10:
                cur=math.log(close[i]/close[i-5])
                hist5=[]
                end_max=i-5
                end_min=max(5,end_max-251)
                for j in range(end_min,end_max+1):
                    if close[j-5]>0:
                        hist5.append(math.log(close[j]/close[j-5]))
                if len(hist5)>=126:
                    pct=sum(x<=cur for x in hist5)/len(hist5)
                    f["own_history_5d_extreme"]=1.0-pct
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
    fm=feature_maps(bm)

    rows=[]
    for r in c.to_dict("records"):
        feat=fm.get(str(r["symbol"]),{}).get(str(r["signal_date"]),{})
        rows.append({**r,**{k:feat.get(k,np.nan) for k in FEATURES}})
    c=pd.DataFrame(rows)
    ci={d:i for i,d in enumerate(cal)}

    receipt={"schema":"LARGE-ABNORMAL-SELLOFF-YEAR-V1","year":a.year,"caps":{}}
    for cap in (300,500):
        z=c[(c.liquidity_rank<=cap)&(c.box_age_sessions<=FRESH[cap])].copy()
        z["year"]=a.year;z["rank_cap"]=cap
        z.to_csv(out/f"abnormal_selloff_candidates_{cap}_{a.year}.csv.gz",index=False,compression="gzip")

        event_n={}
        for label,frac in TARGETS.items():
            ev=[]
            for row in z.to_dict("records"):
                rr=large.event_outcome(row,bm,ci,frac)
                if rr is not None:
                    ev.append({**row,"target_fraction":frac,**rr})
            e=pd.DataFrame(ev)
            event_n[label]=int(len(e))
            if len(e):
                e.to_csv(out/f"abnormal_selloff_events_{cap}_{label}_{a.year}.csv.gz",
                         index=False,compression="gzip")

        receipt["caps"][str(cap)]={
          "confirmed_fresh_large":int(len(z)),
          "events":event_n,
          "feature_nonnull":{f:int(z[f].notna().sum()) for f in FEATURES},
        }

    (out/f"summary_{a.year}.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
    print(json.dumps(receipt,indent=2))

if __name__=="__main__":
    main()
