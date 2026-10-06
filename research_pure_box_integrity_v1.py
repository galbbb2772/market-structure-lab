#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math, statistics
from collections import defaultdict
from datetime import date
from pathlib import Path
import numpy as np
import pandas as pd

ENTRY_COST=.0005
EXIT_COST=.0005
TARGET_WEIGHT={"small":.5,"large":1.0}
ADV_FLOOR=25_000_000.0
YEARS=(2021,2022,2023,2024,2025,2026)
GATES=["all","low_consumption","not_clustered","short_bottom_streak","integrity_core",
       "no_fast_breadth_break","no_medium_breadth_break","no_newlow_acceleration",
       "deterioration_core","integrity_plus_fast_breadth","integrity_plus_deterioration_core"]

def pf(rs):
    w=sum(x for x in rs if x>0);l=-sum(x for x in rs if x<0)
    return w/l if l>0 else None
def mdd(vals):
    p=vals[0];d=0
    for x in vals:p=max(p,x);d=min(d,x/p-1)
    return d
def sharpe(eq):
    r=[eq[i][1]/eq[i-1][1]-1 for i in range(1,len(eq)) if eq[i-1][1]>0]
    if len(r)<2:return None
    s=statistics.stdev(r)
    return None if s==0 else statistics.mean(r)/s*math.sqrt(252)

def load(indir):
    p=Path(indir)
    bars=pd.concat([pd.read_csv(x) for x in sorted(p.glob("**/bars_*.csv.gz"))],ignore_index=True)
    bars["date"]=bars.date.astype(str);bars["ticker"]=bars.ticker.astype(str)
    bars=bars.sort_values(["ticker","date"]).drop_duplicates(["ticker","date"],keep="last")
    sig=pd.concat([pd.read_csv(x) for x in sorted(p.glob("**/signals_*.csv"))],ignore_index=True)
    sig["signal_date"]=sig.signal_date.astype(str);sig["symbol"]=sig.symbol.astype(str)
    spy=bars[bars.ticker=="SPY"].sort_values("date")
    cal=spy.date.tolist();idx={d:i for i,d in enumerate(cal)}
    nxt={cal[i]:cal[i+1] for i in range(len(cal)-1)}
    bm={s:g.sort_values("date").reset_index(drop=True) for s,g in bars.groupby("ticker")}
    bmd={s:{r["date"]:r for r in g.to_dict("records")} for s,g in bm.items()}
    return bars,sig,cal,idx,nxt,bm,bmd

def build_breadth(bars,cap):
    x=bars[bars.ticker!="SPY"].copy().sort_values(["ticker","date"])
    x["dollar_volume"]=x.close*x.volume
    gp=x.groupby("ticker",group_keys=False)
    x["adv20_prior"]=gp.dollar_volume.transform(lambda s:s.shift(1).rolling(20,min_periods=20).mean())
    x["ma50"]=gp.close.transform(lambda s:s.rolling(50,min_periods=50).mean())
    x["ret20"]=gp.close.pct_change(20)
    x["prior20_low"]=gp.close.transform(lambda s:s.shift(1).rolling(20,min_periods=20).min())
    valid=(x.close>=5)&x.adv20_prior.notna()&(x.adv20_prior>=ADV_FLOOR)
    z=x.loc[valid].sort_values(["date","adv20_prior","ticker"],ascending=[True,False,True]).copy()
    z["liq_rank"]=z.groupby("date").cumcount()+1
    z=z[z.liq_rank<=cap]
    rows=[]
    for d,g in z.groupby("date",sort=True):
        rows.append({"date":d,
          "pct_above_ma50":float((g.close>=g.ma50).mean()),
          "pct_ret20_positive":float((g.ret20>0).mean()),
          "pct_new_20d_low":float((g.close<=g.prior20_low).mean())})
    b=pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    for n in (5,10,20):
        b[f"d{n}_ma50"]=b.pct_above_ma50-b.pct_above_ma50.shift(n)
        b[f"d{n}_ret20breadth"]=b.pct_ret20_positive-b.pct_ret20_positive.shift(n)
    for n in (5,10):
        b[f"d{n}_newlow"]=b.pct_new_20d_low-b.pct_new_20d_low.shift(n)
    return b

def integrity_features(symdf,signal_date,detected_at,lower,upper):
    g=symdf
    arr=g[(g.date>=detected_at)&(g.date<=signal_date)].copy()
    if arr.empty:
        return dict(post_detection_lower_touch_days=0,post_detection_lower_touch_episodes=0,
                    touch_days_last10=0,touch_days_last20=0,days_since_prior_lower_touch=np.nan,
                    lower_zone_close_streak=0,signal_close_fraction=np.nan)
    width=max(upper-lower,1e-12)
    arr["touch"]=arr.low<=lower+.12*width
    arr["bottom_close"]=arr.close<=lower+.20*width
    touches=arr.touch.astype(bool).tolist()
    episodes=0;prev=False
    for t in touches:
        if t and not prev:episodes+=1
        prev=t
    last10=int(arr.tail(10).touch.sum());last20=int(arr.tail(20).touch.sum())
    touch_idx=[i for i,v in enumerate(touches) if v]
    # sessions since touch before the final session, if any
    prior=[i for i in touch_idx if i<len(arr)-1]
    days_since=(len(arr)-1-prior[-1]) if prior else np.nan
    streak=0
    for v in reversed(arr.bottom_close.astype(bool).tolist()):
        if v:streak+=1
        else:break
    close=float(arr.iloc[-1].close)
    return {
      "post_detection_lower_touch_days":int(sum(touches)),
      "post_detection_lower_touch_episodes":int(episodes),
      "touch_days_last10":last10,
      "touch_days_last20":last20,
      "days_since_prior_lower_touch":days_since,
      "lower_zone_close_streak":int(streak),
      "signal_close_fraction":(close-lower)/width
    }

def build_candidates(sig,cap,nxt,bm,bmd,idx,breadth_map):
    s=sig[sig.liquidity_rank<=cap].copy()
    s["ord"]=s.scale.map({"small":0,"large":1}).fillna(0)
    s=s.sort_values(["signal_date","symbol","ord","detected_at"],ascending=[True,True,False,False]).drop_duplicates(["signal_date","symbol"],keep="first")
    out=[]
    for q in s.to_dict("records"):
        ed=nxt.get(q["signal_date"]);bar=bmd.get(q["symbol"],{}).get(ed) if ed else None
        if bar is None:continue
        op=float(bar["open"]);lo=float(q["lower"]);hi=float(q["upper"])
        if not(lo<op<hi):continue
        feats=integrity_features(bm[q["symbol"]],q["signal_date"],str(q["detected_at"]),lo,hi)
        br=breadth_map.get(q["signal_date"])
        out.append({**q,**feats,"entry_date":ed,"entry_price":op,"lower":lo,"upper":hi,
                    "box_width_pct":(hi-lo)/op,
                    "box_age_sessions":max(0,idx[q["signal_date"]]-idx.get(str(q["detected_at"]),idx[q["signal_date"]])),
                    "_breadth":br})
    return out

def thresholds(train):
    th={}
    for s in ("small","large"):
        g=train[train.scale==s]
        th[s]={"wm":float(g.box_width_pct.median()),"am":float(g.box_age_sessions.median())}
    return th
def sleeve_ok(c,th,sleeve):
    fresh=c["box_age_sessions"]<=th[c["scale"]]["am"]
    if sleeve=="fresh":return fresh
    return fresh and c["box_width_pct"]>=th[c["scale"]]["wm"]

def flags(c):
    b=c["_breadth"] or {}
    fast=(pd.notna(b.get("d5_ma50")) and pd.notna(b.get("d5_ret20breadth")) and
          b["d5_ma50"]>=-.10 and b["d5_ret20breadth"]>=-.10)
    medium=(pd.notna(b.get("d10_ma50")) and pd.notna(b.get("d10_ret20breadth")) and
            b["d10_ma50"]>=-.15 and b["d10_ret20breadth"]>=-.15)
    nonew=(pd.notna(b.get("d5_newlow")) and b["d5_newlow"]<=.05)
    lowcons=c["post_detection_lower_touch_episodes"]<=1
    notcl=c["touch_days_last10"]<=2
    short=c["lower_zone_close_streak"]<=2
    core=lowcons and notcl and short
    det=fast and nonew
    return dict(low_consumption=lowcons,not_clustered=notcl,short_bottom_streak=short,
                integrity_core=core,no_fast_breadth_break=fast,no_medium_breadth_break=medium,
                no_newlow_acceleration=nonew,deterioration_core=det,
                integrity_plus_fast_breadth=core and fast,
                integrity_plus_deterioration_core=core and det)

def gate_ok(c,name):
    if name=="all":return True
    return flags(c)[name]

def run(cands,cal,bmd,start,end):
    by=defaultdict(list)
    for c in cands:
        if start<=c["entry_date"]<=end:by[c["entry_date"]].append(c)
    days=[d for d in cal if start<=d<=end]
    cash=1.;pos={};tr=[];eq=[];ex=[]
    for d in days:
        for sym in list(pos):
            b=bmd.get(sym,{}).get(d)
            if b is None:continue
            p=pos[sym];op=float(b["open"]);px=None;reason=None
            if op<=p["lower"]:px=op;reason="stop"
            elif op>=p["upper"]:px=op;reason="target"
            if px is not None:
                proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                tr.append({**p,"exit_reason":reason,"net_return":proceeds/p["cost_basis"]-1});del pos[sym]
        cand=[c for c in by.get(d,[]) if c["symbol"] not in pos]
        cand.sort(key=lambda x:x["symbol"])
        eqo=cash
        for sym,p in pos.items():
            b=bmd.get(sym,{}).get(d);eqo+=p["shares"]*(float(b["open"]) if b is not None else p["last"])
        req=sum(TARGET_WEIGHT[c["scale"]]*eqo for c in cand)
        sc=1 if req<=cash or req<=0 else cash/req
        for c in cand:
            alloc=TARGET_WEIGHT[c["scale"]]*eqo*sc
            if alloc<=1e-12 or alloc>cash+1e-10:continue
            invest=alloc*(1-ENTRY_COST);cash-=alloc
            pos[c["symbol"]]={**c,"shares":invest/c["entry_price"],"cost_basis":alloc,"last":c["entry_price"]}
        for sym in list(pos):
            b=bmd.get(sym,{}).get(d)
            if b is None:continue
            p=pos[sym];lo=float(b["low"]);hi=float(b["high"]);cl=float(b["close"]);px=None;reason=None
            if lo<=p["lower"]:px=p["lower"];reason="stop"
            elif hi>=p["upper"]:px=p["upper"];reason="target"
            if px is not None:
                proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                tr.append({**p,"exit_reason":reason,"net_return":proceeds/p["cost_basis"]-1});del pos[sym]
            else:p["last"]=cl
        val=cash;inv=0.
        for sym,p in pos.items():
            b=bmd.get(sym,{}).get(d);px=float(b["close"]) if b is not None else p["last"];p["last"]=px
            z=p["shares"]*px;val+=z;inv+=z
        eq.append((d,val));ex.append(inv/val if val>0 else 0)
    vals=[v for _,v in eq];rs=[t["net_return"] for t in tr]
    yrs=max((date.fromisoformat(eq[-1][0])-date.fromisoformat(eq[0][0])).days/365.2425,1/365)
    return {"total_return":vals[-1]/vals[0]-1,"cagr":(vals[-1]/vals[0])**(1/yrs)-1,
            "max_drawdown":mdd(vals),"sharpe":sharpe(eq),"avg_exposure":statistics.mean(ex),
            "trades":len(tr),"profit_factor":pf(rs),"mean_trade":statistics.mean(rs) if rs else None}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True)
    a=ap.parse_args();out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    bars,sig,cal,idx,nxt,bm,bmd=load(a.indir)
    rows=[];featrows=[]
    summary={"schema":"PURE-BOX-INTEGRITY-V1","lanes":{}}
    for cap in (300,500):
        breadth=build_breadth(bars,cap)
        bmap={r["date"]:r for r in breadth.to_dict("records")}
        cs=build_candidates(sig,cap,nxt,bm,bmd,idx,bmap)
        cdf=pd.DataFrame([{k:v for k,v in c.items() if k!="_breadth"} for c in cs])
        for y in YEARS:
            train=cdf[cdf.signal_date.str[:4].astype(int)<y]
            test=[c for c in cs if int(c["signal_date"][:4])==y]
            if train.empty or not test:continue
            th=thresholds(train)
            for sleeve in ("fresh","wide_fresh"):
                base=[c for c in test if sleeve_ok(c,th,sleeve)]
                if base:
                    fdf=pd.DataFrame([{**{k:v for k,v in c.items() if k!="_breadth"},
                                      **{f"br_{k}":v for k,v in (c["_breadth"] or {}).items()}} for c in base])
                    featrows.append({
                      "rank_cap":cap,"year":y,"sleeve":sleeve,"n":len(fdf),
                      "mean_touch_episodes":float(fdf.post_detection_lower_touch_episodes.mean()),
                      "mean_touch_days_last10":float(fdf.touch_days_last10.mean()),
                      "mean_bottom_streak":float(fdf.lower_zone_close_streak.mean()),
                      "mean_d5_ma50":float(fdf.br_d5_ma50.mean()),
                      "mean_d5_ret20breadth":float(fdf.br_d5_ret20breadth.mean()),
                      "mean_d5_newlow":float(fdf.br_d5_newlow.mean())
                    })
                for gate in GATES:
                    filt=[c for c in base if gate_ok(c,gate)]
                    res=run(filt,cal,bmd,f"{y}-01-01",f"{y}-12-31")
                    rows.append({"rank_cap":cap,"year":y,"sleeve":sleeve,"gate":gate,
                                 "eligible_candidates":len(filt),**res})
    rdf=pd.DataFrame(rows)
    rdf.to_csv(out/"annual_integrity.csv",index=False)
    pd.DataFrame(featrows).to_csv(out/"feature_year_receipt.csv",index=False)
    for cap in (300,500):
        summary["lanes"][f"top{cap}"]={}
        for sleeve in ("fresh","wide_fresh"):
            summary["lanes"][f"top{cap}"][sleeve]={}
            for gate in GATES:
                g=rdf[(rdf.rank_cap==cap)&(rdf.sleeve==sleeve)&(rdf.gate==gate)].sort_values("year")
                comp=1.;vals=[]
                for r in g.to_dict("records"):
                    comp*=1+float(r["total_return"]);vals.append(float(r["total_return"]))
                summary["lanes"][f"top{cap}"][sleeve][gate]={
                  "compounded_walk_forward_return":comp-1,
                  "positive_years":sum(v>0 for v in vals),"years":len(vals),
                  "avg_year_return":statistics.mean(vals),"avg_sharpe":float(g.sharpe.mean()),
                  "avg_exposure":float(g.avg_exposure.mean()),"total_trades":int(g.trades.sum()),
                  "yearly":{str(int(r.year)):float(r.total_return) for r in g.itertuples()}
                }
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
