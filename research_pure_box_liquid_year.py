#!/usr/bin/env python3
from __future__ import annotations

import argparse, csv, json, math, re, tempfile, time
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl
import requests

HF = "https://huggingface.co/datasets/mito0o852/OHLCV-1m/resolve/main/data/ohlcv_{ym}.parquet"
MAX_YM = (2026, 3)
SIMPLE = re.compile(r"^[A-Z]{1,5}$")
ADV_FLOOR = 25_000_000.0
MAX_RANK = 500
BOTTOM_FRAC = 0.20

def month_iter(year: int):
    vals=[(year-1,m) for m in (10,11,12)]
    for m in range(1,13):
        if (year,m) <= MAX_YM:
            vals.append((year,m))
    return vals

def download(url: str, path: Path) -> bool:
    for attempt in range(4):
        try:
            with requests.get(url,stream=True,timeout=180,allow_redirects=True) as r:
                if r.status_code == 404:
                    return False
                r.raise_for_status()
                with path.open("wb") as fh:
                    for chunk in r.iter_content(4*1024*1024):
                        if chunk: fh.write(chunk)
            return True
        except Exception:
            if attempt == 3: raise
            time.sleep(2+attempt*2)
    return False

def aggregate_month(raw_path: Path, out_path: Path):
    lf=(pl.scan_parquet(raw_path)
        .with_columns(pl.col("timestamp").dt.convert_time_zone("America/New_York").alias("_et"))
        .filter(
            ((pl.col("_et").dt.hour()>9) | ((pl.col("_et").dt.hour()==9)&(pl.col("_et").dt.minute()>=30))) &
            (pl.col("_et").dt.hour()<16)
        )
        .with_columns(pl.col("_et").dt.date().alias("date"))
        .group_by(["ticker","date"])
        .agg([
            pl.col("open").sort_by("timestamp").first().alias("open"),
            pl.col("high").max().alias("high"),
            pl.col("low").min().alias("low"),
            pl.col("close").sort_by("timestamp").last().alias("close"),
            pl.col("volume").sum().alias("volume"),
            pl.len().alias("minute_count"),
        ])
    )
    df=lf.collect(engine="streaming")
    # deterministic duplicate repair used elsewhere in the research repo
    df=(df.sort(["ticker","date","minute_count","volume"])
          .unique(subset=["ticker","date"],keep="last",maintain_order=True)
          .sort(["ticker","date"]))
    df.write_parquet(out_path,compression="zstd")
    return {"rows":df.height,"tickers":df["ticker"].n_unique() if df.height else 0,
            "dates":df["date"].n_unique() if df.height else 0}

def qualifies_window(g: pd.DataFrame, t: int, window: int, max_width_pct: float):
    if t < window-1:
        return None
    z=g.iloc[t-window+1:t+1]
    upper=float(z.high.max()); lower=float(z.low.min())
    center=max((upper+lower)/2,1e-12)
    width_pct=(upper-lower)/center
    if width_pct > max_width_pct or width_pct < .002:
        return None
    if abs(float(z.close.iloc[-1])-float(z.close.iloc[0])) > .55*(upper-lower):
        return None
    width=upper-lower
    touches_upper=int((z.high >= upper-.12*width).sum())
    touches_lower=int((z.low <= lower+.12*width).sum())
    if min(touches_upper,touches_lower) < 2:
        return None
    return lower,upper

def emit_signals_for_symbol(g: pd.DataFrame, year: int):
    rows=[]
    states={
        "small":{"window":20,"maxw":.14,"active":None,"last_break":-1},
        "large":{"window":60,"maxw":.28,"active":None,"last_break":-1},
    }
    g=g.sort_values("date").reset_index(drop=True)
    for t,row in g.iterrows():
        d=str(row.date)[:10]; close=float(row.close)
        rank=None if pd.isna(row.liquidity_rank) else int(row.liquidity_rank)
        for scale,st in states.items():
            a=st["active"]
            if a is not None:
                lo,hi=a["lower"],a["upper"]
                if close < lo*(1-.02) or close > hi*(1+.02):
                    st["active"]=None; st["last_break"]=t; a=None
            if st["active"] is None:
                if t-st["last_break"] >= st["window"] and t >= st["window"]-1:
                    q=qualifies_window(g,t,st["window"],st["maxw"])
                    if q is not None:
                        lo,hi=q
                        st["active"]={"lower":lo,"upper":hi,"detected_at":d}
            a=st["active"]
            if a is None or int(d[:4]) != year or rank is None or rank > MAX_RANK:
                continue
            lo,hi=a["lower"],a["upper"]
            if lo <= close <= lo + BOTTOM_FRAC*(hi-lo):
                rows.append({
                    "signal_date":d,"symbol":str(row.ticker),"scale":scale,
                    "lower":lo,"upper":hi,"close":close,
                    "liquidity_rank":rank,"adv20_prior":float(row.adv20_prior),
                    "detected_at":a["detected_at"],
                })
    return rows

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--year",type=int,required=True)
    ap.add_argument("--outdir",required=True)
    args=ap.parse_args()
    year=args.year; out=Path(args.outdir); out.mkdir(parents=True,exist_ok=True)

    month_meta=[]
    with tempfile.TemporaryDirectory() as td0:
        td=Path(td0); parts=[]
        for y,m in month_iter(year):
            ym=f"{y:04d}-{m:02d}"
            raw=td/f"raw_{ym}.parquet"; daily=td/f"daily_{ym}.parquet"
            ok=download(HF.format(ym=ym),raw)
            if not ok: continue
            meta=aggregate_month(raw,daily); meta["ym"]=ym; month_meta.append(meta)
            parts.append(daily); raw.unlink(missing_ok=True)
        if not parts:
            raise RuntimeError("No source months available")
        daily=pl.concat([pl.read_parquet(p) for p in parts],how="vertical_relaxed")
        daily=(daily.sort(["ticker","date","minute_count","volume"])
                    .unique(subset=["ticker","date"],keep="last",maintain_order=True)
                    .sort(["ticker","date"]))

    daily=daily.with_columns([
        (pl.col("close")*pl.col("volume")).alias("dollar_volume"),
    ]).with_columns([
        pl.col("dollar_volume").shift(1).rolling_mean(window_size=20,min_samples=20).over("ticker").alias("adv20_prior"),
    ])
    pdf=daily.select(["ticker","date","open","high","low","close","volume","adv20_prior","minute_count"]).to_pandas()
    pdf["ticker"]=pdf.ticker.astype(str).str.upper()
    pdf["date"]=pd.to_datetime(pdf.date)
    valid=(pdf.ticker.str.fullmatch(r"[A-Z]{1,5}") & (pdf.close>=5) &
           pdf.adv20_prior.notna() & (pdf.adv20_prior>=ADV_FLOOR))
    ranks=pdf.loc[valid,["date","ticker","adv20_prior"]].sort_values(
        ["date","adv20_prior","ticker"],ascending=[True,False,True]
    )
    ranks["liquidity_rank"]=ranks.groupby("date").cumcount()+1
    pdf=pdf.merge(ranks[["date","ticker","liquidity_rank"]],on=["date","ticker"],how="left")

    # Symbols that were Top500 at least once during warmup+target period.
    leaders=set(pdf.loc[pdf.liquidity_rank.le(MAX_RANK,fill_value=False),"ticker"].unique())
    leaders.add("SPY")  # benchmark/calendar
    x=pdf[pdf.ticker.isin(leaders)].sort_values(["ticker","date"]).copy()

    signals=[]
    for sym,g in x.groupby("ticker",sort=True):
        if sym=="SPY":
            # SPY may still be emitted as a signal if the data source treats it like
            # a listed instrument; keep portfolio stock-like by excluding it here.
            continue
        signals.extend(emit_signals_for_symbol(g,year))

    sig=pd.DataFrame(signals)
    if sig.empty:
        sig=pd.DataFrame(columns=["signal_date","symbol","scale","lower","upper","close","liquidity_rank","adv20_prior","detected_at"])
    sig=sig.sort_values(["signal_date","symbol","scale"]).reset_index(drop=True)
    sig.to_csv(out/f"signals_{year}.csv",index=False)

    # Persist target-year daily bars for any symbol that was a Top500 leader in
    # warmup+year, plus SPY. These remain workflow artifacts only.
    target=x[x.date.dt.year.eq(year)][["date","ticker","open","high","low","close","volume"]].copy()
    target["date"]=target.date.dt.strftime("%Y-%m-%d")
    target.to_csv(out/f"bars_{year}.csv.gz",index=False,compression="gzip")

    summary={
        "schema":"PURE-BOX-LIQUID-LEADERS-YEAR-V1",
        "year":year,
        "source":"mito0o852/OHLCV-1m",
        "months":month_meta,
        "adv_floor":ADV_FLOOR,
        "max_rank":MAX_RANK,
        "leader_symbols":len(leaders)-1,
        "signal_rows":len(sig),
        "signal_symbols":int(sig.symbol.nunique()) if len(sig) else 0,
        "rank_counts":{
            "top200":int((sig.liquidity_rank<=200).sum()) if len(sig) else 0,
            "top300":int((sig.liquidity_rank<=300).sum()) if len(sig) else 0,
            "top500":int((sig.liquidity_rank<=500).sum()) if len(sig) else 0,
        },
        "research_only":True,
        "production_effect":"none",
    }
    (out/f"summary_{year}.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))

if __name__=="__main__":
    main()
