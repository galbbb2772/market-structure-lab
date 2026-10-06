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
INTEGRITY_GATES=("all","avoid_3plus","avoid_3plus_and_cluster")
BREADTH_GATES=("none","breadth_dual","avoid_internal_breakdown")

def pf(rs):
    w=sum(x for x in rs if x>0); l=-sum(x for x in rs if x<0)
    return w/l if l>0 else None

def mdd(vals):
    p=vals[0]; d=0.0
    for x in vals:
        p=max(p,x); d=min(d,x/p-1)
    return d

def sharpe(eq):
    r=[eq[i][1]/eq[i-1][1]-1 for i in range(1,len(eq)) if eq[i-1][1]>0]
    if len(r)<2:return None
    s=statistics.stdev(r)
    return None if s==0 else statistics.mean(r)/s*math.sqrt(252)

def integrity_features(g, signal_date, detected_at, lower, upper):
    dates=g["date"].to_numpy(dtype=str)
    i0=int(np.searchsorted(dates,detected_at,side="left"))
    i1=int(np.searchsorted(dates,signal_date,side="right"))
    a=g.iloc[i0:i1]
    if a.empty:return None
    width=max(float(upper-lower),1e-12)
    touch=a["low"].to_numpy(float)<=lower+.12*width
    episodes=0; prev=False
    for v in touch:
        if v and not prev: episodes+=1
        prev=bool(v)
    return {
      "touch_episodes":int(episodes),
      "touch_last10":int(touch[-10:].sum()),
      "touch_last20":int(touch[-20:].sum()),
    }

def build_breadth(bars,cap):
    x=bars[bars.ticker!="SPY"].copy().sort_values(["ticker","date"])
    x["dollar_volume"]=x.close*x.volume
    gp=x.groupby("ticker",group_keys=False)
    x["adv20_prior"]=gp.dollar_volume.transform(lambda s:s.shift(1).rolling(20,min_periods=20).mean())
    x["ma50"]=gp.close.transform(lambda s:s.rolling(50,min_periods=50).mean())
    x["ret20"]=gp.close.pct_change(20)
    valid=(x.close>=5)&x.adv20_prior.notna()&(x.adv20_prior>=ADV_FLOOR)
    z=x.loc[valid,["date","ticker","close","adv20_prior","ma50","ret20"]].copy()
    z=z.sort_values(["date","adv20_prior","ticker"],ascending=[True,False,True])
    z["liq_rank"]=z.groupby("date").cumcount()+1
    z=z[z.liq_rank<=cap]
    rows=[]
    for d,g in z.groupby("date",sort=True):
        rows.append({"date":d,
          "pct_above_ma50":float((g.close>=g.ma50).mean()),
          "pct_ret20_positive":float((g.ret20>0).mean())})
    return {r["date"]:r for r in rows}

def breadth_ok(b,name):
    if name=="none":return True
    if b is None:return False
    if name=="breadth_dual":
        return b["pct_above_ma50"]>=.50 and b["pct_ret20_positive"]>=.50
    if name=="avoid_internal_breakdown":
        return not (b["pct_above_ma50"]<.35 and b["pct_ret20_positive"]<.35)
    raise ValueError(name)

def integrity_ok(c,name):
    if name=="all":return True
    if name=="avoid_3plus":return c["touch_episodes"]<=2
    if name=="avoid_3plus_and_cluster":
        return c["touch_episodes"]<=2 and c["touch_last10"]<=2
    raise ValueError(name)

def run(cands,calendar,bm,start,end):
    by=defaultdict(list)
    for c in cands:
        if start<=c["entry_date"]<=end:by[c["entry_date"]].append(c)
    days=[d for d in calendar if start<=d<=end]
    cash=1.0; pos={}; tr=[]; eq=[]; ex=[]
    for d in days:
        for sym in list(pos):
            b=bm.get(sym,{}).get(d)
            if b is None:continue
            p=pos[sym];op=float(b["open"]);px=None;reason=None
            if op<=p["lower"]:px=op;reason="stop"
            elif op>=p["upper"]:px=op;reason="target"
            if px is not None:
                proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                tr.append({**p,"exit_reason":reason,"net_return":proceeds/p["cost_basis"]-1})
                del pos[sym]
        cand=[c for c in by.get(d,[]) if c["symbol"] not in pos]
        cand.sort(key=lambda x:x["symbol"])
        eqo=cash
        for sym,p in pos.items():
            b=bm.get(sym,{}).get(d)
            eqo+=p["shares"]*(float(b["open"]) if b is not None else p["last"])
        req=sum(TARGET_WEIGHT[c["scale"]]*eqo for c in cand)
        sc=1.0 if req<=cash or req<=0 else cash/req
        for c in cand:
            alloc=TARGET_WEIGHT[c["scale"]]*eqo*sc
            if alloc<=1e-12 or alloc>cash+1e-10:continue
            invest=alloc*(1-ENTRY_COST);cash-=alloc
            pos[c["symbol"]]={**c,"shares":invest/c["entry_price"],"cost_basis":alloc,"last":c["entry_price"]}
        for sym in list(pos):
            b=bm.get(sym,{}).get(d)
            if b is None:continue
            p=pos[sym];lo=float(b["low"]);hi=float(b["high"]);cl=float(b["close"]);px=None;reason=None
            if lo<=p["lower"]:px=p["lower"];reason="stop"
            elif hi>=p["upper"]:px=p["upper"];reason="target"
            if px is not None:
                proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                tr.append({**p,"exit_reason":reason,"net_return":proceeds/p["cost_basis"]-1})
                del pos[sym]
            else:p["last"]=cl
        val=cash;inv=0.0
        for sym,p in pos.items():
            b=bm.get(sym,{}).get(d)
            px=float(b["close"]) if b is not None else p["last"];p["last"]=px
            z=p["shares"]*px;val+=z;inv+=z
        eq.append((d,val));ex.append(inv/val if val>0 else 0.0)
    vals=[v for _,v in eq];rs=[t["net_return"] for t in tr]
    return {
      "total_return":vals[-1]/vals[0]-1,
      "max_drawdown":mdd(vals),
      "sharpe":sharpe(eq),
      "avg_exposure":statistics.mean(ex),
      "trades":len(tr),
      "profit_factor":pf(rs),
      "mean_trade":statistics.mean(rs) if rs else None
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--year",type=int,required=True)
    ap.add_argument("--cap",type=int,required=True,choices=[300,500])
    ap.add_argument("--indir",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    p=Path(a.indir);out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

    # Frozen walk-forward box thresholds from the prior Vitality V2 study.
    vit=json.load(open("research/pure_box_liquid_leaders_v1/vitality_v2/summary.json"))
    annual=vit["rank_caps"][f"top{a.cap}"]["annual_walk_forward"]
    th=next(x["thresholds"] for x in annual if int(x["year"])==a.year)

    sigp=next(p.glob(f"**/signals_{a.year}.csv"))
    barsp=next(p.glob(f"**/bars_{a.year}.csv.gz"))
    sig=pd.read_csv(sigp)
    sig["signal_date"]=sig.signal_date.astype(str);sig["detected_at"]=sig.detected_at.astype(str);sig["symbol"]=sig.symbol.astype(str)
    sig=sig[sig.liquidity_rank<=a.cap].copy()
    sig["ord"]=sig.scale.map({"small":0,"large":1}).fillna(0)
    sig=sig.sort_values(["signal_date","symbol","ord","detected_at"],ascending=[True,True,False,False]).drop_duplicates(["signal_date","symbol"],keep="first")

    # One-year artifact includes warmup months; loading one shard at a time keeps memory bounded.
    bars=pd.read_csv(barsp)
    bars["date"]=bars.date.astype(str);bars["ticker"]=bars.ticker.astype(str)
    bars=bars.sort_values(["ticker","date"]).drop_duplicates(["ticker","date"],keep="last")
    breadth=build_breadth(bars,a.cap)

    spy=bars[bars.ticker=="SPY"].sort_values("date")
    calendar=spy.date.tolist();idx={d:i for i,d in enumerate(calendar)}
    nxt={calendar[i]:calendar[i+1] for i in range(len(calendar)-1)}

    symbols=set(sig.symbol)
    sb=bars[bars.ticker.isin(symbols)].copy()
    bg={s:g.reset_index(drop=True) for s,g in sb.groupby("ticker")}
    bm={s:{r["date"]:r for r in g.to_dict("records")} for s,g in bg.items()}

    cands=[]
    for q in sig.to_dict("records"):
        ed=nxt.get(q["signal_date"]);g=bg.get(q["symbol"])
        if ed is None or g is None:continue
        b=bm[q["symbol"]].get(ed)
        if b is None:continue
        op=float(b["open"]);lo=float(q["lower"]);hi=float(q["upper"])
        if not(lo<op<hi):continue
        f=integrity_features(g,q["signal_date"],q["detected_at"],lo,hi)
        if f is None:continue
        age=max(0,idx[q["signal_date"]]-idx.get(q["detected_at"],idx[q["signal_date"]]))
        cands.append({**q,**f,"entry_date":ed,"entry_price":op,"lower":lo,"upper":hi,
                      "box_age_sessions":age,"box_width_pct":(hi-lo)/op,
                      "_breadth":breadth.get(q["signal_date"])})

    rows=[]
    start=f"{a.year}-01-01";end=f"{a.year}-12-31"
    for sleeve in ("fresh","wide_fresh"):
        def sleeve_ok(c):
            t=th[c["scale"]]
            fresh=c["box_age_sessions"]<=t["am"]
            return fresh if sleeve=="fresh" else fresh and c["box_width_pct"]>=t["wm"]
        base=[c for c in cands if sleeve_ok(c)]
        for ig in INTEGRITY_GATES:
            for bgate in BREADTH_GATES:
                filt=[c for c in base if integrity_ok(c,ig) and breadth_ok(c["_breadth"],bgate)]
                r=run(filt,calendar,bm,start,end)
                rows.append({"year":a.year,"rank_cap":a.cap,"sleeve":sleeve,
                             "integrity_gate":ig,"breadth_gate":bgate,
                             "eligible_candidates":len(filt),**r})
    df=pd.DataFrame(rows)
    df.to_csv(out/f"integrity_portfolio_{a.cap}_{a.year}.csv",index=False)
    receipt={"schema":"PURE-BOX-INTEGRITY-PORTFOLIO-YEAR-V2","year":a.year,"rank_cap":a.cap,
             "raw_candidates":len(cands),"thresholds":th}
    (out/f"summary_{a.cap}_{a.year}.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
    print(df.to_string(index=False))

if __name__=="__main__":main()
