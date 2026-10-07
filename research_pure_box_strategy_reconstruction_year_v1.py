#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math
from pathlib import Path
import numpy as np
import pandas as pd

TARGETS={"50":.50,"60":.60,"80":.80,"100":1.00}
HORIZONS=(10,20,40)

def path_metrics(g, entry_date, entry_price, lower, upper):
    dates=g["date"].to_numpy(dtype=str)
    j=int(np.searchsorted(dates,entry_date,side="left"))
    out={}
    if j>=len(g) or dates[j]!=entry_date:
        return None
    width=max(upper-lower,1e-12)
    for h in HORIZONS:
        z=g.iloc[j:min(len(g),j+h)]
        out[f"h{h}_complete"]=bool(len(z)>=h)
        if len(z):
            out[f"mfe_progress_{h}"]=(float(z["high"].max())-lower)/width
            out[f"mae_return_{h}"]=float(z["low"].min())/entry_price-1
        else:
            out[f"mfe_progress_{h}"]=np.nan
            out[f"mae_return_{h}"]=np.nan
    for h in (5,10):
        k=j+h-1
        out[f"fwd{h}_return"]=float(g.iloc[k]["close"])/entry_price-1 if k<len(g) else np.nan

    maxz=g.iloc[j:min(len(g),j+40)]
    for label,frac in TARGETS.items():
        target=lower+frac*width
        out[f"t{label}_eligible"]=bool(entry_price<target)
        out[f"t{label}_target_return"]=target/entry_price-1 if entry_price<target else np.nan
        if entry_price>=target:
            out[f"t{label}_event"]="ineligible"
            out[f"t{label}_event_day"]=np.nan
            continue
        event="unresolved";event_day=np.nan
        for k,r in enumerate(maxz.itertuples(index=False),start=1):
            op=float(r.open);lo=float(r.low);hi=float(r.high)
            if op<=lower:
                event="stop";event_day=k;break
            if op>=target:
                event="target";event_day=k;break
            if lo<=lower:
                event="stop";event_day=k;break
            if hi>=target:
                event="target";event_day=k;break
        out[f"t{label}_event"]=event
        out[f"t{label}_event_day"]=event_day
    return out

def confirmation_features(g, signal_date, confirmation_date, lower, upper):
    dates=g["date"].to_numpy(dtype=str)
    i0=int(np.searchsorted(dates,signal_date,side="left"))
    i1=int(np.searchsorted(dates,confirmation_date,side="left"))
    if i0>=len(g) or i1>=len(g) or dates[i0]!=signal_date or dates[i1]!=confirmation_date:
        return None
    s=g.iloc[i0];c=g.iloc[i1];width=max(upper-lower,1e-12)
    cr=max(float(c.high)-float(c.low),1e-12)
    sr=max(float(s.high)-float(s.low),1e-12)
    prior20=g.iloc[max(0,i1-20):i1]
    volmed=float(prior20.volume.median()) if len(prior20)>=10 else np.nan
    i5=i0-5
    sell5=float(s.close)/float(g.iloc[i5].close)-1 if i5>=0 else np.nan
    return {
      "low_progress_box":(float(c.low)-float(s.low))/width,
      "rebound_from_low_box":(float(c.close)-min(float(s.low),float(c.low)))/width,
      "range_ratio":cr/sr,
      "confirmation_clv":(float(c.close)-float(c.low))/cr,
      "volume_ratio20":float(c.volume)/volmed if pd.notna(volmed) and volmed>0 else np.nan,
      "selloff_5d":sell5,
      "confirmation_body_box":(float(c.close)-float(c.open))/width,
    }

def load_year(indir,year):
    p=Path(indir)
    sigp=next(p.glob(f"**/signals_{year}.csv"))
    sig=pd.read_csv(sigp)
    sig["signal_date"]=sig.signal_date.astype(str)
    sig["detected_at"]=sig.detected_at.astype(str)
    sig["symbol"]=sig.symbol.astype(str)
    sig=sig[sig.liquidity_rank<=500].copy()
    sig["scale_order"]=sig.scale.map({"small":0,"large":1}).fillna(0)
    sig=sig.sort_values(["signal_date","symbol","scale_order","detected_at"],
                        ascending=[True,True,False,False]).drop_duplicates(
                            ["signal_date","symbol"],keep="first"
                        )
    syms=set(sig.symbol)
    kept=[];dates=set()
    for bp in sorted(p.glob("**/bars_*.csv.gz")):
        for ch in pd.read_csv(bp,chunksize=300000):
            ch["date"]=ch.date.astype(str)
            dates.update(ch.date.unique().tolist())
            z=ch[ch.ticker.astype(str).isin(syms)].copy()
            if len(z):kept.append(z)
    bars=pd.concat(kept,ignore_index=True)
    bars["ticker"]=bars.ticker.astype(str)
    bars["date"]=bars.date.astype(str)
    bars=bars.sort_values(["ticker","date"]).drop_duplicates(["ticker","date"],keep="last")
    cal=sorted(dates);idx={d:i for i,d in enumerate(cal)}
    nxt={cal[i]:cal[i+1] for i in range(len(cal)-1)}
    by={s:g.reset_index(drop=True) for s,g in bars.groupby("ticker")}
    return sig,cal,idx,nxt,by

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--year",type=int,required=True)
    ap.add_argument("--indir",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

    vit=json.load(open("research/pure_box_liquid_leaders_v1/vitality_v2/summary.json"))
    th={}
    for cap in (300,500):
        ann=vit["rank_caps"][f"top{cap}"]["annual_walk_forward"]
        row=next(x for x in ann if int(x["year"])==a.year)
        th[cap]=row["thresholds"]

    sig,cal,idx,nxt,by=load_year(a.indir,a.year)
    rows=[]
    for q in sig.to_dict("records"):
        g=by.get(q["symbol"])
        if g is None:continue
        d0=q["signal_date"];d1=nxt.get(d0)
        if d1 is None:continue
        dates=g["date"].to_numpy(dtype=str)
        j0=int(np.searchsorted(dates,d0,side="left"))
        j1=int(np.searchsorted(dates,d1,side="left"))
        if j0>=len(g) or j1>=len(g) or dates[j0]!=d0 or dates[j1]!=d1:continue
        b0=g.iloc[j0];b1=g.iloc[j1]
        lo=float(q["lower"]);hi=float(q["upper"]);op1=float(b1.open)
        if not(lo<op1<hi):continue
        age=max(0,idx[d0]-idx.get(q["detected_at"],idx[d0]))
        common={
          **q,"lower":lo,"upper":hi,"box_age_sessions":age,
          "box_width_pct":(hi-lo)/op1,
          "fresh_top300":bool(q["liquidity_rank"]<=300 and age<=th[300][q["scale"]]["am"]),
          "fresh_top500":bool(q["liquidity_rank"]<=500 and age<=th[500][q["scale"]]["am"]),
        }
        pm=path_metrics(g,d1,op1,lo,hi)
        if pm is not None:
            rows.append({**common,"stage":"raw_bottom_signal","entry_date":d1,"entry_price":op1,**pm})

        d2=nxt.get(d1)
        if d2 is None:continue
        j2=int(np.searchsorted(dates,d2,side="left"))
        if j2>=len(g) or dates[j2]!=d2:continue
        b2=g.iloc[j2];op2=float(b2.open)
        if not(lo<op2<hi):continue
        if float(b1.low)<float(b0.low):continue
        if float(b1.close)<=float(b1.open):continue
        feats=confirmation_features(g,d0,d1,lo,hi)
        if feats is None:continue
        pm2=path_metrics(g,d2,op2,lo,hi)
        if pm2 is None:continue
        rows.append({**common,"stage":"confirmed_no_new_low_green",
                     "confirmation_date":d1,"entry_date":d2,"entry_price":op2,
                     **feats,**pm2})

    x=pd.DataFrame(rows)
    x.to_csv(out/f"strategy_reconstruction_{a.year}.csv.gz",index=False,compression="gzip")
    receipt={
      "schema":"STRATEGY-RECONSTRUCTION-YEAR-V1",
      "year":a.year,
      "raw_source_signals":int(len(sig)),
      "observations":int(len(x)),
      "raw_stage":int((x.stage=="raw_bottom_signal").sum()) if len(x) else 0,
      "confirmed_stage":int((x.stage=="confirmed_no_new_low_green").sum()) if len(x) else 0,
    }
    (out/f"summary_{a.year}.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
    print(json.dumps(receipt,indent=2))

if __name__=="__main__":
    main()
