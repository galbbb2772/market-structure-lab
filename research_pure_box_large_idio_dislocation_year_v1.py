#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math
from pathlib import Path
import numpy as np
import pandas as pd
import research_pure_box_large_market_permission_year_v1 as base

TARGETS={"60":.60,"80":.80}

def feature_for(row,cal,idx,bm):
    d=str(row["confirmation_date"]);i=idx.get(d)
    if i is None:return None
    sm=bm.get(str(row["symbol"]),{});spy=bm.get("SPY",{})
    sr=[];mr=[]
    start=max(1,i-90)
    for k in range(start,i+1):
        d0=cal[k-1];d1=cal[k]
        s0=sm.get(d0);s1=sm.get(d1);m0=spy.get(d0);m1=spy.get(d1)
        if None in (s0,s1,m0,m1):continue
        sc0=float(s0["close"]);sc1=float(s1["close"]);mc0=float(m0["close"]);mc1=float(m1["close"])
        if sc0<=0 or mc0<=0:continue
        sr.append(sc1/sc0-1);mr.append(mc1/mc0-1)
    if len(sr)<45:return None
    sr=np.array(sr[-60:],float);mr=np.array(mr[-60:],float)
    vv=float(np.var(mr,ddof=1))
    if not math.isfinite(vv) or vv<=1e-12:return None
    beta=float(np.cov(sr,mr,ddof=1)[0,1]/vv)
    def ret_n(mp,n):
        if i-n<0:return np.nan
        a=mp.get(cal[i-n]);b=mp.get(cal[i])
        if a is None or b is None:return np.nan
        ca=float(a["close"]);cb=float(b["close"])
        return cb/ca-1 if ca>0 else np.nan
    s5=ret_n(sm,5);s20=ret_n(sm,20);m5=ret_n(spy,5);m20=ret_n(spy,20)
    return {
      "beta60":beta,
      "stock_ret5":s5,"stock_ret20":s20,"spy_ret5":m5,"spy_ret20_local":m20,
      "idio_dislocation_5d":-(s5-beta*m5) if pd.notna(s5) and pd.notna(m5) else np.nan,
      "idio_dislocation_20d":-(s20-beta*m20) if pd.notna(s20) and pd.notna(m20) else np.nan,
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--year",type=int,required=True)
    ap.add_argument("--indir",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

    sig,cal,idx,nxt,bm,spy=base.load(a.indir,a.year)
    base.CALENDAR=cal
    regs=base.regime_map(spy)
    c=base.confirmed(sig,cal,idx,nxt,bm,regs)
    ci={d:i for i,d in enumerate(cal)}
    rows=[]
    feature_ok=0
    for q in c.to_dict("records"):
        f=feature_for(q,cal,idx,bm)
        if f is None:continue
        feature_ok+=1
        for label,frac in TARGETS.items():
            rr=base.event_outcome(q,bm,ci,frac)
            if rr is None:continue
            rows.append({
              "year":a.year,"target_fraction":frac,
              "symbol":q["symbol"],"signal_date":q["signal_date"],
              "confirmation_date":q["confirmation_date"],"entry_date":q["entry_date"],
              "liquidity_rank":q["liquidity_rank"],"box_age_sessions":q["box_age_sessions"],
              **f,**rr
            })
    x=pd.DataFrame(rows)
    x.to_csv(out/f"idio_dislocation_{a.year}.csv.gz",index=False,compression="gzip")
    receipt={
      "schema":"LARGE-IDIO-DISLOCATION-YEAR-V1",
      "year":a.year,"confirmed_large":int(len(c)),
      "feature_usable_events":feature_ok,"outcome_rows":int(len(x))
    }
    (out/f"summary_{a.year}.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
    print(json.dumps(receipt,indent=2))

if __name__=="__main__":
    main()
