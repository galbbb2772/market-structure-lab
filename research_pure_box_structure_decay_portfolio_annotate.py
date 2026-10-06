#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd

TOUCH_FRAC=.12
BOTTOM_FRAC=.20

def features(g, signal_date, detected_at, lower, upper):
    dates=g["date"].to_numpy(dtype=str)
    i0=int(np.searchsorted(dates,detected_at,side="left"))
    i1=int(np.searchsorted(dates,signal_date,side="right"))
    a=g.iloc[i0:i1]
    if a.empty:return None
    width=max(float(upper-lower),1e-12)
    touch=a["low"].to_numpy(float)<=lower+TOUCH_FRAC*width
    episodes=0;prev=False
    for v in touch:
        if v and not prev:episodes+=1
        prev=bool(v)
    return {
      "touch_episodes":int(episodes),
      "age_sessions":int(len(a)-1),
      "touch_days":int(touch.sum()),
      "touch_last10":int(touch[-10:].sum()),
      "signal_close_fraction":(float(a.iloc[-1]["close"])-lower)/width,
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--year",type=int,required=True)
    ap.add_argument("--indir",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    p=Path(a.indir);out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sigp=next(p.glob(f"**/signals_{a.year}.csv"))
    barsp=next(p.glob(f"**/bars_{a.year}.csv.gz"))

    sig=pd.read_csv(sigp)
    sig["signal_date"]=sig.signal_date.astype(str)
    sig["detected_at"]=sig.detected_at.astype(str)
    sig["symbol"]=sig.symbol.astype(str)
    sig=sig[sig.liquidity_rank<=500].copy()
    sig["ord"]=sig.scale.map({"small":0,"large":1}).fillna(0)
    sig=sig.sort_values(["signal_date","symbol","ord","detected_at"],
                        ascending=[True,True,False,False]).drop_duplicates(["signal_date","symbol"],keep="first")
    symbols=set(sig.symbol)

    parts=[]
    for ch in pd.read_csv(barsp,chunksize=300000):
        ch["ticker"]=ch.ticker.astype(str)
        z=ch[ch.ticker.isin(symbols)].copy()
        if len(z):
            z["date"]=z.date.astype(str)
            parts.append(z)
    bars=pd.concat(parts,ignore_index=True)
    bars=bars.sort_values(["ticker","date"]).drop_duplicates(["ticker","date"],keep="last")
    by={s:g.reset_index(drop=True) for s,g in bars.groupby("ticker")}

    rows=[]
    for q in sig.to_dict("records"):
        g=by.get(q["symbol"])
        if g is None:continue
        f=features(g,q["signal_date"],q["detected_at"],float(q["lower"]),float(q["upper"]))
        if f is None:continue
        rows.append({**q,**f})
    x=pd.DataFrame(rows)
    x.to_csv(out/f"annotated_signals_{a.year}.csv.gz",index=False,compression="gzip")
    summary={"schema":"STRUCTURE-DECAY-PORTFOLIO-ANNOTATION-V1.2","year":a.year,
             "rows":int(len(x)),"top300":int((x.liquidity_rank<=300).sum()) if len(x) else 0}
    (out/f"summary_{a.year}.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))

if __name__=="__main__":main()
