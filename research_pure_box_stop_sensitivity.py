#!/usr/bin/env python3
from __future__ import annotations

import argparse, csv, json, math, statistics
from collections import defaultdict
from datetime import date
from pathlib import Path

import pandas as pd

ENTRY_COST=0.0005
EXIT_COST=0.0005
TARGET_WEIGHT={"small":0.50,"large":1.00}
STOP_LANES=[
    ("box_lower", None),
    ("fixed_2pct", 0.02),
    ("fixed_3pct", 0.03),
    ("fixed_5pct", 0.05),
    ("fixed_7pct", 0.07),
    ("fixed_10pct", 0.10),
]

def mdd(vals):
    p=vals[0]; out=0.0
    for v in vals:
        p=max(p,v); out=min(out,v/p-1)
    return out

def sharpe(eq):
    r=[eq[i][1]/eq[i-1][1]-1 for i in range(1,len(eq)) if eq[i-1][1]>0]
    if len(r)<2:return None
    sd=statistics.stdev(r)
    return None if sd==0 else statistics.mean(r)/sd*math.sqrt(252)

def trade_stats(trades,scale=None):
    z=[t for t in trades if scale is None or t["scale"]==scale]
    if not z:return {"trades":0}
    rr=[t["net_return"] for t in z]; w=[x for x in rr if x>0]; l=[x for x in rr if x<0]
    pf=sum(w)/abs(sum(l)) if l else (float("inf") if w else None)
    return {
        "trades":len(z),
        "win_rate":sum(x>0 for x in rr)/len(rr),
        "mean_return":statistics.mean(rr),
        "median_return":statistics.median(rr),
        "profit_factor":pf,
        "avg_hold_sessions":statistics.mean(t["hold_sessions"] for t in z),
        "target_exits":sum(t["exit_reason"]=="target" for t in z),
        "stop_exits":sum(t["exit_reason"]=="stop" for t in z),
        "end_mark_exits":sum(t["exit_reason"]=="end_mark" for t in z),
    }

def run_lane(rank_cap, stop_name, stop_pct, bars, signals, calendar, bar_map):
    cash=1.0; pos={}; trades=[]; equity=[]; exposure=[]
    rejected=defaultdict(int)
    s=signals[signals.liquidity_rank<=rank_cap].copy()
    s["scale_order"]=s.scale.map({"small":0,"large":1}).fillna(0)
    s=s.sort_values(["signal_date","symbol","scale_order","detected_at"],
                    ascending=[True,True,False,False])
    s=s.drop_duplicates(["signal_date","symbol"],keep="first")
    by_signal={d:g.to_dict("records") for d,g in s.groupby("signal_date")}

    next_session={calendar[i]:calendar[i+1] for i in range(len(calendar)-1)}
    pending=defaultdict(list)
    for d,rows in by_signal.items():
        nd=next_session.get(d)
        if nd: pending[nd].extend(rows)

    for d in calendar:
        # gap exits for existing positions
        for sym in list(pos):
            b=bar_map.get(sym,{}).get(d)
            if b is None: continue
            op=float(b["open"]); p=pos[sym]
            px=None; reason=None
            if op<=p["stop_price"]: px=op; reason="stop"
            elif op>=p["upper"]: px=op; reason="target"
            if px is not None:
                proceeds=p["shares"]*px*(1-EXIT_COST); cash+=proceeds
                trades.append({**p,"exit_date":d,"exit_price":px,"exit_reason":reason,
                               "net_return":proceeds/p["cost_basis"]-1,
                               "hold_sessions":p["age"]+1})
                del pos[sym]

        # entries
        candidates=[]
        for q in pending.get(d,[]):
            sym=q["symbol"]
            if sym in pos:
                rejected["already_held"]+=1; continue
            b=bar_map.get(sym,{}).get(d)
            if b is None:
                rejected["missing_next_open"]+=1; continue
            op=float(b["open"]); hi=float(q["upper"]); box_lo=float(q["lower"])
            stop_price=box_lo if stop_pct is None else op*(1-stop_pct)
            if stop_pct is None and op<=stop_price:
                rejected["gap_below_stop"]+=1; continue
            if op>=hi:
                rejected["gap_above_target"]+=1; continue
            candidates.append((q,op,stop_price))

        eq_open=cash
        for sym,p in pos.items():
            b=bar_map.get(sym,{}).get(d)
            px=float(b["open"]) if b is not None else p["last"]
            eq_open += p["shares"]*px
        requested=sum(TARGET_WEIGHT[q["scale"]]*eq_open for q,_,__ in candidates)
        avail=max(0.0,cash)
        scale=1.0 if requested<=avail or requested<=0 else avail/requested
        for q,op,stop_price in candidates:
            alloc=TARGET_WEIGHT[q["scale"]]*eq_open*scale
            if alloc<=1e-12 or alloc>cash+1e-10:
                rejected["no_cash"]+=1; continue
            invest=alloc*(1-ENTRY_COST); shares=invest/op; cash-=alloc
            pos[q["symbol"]]={
                "symbol":q["symbol"],"scale":q["scale"],"signal_date":q["signal_date"],
                "entry_date":d,"entry_price":op,"shares":shares,"cost_basis":alloc,
                "box_lower":float(q["lower"]),"upper":float(q["upper"]),
                "stop_name":stop_name,"stop_pct":stop_pct,"stop_price":float(stop_price),
                "liquidity_rank":int(q["liquidity_rank"]),"adv20_prior":float(q["adv20_prior"]),
                "requested_weight":TARGET_WEIGHT[q["scale"]],
                "actual_entry_weight":alloc/max(eq_open,1e-12),"age":0,"last":op,
            }

        # intraday exits; if both touched, conservative stop-first
        for sym in list(pos):
            b=bar_map.get(sym,{}).get(d)
            if b is None: continue
            p=pos[sym]; lo=float(b["low"]); hi=float(b["high"]); cl=float(b["close"])
            px=None; reason=None
            if lo<=p["stop_price"]: px=p["stop_price"]; reason="stop"
            elif hi>=p["upper"]: px=p["upper"]; reason="target"
            if px is not None:
                proceeds=p["shares"]*px*(1-EXIT_COST); cash+=proceeds
                trades.append({**p,"exit_date":d,"exit_price":px,"exit_reason":reason,
                               "net_return":proceeds/p["cost_basis"]-1,
                               "hold_sessions":p["age"]+1})
                del pos[sym]
            else:
                p["last"]=cl; p["age"]+=1

        eq=cash; invested=0.0
        for sym,p in pos.items():
            b=bar_map.get(sym,{}).get(d)
            px=float(b["close"]) if b is not None else p["last"]
            p["last"]=px; v=p["shares"]*px; eq+=v; invested+=v
        equity.append((d,eq)); exposure.append((d,0 if eq<=0 else invested/eq))

    if calendar:
        fd=calendar[-1]
        for sym,p in list(pos.items()):
            b=bar_map.get(sym,{}).get(fd)
            px=float(b["close"]) if b is not None else p["last"]
            proceeds=p["shares"]*px*(1-EXIT_COST)
            trades.append({**p,"exit_date":fd,"exit_price":px,"exit_reason":"end_mark",
                           "net_return":proceeds/p["cost_basis"]-1,
                           "hold_sessions":p["age"]})

    vals=[e for _,e in equity]
    y=max((date.fromisoformat(equity[-1][0])-date.fromisoformat(equity[0][0])).days/365.2425,1/365.2425)
    eqdf=pd.DataFrame(equity,columns=["date","equity"]); eqdf["year"]=eqdf.date.str[:4]
    yearly={}
    for yr,g in eqdf.groupby("year"):
        first=float(g.equity.iloc[0]); last=float(g.equity.iloc[-1])
        yearly[yr]=last/first-1 if first else None
    return {
        "rank_cap":rank_cap,"stop_name":stop_name,"stop_pct":stop_pct,
        "portfolio":{
            "start_equity":vals[0],"end_equity":vals[-1],
            "total_return":vals[-1]/vals[0]-1,
            "cagr":(vals[-1]/vals[0])**(1/y)-1,
            "max_drawdown":mdd(vals),"daily_sharpe":sharpe(equity),
            "avg_exposure":statistics.mean(v for _,v in exposure),
            "max_exposure":max(v for _,v in exposure),
        },
        "trade_stats_all":trade_stats(trades),
        "trade_stats_small":trade_stats(trades,"small"),
        "trade_stats_large":trade_stats(trades,"large"),
        "rejected_entries":dict(rejected),"yearly_returns":yearly,
    }, trades

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--indir",required=True); ap.add_argument("--outdir",required=True)
    args=ap.parse_args(); indir=Path(args.indir); outdir=Path(args.outdir); outdir.mkdir(parents=True,exist_ok=True)

    bars_parts=[pd.read_csv(p) for p in sorted(indir.glob("**/bars_*.csv.gz"))]
    if not bars_parts: raise RuntimeError("No yearly bar artifacts")
    bars=pd.concat(bars_parts,ignore_index=True)
    bars["date"]=bars.date.astype(str); bars["ticker"]=bars.ticker.astype(str)
    bars=bars.sort_values(["ticker","date"]).drop_duplicates(["ticker","date"],keep="last")

    sig_parts=[pd.read_csv(p) for p in sorted(indir.glob("**/signals_*.csv"))]
    signals=pd.concat(sig_parts,ignore_index=True) if sig_parts else pd.DataFrame()
    if signals.empty: raise RuntimeError("No signals")
    signals["signal_date"]=signals.signal_date.astype(str); signals["symbol"]=signals.symbol.astype(str)

    spy=bars[bars.ticker=="SPY"].sort_values("date")
    if spy.empty: raise RuntimeError("SPY calendar missing")
    calendar=spy.date.tolist()
    bar_map={}
    for sym,g in bars.groupby("ticker"):
        bar_map[sym]={r["date"]:r for r in g.to_dict("records")}

    results={}
    primary_trades={}
    for cap in (200,300,500):
        results[f"top{cap}"]={}
        for stop_name,stop_pct in STOP_LANES:
            res,tr=run_lane(cap,stop_name,stop_pct,bars,signals,calendar,bar_map)
            results[f"top{cap}"][stop_name]=res
            if cap==500 and stop_name in ("box_lower","fixed_5pct"):
                primary_trades[stop_name]=tr

    summary={
        "schema":"PURE-BOX-STOP-SENSITIVITY-V1",
        "research_only":True,
        "window":[calendar[0],calendar[-1]],
        "universe":"same causal prior-ADV20 Top200/300/500 liquid-leader proxy as Pure Box Liquid Leaders V1",
        "frozen_except_stop":True,
        "stop_lanes":{"box_lower":"existing baseline","fixed_2pct":"2% below entry","fixed_3pct":"3% below entry",
                      "fixed_5pct":"5% below entry","fixed_7pct":"7% below entry","fixed_10pct":"10% below entry"},
        "take_profit":"unchanged box upper",
        "results":results,
    }
    (outdir/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")

    # compact CSV for easy comparison
    rows=[]
    for cap,lanes in results.items():
        for stop_name,r in lanes.items():
            p=r["portfolio"]; a=r["trade_stats_all"]; sm=r["trade_stats_small"]; lg=r["trade_stats_large"]
            rows.append({
                "universe":cap,"stop":stop_name,
                "total_return":p["total_return"],"cagr":p["cagr"],"max_drawdown":p["max_drawdown"],
                "sharpe":p["daily_sharpe"],"avg_exposure":p["avg_exposure"],
                "trades":a.get("trades"),"win_rate":a.get("win_rate"),"mean_trade":a.get("mean_return"),
                "profit_factor":a.get("profit_factor"),"avg_hold":a.get("avg_hold_sessions"),
                "small_pf":sm.get("profit_factor"),"small_mean":sm.get("mean_return"),
                "large_pf":lg.get("profit_factor"),"large_mean":lg.get("mean_return"),
            })
    pd.DataFrame(rows).to_csv(outdir/"comparison.csv",index=False)

    # save year-by-year comparison for Top500 only
    yr=[]
    for stop_name,r in results["top500"].items():
        for y,v in r["yearly_returns"].items():
            yr.append({"stop":stop_name,"year":y,"return":v})
    pd.DataFrame(yr).to_csv(outdir/"top500_yearly.csv",index=False)

    print(json.dumps(summary,indent=2))

if __name__=="__main__":
    main()
