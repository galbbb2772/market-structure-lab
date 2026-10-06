#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math, statistics
from collections import defaultdict
from datetime import date
from pathlib import Path
import pandas as pd

ENTRY_COST=.0005
EXIT_COST=.0005
TARGET_WEIGHT={"small":.5,"large":1.0}
THRESH={
 "small":{"age":8.0,"width":0.1008858137242378},
 "large":{"age":18.0,"width":0.2025964527335894},
}

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

def lane_ok(q,lane,entry_open):
    scale=str(q["scale"])
    fresh=float(q["age_sessions"])<=THRESH[scale]["age"]
    width=(float(q["upper"])-float(q["lower"]))/entry_open
    wide=width>=THRESH[scale]["width"]
    no3=int(q["touch_episodes"])<=2
    if lane=="fresh_all":return fresh
    if lane=="fresh_no3plus":return fresh and no3
    if lane=="wide_fresh_all":return fresh and wide
    if lane=="wide_fresh_no3plus":return fresh and wide and no3
    raise ValueError(lane)

def run(signals,rank_cap,lane,calendar,bar_map):
    s=signals[signals.liquidity_rank<=rank_cap].copy()
    next_session={calendar[i]:calendar[i+1] for i in range(len(calendar)-1)}
    pending=defaultdict(list)
    for q in s.to_dict("records"):
        nd=next_session.get(str(q["signal_date"]))
        if nd:pending[nd].append(q)

    cash=1.;pos={};tr=[];eq=[];ex=[]
    for d in calendar:
        # gaps
        for sym in list(pos):
            b=bar_map.get(sym,{}).get(d)
            if b is None:continue
            p=pos[sym];op=float(b["open"]);px=None;reason=None
            if op<=p["lower"]:px=op;reason="stop"
            elif op>=p["upper"]:px=op;reason="target"
            if px is not None:
                proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                tr.append({**p,"exit_date":d,"exit_reason":reason,
                           "net_return":proceeds/p["cost_basis"]-1,
                           "hold_sessions":p["age"]+1})
                del pos[sym]

        cand=[]
        for q in pending.get(d,[]):
            sym=q["symbol"]
            if sym in pos:continue
            b=bar_map.get(sym,{}).get(d)
            if b is None:continue
            op=float(b["open"]);lo=float(q["lower"]);hi=float(q["upper"])
            if op<=lo or op>=hi:continue
            if not lane_ok(q,lane,op):continue
            cand.append((q,op))
        cand.sort(key=lambda z:z[0]["symbol"])

        eqo=cash
        for sym,p in pos.items():
            b=bar_map.get(sym,{}).get(d)
            eqo+=p["shares"]*(float(b["open"]) if b is not None else p["last"])
        req=sum(TARGET_WEIGHT[q["scale"]]*eqo for q,_ in cand)
        sc=1 if req<=cash or req<=0 else cash/req
        for q,op in cand:
            alloc=TARGET_WEIGHT[q["scale"]]*eqo*sc
            if alloc<=1e-12 or alloc>cash+1e-10:continue
            invest=alloc*(1-ENTRY_COST);cash-=alloc
            pos[q["symbol"]]={
              "symbol":q["symbol"],"scale":q["scale"],"signal_date":q["signal_date"],
              "entry_date":d,"entry_price":op,"lower":float(q["lower"]),"upper":float(q["upper"]),
              "touch_episodes":int(q["touch_episodes"]),"age_sessions":int(q["age_sessions"]),
              "shares":invest/op,"cost_basis":alloc,"age":0,"last":op
            }

        # intraday stop-first
        for sym in list(pos):
            b=bar_map.get(sym,{}).get(d)
            if b is None:continue
            p=pos[sym];lo=float(b["low"]);hi=float(b["high"]);cl=float(b["close"]);px=None;reason=None
            if lo<=p["lower"]:px=p["lower"];reason="stop"
            elif hi>=p["upper"]:px=p["upper"];reason="target"
            if px is not None:
                proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                tr.append({**p,"exit_date":d,"exit_reason":reason,
                           "net_return":proceeds/p["cost_basis"]-1,
                           "hold_sessions":p["age"]+1})
                del pos[sym]
            else:
                p["last"]=cl;p["age"]+=1

        val=cash;invested=0.
        for sym,p in pos.items():
            b=bar_map.get(sym,{}).get(d)
            px=float(b["close"]) if b is not None else p["last"]
            p["last"]=px;z=p["shares"]*px;val+=z;invested+=z
        eq.append((d,val));ex.append(invested/val if val>0 else 0)

    vals=[v for _,v in eq]
    yrs=max((date.fromisoformat(eq[-1][0])-date.fromisoformat(eq[0][0])).days/365.2425,1/365)
    rs=[t["net_return"] for t in tr]
    edf=pd.DataFrame(eq,columns=["date","equity"]);edf["year"]=edf.date.str[:4]
    yearly={y:float(g.equity.iloc[-1]/g.equity.iloc[0]-1) for y,g in edf.groupby("year")}
    return {
      "portfolio":{"total_return":vals[-1]/vals[0]-1,"cagr":(vals[-1]/vals[0])**(1/yrs)-1,
                   "max_drawdown":mdd(vals),"sharpe":sharpe(eq),"avg_exposure":statistics.mean(ex)},
      "trades":len(tr),"win_rate":sum(x>0 for x in rs)/len(rs) if rs else None,
      "mean_trade":statistics.mean(rs) if rs else None,"profit_factor":pf(rs),"yearly":yearly
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--annodir",required=True);ap.add_argument("--bardir",required=True);ap.add_argument("--outdir",required=True)
    a=ap.parse_args();out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig=pd.concat([pd.read_csv(p) for p in sorted(Path(a.annodir).glob("**/annotated_signals_*.csv.gz"))],ignore_index=True)
    sig["signal_date"]=sig.signal_date.astype(str);sig["symbol"]=sig.symbol.astype(str)
    parts=[]
    for p in sorted(Path(a.bardir).glob("**/bars_*.csv.gz")):
        z=pd.read_csv(p);z["date"]=z.date.astype(str);z["ticker"]=z.ticker.astype(str);parts.append(z)
    bars=pd.concat(parts,ignore_index=True).sort_values(["ticker","date"]).drop_duplicates(["ticker","date"],keep="last")
    spy=bars[bars.ticker=="SPY"].sort_values("date")
    calendar=[d for d in spy.date.tolist() if "2023-01-01"<=d<="2026-03-31"]
    bar_map={s:{r["date"]:r for r in g.to_dict("records")} for s,g in bars.groupby("ticker")}
    result={"schema":"STRUCTURE-DECAY-PORTFOLIO-V1.2","window":[calendar[0],calendar[-1]],"results":{}}
    for cap in (300,500):
        result["results"][f"top{cap}"]={}
        for lane in ("fresh_all","fresh_no3plus","wide_fresh_all","wide_fresh_no3plus"):
            result["results"][f"top{cap}"][lane]=run(sig,cap,lane,calendar,bar_map)
    (out/"summary.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    rows=[]
    for cap,v in result["results"].items():
        for lane,r in v.items():
            rows.append({"universe":cap,"lane":lane,**r["portfolio"],"trades":r["trades"],
                         "win_rate":r["win_rate"],"mean_trade":r["mean_trade"],"profit_factor":r["profit_factor"],
                         **{f"ret_{y}":x for y,x in r["yearly"].items()}})
    pd.DataFrame(rows).to_csv(out/"comparison.csv",index=False)
    print(json.dumps(result,indent=2))
if __name__=="__main__":main()
