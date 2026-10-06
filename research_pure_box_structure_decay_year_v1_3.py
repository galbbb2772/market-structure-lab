#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd

TOUCH_FRAC=.12
BOTTOM_FRAC=.20

def integrity_features(g, signal_date, detected_at, lower, upper):
    dates=g["date"].to_numpy(dtype=str)
    i0=int(np.searchsorted(dates, detected_at, side="left"))
    i1=int(np.searchsorted(dates, signal_date, side="right"))
    a=g.iloc[i0:i1]
    if a.empty:
        return None
    width=max(float(upper-lower),1e-12)
    touch=a["low"].to_numpy(float) <= lower + TOUCH_FRAC*width
    bottom=a["close"].to_numpy(float) <= lower + BOTTOM_FRAC*width
    episodes=0
    prev=False
    for v in touch:
        if v and not prev:
            episodes += 1
        prev=bool(v)
    last10=int(touch[-10:].sum())
    last20=int(touch[-20:].sum())
    prev10=int(touch[-20:-10].sum()) if len(touch)>10 else 0
    streak=0
    for v in bottom[::-1]:
        if v: streak+=1
        else: break
    prior=np.where(touch[:-1])[0]
    gap=(len(touch)-1-int(prior[-1])) if len(prior) else np.nan
    return {
        "touch_episodes":int(episodes),
        "touch_days":int(touch.sum()),
        "touch_last10":last10,
        "touch_last20":last20,
        "touch_accel10":last10-prev10,
        "bottom_streak":int(streak),
        "days_since_prior_touch":gap,
        "age_sessions":int(len(a)-1),
        "signal_close_fraction":(float(a.iloc[-1]["close"])-lower)/width,
    }

def path_outcome(g, entry_date, lower, upper, entry_open):
    dates=g["date"].to_numpy(dtype=str)
    j=int(np.searchsorted(dates, entry_date, side="left"))
    if j>=len(g) or dates[j]!=entry_date:
        return None
    out={}
    for h in (5,10):
        k=j+h-1
        out[f"fwd{h}"]=(float(g.iloc[k]["close"])/entry_open-1) if k<len(g) else np.nan
    recs=g.iloc[j:min(len(g),j+20)]
    out["horizon20_complete"]=bool(len(recs)>=20)
    out["mfe20"]=(float(recs["high"].max())/entry_open-1) if len(recs) else np.nan
    out["mae20"]=(float(recs["low"].min())/entry_open-1) if len(recs) else np.nan
    reason="none"; hit_day=np.nan
    for k,r in enumerate(recs.itertuples(index=False), start=1):
        op=float(r.open); lo=float(r.low); hi=float(r.high)
        if op<=lower:
            reason="stop"; hit_day=k; break
        if op>=upper:
            reason="target"; hit_day=k; break
        if lo<=lower:
            reason="stop"; hit_day=k; break
        if hi>=upper:
            reason="target"; hit_day=k; break
    out["first_hit20"]=reason
    out["hit_day20"]=hit_day
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--year",type=int,required=True)
    ap.add_argument("--indir",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    p=Path(a.indir); out=Path(a.outdir); out.mkdir(parents=True,exist_ok=True)
    sigp=next(p.glob(f"**/signals_{a.year}.csv"))
    barps=sorted(p.glob("**/bars_*.csv.gz"))
    if not barps: raise RuntimeError("No bars found")

    sig=pd.read_csv(sigp)
    sig["signal_date"]=sig["signal_date"].astype(str)
    sig["detected_at"]=sig["detected_at"].astype(str)
    sig["symbol"]=sig["symbol"].astype(str)
    sig=sig[sig["liquidity_rank"]<=500].copy()
    sig["ord"]=sig["scale"].map({"small":0,"large":1}).fillna(0)
    sig=sig.sort_values(["signal_date","symbol","ord","detected_at"],
                        ascending=[True,True,False,False]).drop_duplicates(["signal_date","symbol"],keep="first")
    symbols=set(sig["symbol"])

    kept=[]; all_dates=set()
    for barsp in barps:
        for ch in pd.read_csv(barsp,chunksize=300000):
            ch["date"]=ch["date"].astype(str)
            all_dates.update(ch["date"].unique().tolist())
            z=ch[ch["ticker"].astype(str).isin(symbols)].copy()
            if len(z): kept.append(z)
    bars=pd.concat(kept,ignore_index=True)
    bars["ticker"]=bars["ticker"].astype(str)
    bars["date"]=bars["date"].astype(str)
    bars=bars.sort_values(["ticker","date"]).drop_duplicates(["ticker","date"],keep="last")
    by={s:g.reset_index(drop=True) for s,g in bars.groupby("ticker")}
    cal=sorted(all_dates)
    nxt={cal[i]:cal[i+1] for i in range(len(cal)-1)}

    rows=[]
    for q in sig.to_dict("records"):
        g=by.get(q["symbol"])
        if g is None: continue
        ed=nxt.get(q["signal_date"])
        if ed is None: continue
        dates=g["date"].to_numpy(dtype=str)
        j=int(np.searchsorted(dates,ed,side="left"))
        if j>=len(g) or dates[j]!=ed: continue
        op=float(g.iloc[j]["open"]); lo=float(q["lower"]); hi=float(q["upper"])
        if not (lo<op<hi): continue
        history_complete=bool(len(dates)>0 and dates[0] <= q["detected_at"])
        f=integrity_features(g,q["signal_date"],q["detected_at"],lo,hi)
        if f is None: continue
        o=path_outcome(g,ed,lo,hi,op)
        if o is None: continue
        rows.append({
            **q,**f,**o,
            "entry_date":ed,
            "entry_open":op,
            "box_width_pct":(hi-lo)/op,
            "history_complete":history_complete,
            "year":a.year,
        })

    x=pd.DataFrame(rows)
    if len(x):
        x=x.sort_values(["symbol","detected_at","scale","lower","upper","touch_episodes","signal_date"])
        x=x.drop_duplicates(["symbol","detected_at","scale","lower","upper","touch_episodes"],keep="first")
    x.to_csv(out/f"structure_decay_audit_{a.year}.csv.gz",index=False,compression="gzip")
    summary={
        "schema":"STRUCTURE-DECAY-YEAR-V1.3-AUDIT",
        "year":a.year,
        "raw_signals":int(len(sig)),
        "episode_observations":int(len(x)),
        "top300_observations":int((x["liquidity_rank"]<=300).sum()) if len(x) else 0,
        "top500_observations":int(len(x)),
        "history_complete_observations":int(x["history_complete"].sum()) if len(x) else 0,
        "horizon20_complete_observations":int(x["horizon20_complete"].sum()) if len(x) else 0,
    }
    (out/f"summary_audit_{a.year}.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))

if __name__=="__main__":
    main()
