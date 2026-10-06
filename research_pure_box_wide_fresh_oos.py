#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math, statistics
from collections import defaultdict
from datetime import date
from pathlib import Path
import pandas as pd

ENTRY_COST=.0005; EXIT_COST=.0005
TARGET_WEIGHT={"small":.5,"large":1.0}
DISC_END="2022-12-31"; VAL_START="2023-01-01"

def mdd(v):
    p=v[0];d=0
    for x in v:p=max(p,x);d=min(d,x/p-1)
    return d
def sharpe(eq):
    r=[eq[i][1]/eq[i-1][1]-1 for i in range(1,len(eq))]
    if len(r)<2:return None
    s=statistics.stdev(r)
    return None if s==0 else statistics.mean(r)/s*math.sqrt(252)
def pf(rs):
    w=sum(x for x in rs if x>0); l=-sum(x for x in rs if x<0)
    return w/l if l>0 else None

def load(indir):
    p=Path(indir)
    bars=pd.concat([pd.read_csv(x) for x in sorted(p.glob("**/bars_*.csv.gz"))],ignore_index=True)
    bars["date"]=bars.date.astype(str);bars["ticker"]=bars.ticker.astype(str)
    bars=bars.sort_values(["ticker","date"]).drop_duplicates(["ticker","date"],keep="last")
    sig=pd.concat([pd.read_csv(x) for x in sorted(p.glob("**/signals_*.csv"))],ignore_index=True)
    sig["signal_date"]=sig.signal_date.astype(str);sig["symbol"]=sig.symbol.astype(str)
    spy=bars[bars.ticker=="SPY"].sort_values("date")
    cal=spy.date.tolist(); idx={d:i for i,d in enumerate(cal)}
    nxt={cal[i]:cal[i+1] for i in range(len(cal)-1)}
    bm={s:{r["date"]:r for r in g.to_dict("records")} for s,g in bars.groupby("ticker")}
    return sig,cal,idx,nxt,bm

def candidates(sig,cap,nxt,bm,idx):
    s=sig[sig.liquidity_rank<=cap].copy()
    s["ord"]=s.scale.map({"small":0,"large":1})
    s=s.sort_values(["signal_date","symbol","ord","detected_at"],ascending=[True,True,False,False]).drop_duplicates(["signal_date","symbol"],keep="first")
    out=[]
    for q in s.to_dict("records"):
        ed=nxt.get(q["signal_date"]); b=bm.get(q["symbol"],{}).get(ed) if ed else None
        if b is None:continue
        op=float(b["open"]);lo=float(q["lower"]);hi=float(q["upper"])
        if not (lo<op<hi):continue
        width=hi-lo
        out.append({**q,"entry_date":ed,"entry_price":op,"lower":lo,"upper":hi,
                    "box_width_pct":width/op,
                    "box_age_sessions":max(0,idx[q["signal_date"]]-idx.get(str(q["detected_at"]),idx[q["signal_date"]]))})
    return out

def run(cands,calendar,bm,rule):
    by=defaultdict(list)
    for c in cands:
        if c["entry_date"]>=VAL_START and rule(c):by[c["entry_date"]].append(c)
    cash=1.;pos={};tr=[];eq=[];ex=[]
    for d in [x for x in calendar if x>=VAL_START]:
        for sym in list(pos):
            b=bm.get(sym,{}).get(d)
            if b is None:continue
            p=pos[sym];op=float(b["open"]);px=None;reason=None
            if op<=p["lower"]:px=op;reason="stop"
            elif op>=p["upper"]:px=op;reason="target"
            if px is not None:
                proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                tr.append({**p,"exit_date":d,"exit_reason":reason,"net_return":proceeds/p["cost_basis"]-1,"hold":p["age"]+1});del pos[sym]
        cand=[c for c in by.get(d,[]) if c["symbol"] not in pos]
        eqo=cash
        for sym,p in pos.items():
            b=bm.get(sym,{}).get(d);eqo+=p["shares"]*(float(b["open"]) if b is not None else p["last"])
        req=sum(TARGET_WEIGHT[c["scale"]]*eqo for c in cand)
        sc=1 if req<=cash or req<=0 else cash/req
        for c in cand:
            alloc=TARGET_WEIGHT[c["scale"]]*eqo*sc
            if alloc<=1e-12 or alloc>cash+1e-10:continue
            op=c["entry_price"];invest=alloc*(1-ENTRY_COST);cash-=alloc
            pos[c["symbol"]]={**c,"shares":invest/op,"cost_basis":alloc,"age":0,"last":op}
        for sym in list(pos):
            b=bm.get(sym,{}).get(d)
            if b is None:continue
            p=pos[sym];lo=float(b["low"]);hi=float(b["high"]);cl=float(b["close"]);px=None;reason=None
            if lo<=p["lower"]:px=p["lower"];reason="stop"
            elif hi>=p["upper"]:px=p["upper"];reason="target"
            if px is not None:
                proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                tr.append({**p,"exit_date":d,"exit_reason":reason,"net_return":proceeds/p["cost_basis"]-1,"hold":p["age"]+1});del pos[sym]
            else:p["last"]=cl;p["age"]+=1
        val=cash;invested=0
        for sym,p in pos.items():
            b=bm.get(sym,{}).get(d);px=float(b["close"]) if b is not None else p["last"];p["last"]=px
            z=p["shares"]*px;val+=z;invested+=z
        eq.append((d,val));ex.append(invested/val if val>0 else 0)
    vals=[v for _,v in eq];yrs=max((date.fromisoformat(eq[-1][0])-date.fromisoformat(eq[0][0])).days/365.2425,1/365)
    rs=[x["net_return"] for x in tr]
    edf=pd.DataFrame(eq,columns=["date","equity"]);edf["year"]=edf.date.str[:4]
    return {"portfolio":{"total_return":vals[-1]/vals[0]-1,"cagr":(vals[-1]/vals[0])**(1/yrs)-1,
                          "max_drawdown":mdd(vals),"sharpe":sharpe(eq),"avg_exposure":statistics.mean(ex)},
            "trades":len(tr),"win_rate":sum(x>0 for x in rs)/len(rs) if rs else None,
            "mean_trade":statistics.mean(rs) if rs else None,"profit_factor":pf(rs),
            "yearly":{y:float(g.equity.iloc[-1]/g.equity.iloc[0]-1) for y,g in edf.groupby("year")}}

def main():
    a=argparse.ArgumentParser();a.add_argument("--indir",required=True);a.add_argument("--outdir",required=True);z=a.parse_args()
    out=Path(z.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=load(z.indir)
    result={"schema":"PURE-BOX-WIDE-FRESH-OOS-V1","discovery":"2019-2022","validation":"2023-2026Q1","rank_caps":{}}
    for cap in (300,500):
        cs=candidates(sig,cap,nxt,bm,idx)
        disc=pd.DataFrame([c for c in cs if c["signal_date"]<=DISC_END])
        thresholds={}
        for scale in ("small","large"):
            g=disc[disc.scale==scale]
            thresholds[scale]={
                "width_median":float(g.box_width_pct.median()),
                "age_median":float(g.box_age_sessions.median()),
                "width_q80":float(g.box_width_pct.quantile(.8)),
                "age_q20":float(g.box_age_sessions.quantile(.2)),
            }
        def base(c):return True
        def wide(c):return c["box_width_pct"]>=thresholds[c["scale"]]["width_median"]
        def fresh(c):return c["box_age_sessions"]<=thresholds[c["scale"]]["age_median"]
        def wide_fresh(c):return wide(c) and fresh(c)
        def strict(c):return c["box_width_pct"]>=thresholds[c["scale"]]["width_q80"] and c["box_age_sessions"]<=thresholds[c["scale"]]["age_q20"]
        lanes={n:run(cs,cal,bm,f) for n,f in [("baseline",base),("wide_only",wide),("fresh_only",fresh),("wide_fresh",wide_fresh),("strict_wide_fresh",strict)]}
        result["rank_caps"][f"top{cap}"]={"thresholds_from_discovery":thresholds,"validation":lanes}
    (out/"summary.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))
if __name__=="__main__":main()
