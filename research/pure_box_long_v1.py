#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
import statistics
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs/data/structure_lab.json"
OUTDIR = ROOT / "research/pure_box_long_v1"
START = "2019-01-01"
BOTTOM_FRAC = 0.20
ENTRY_COST = 0.0005
EXIT_COST = 0.0005
TARGET_WEIGHT = {"small": 0.50, "large": 1.00}

def next_date_map(bars):
    return {bars[i][0]: bars[i+1][0] for i in range(len(bars)-1)}

def active_boxes_by_date(inst):
    bars = inst["bars"]
    dates = [b[0] for b in bars]
    idx = {d:i for i,d in enumerate(dates)}
    by = defaultdict(list)
    for box in inst.get("boxes", []):
        det = str(box.get("detected_at") or "")
        if det not in idx:
            continue
        end = box.get("end_at")
        end_i = idx.get(str(end), len(dates)-1) if end else len(dates)-1
        lo = float(box["lower"]); hi = float(box["upper"])
        if not hi > lo:
            continue
        # The box is known only after detected_at close. A signal at that close
        # may first enter next session. end_at is the last close before break_at,
        # so a signal on end_at is still causally valid for the breakout session.
        for j in range(idx[det], end_i+1):
            by[dates[j]].append({
                "id": box.get("id"),
                "scale": box.get("scale"),
                "lower": lo,
                "upper": hi,
                "detected_at": det,
            })
    return by

def build_opportunities(instruments):
    opps = defaultdict(list)
    bars_by = {}
    for sym, inst in instruments.items():
        if inst.get("group") == "index":
            continue
        bars = [b for b in inst.get("bars", []) if b[0] >= START]
        if len(bars) < 2:
            continue
        bars_by[sym] = bars
        nd = next_date_map(bars)
        ab = active_boxes_by_date(inst)
        for b in bars[:-1]:
            d, op, hi, lo, cl, vol = b
            candidates = []
            for box in ab.get(d, []):
                lower, upper = box["lower"], box["upper"]
                if lower <= float(cl) <= lower + BOTTOM_FRAC*(upper-lower):
                    candidates.append(box)
            if not candidates:
                continue
            # large > small. If same scale somehow overlaps, newest detection wins.
            candidates.sort(key=lambda x: (1 if x["scale"]=="large" else 0, x["detected_at"]), reverse=True)
            box = candidates[0]
            opps[nd[d]].append({
                "symbol": sym, "signal_date": d, "entry_date": nd[d],
                "scale": box["scale"], "box_id": box["id"],
                "lower": box["lower"], "upper": box["upper"],
                "requested_weight": TARGET_WEIGHT[box["scale"]],
            })
    return bars_by, opps

def max_drawdown(vals):
    peak = vals[0]
    mdd = 0.0
    for v in vals:
        peak = max(peak, v)
        mdd = min(mdd, v/peak - 1.0)
    return mdd

def sharpe_from_equity(equity):
    rets=[]
    for i in range(1,len(equity)):
        a,b=equity[i-1][1],equity[i][1]
        if a>0: rets.append(b/a-1)
    if len(rets)<2:
        return None
    sd=statistics.stdev(rets)
    return None if sd==0 else statistics.mean(rets)/sd*math.sqrt(252)

def summarize_trades(trades, scale=None):
    z=[t for t in trades if scale is None or t["scale"]==scale]
    if not z:
        return {"trades":0}
    rr=[t["net_return"] for t in z]
    wins=[x for x in rr if x>0]
    losses=[x for x in rr if x<0]
    pf=(sum(wins)/abs(sum(losses))) if losses else (float("inf") if wins else None)
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

def run():
    data=json.loads(DATA.read_text(encoding="utf-8"))
    instruments=data["instruments"]
    bars_by, opps=build_opportunities(instruments)
    symbols=sorted(bars_by)

    # Union calendar from investable instruments.
    calendar=sorted({b[0] for bars in bars_by.values() for b in bars})
    bar_map={s:{b[0]:b for b in bars} for s,bars in bars_by.items()}

    cash=1.0
    pos={}
    pending=defaultdict(list)
    trades=[]
    equity=[]
    exposure_series=[]
    rejected={"gap_below_stop":0,"gap_above_target":0,"no_cash":0,"already_held":0}

    # Preload all signal opportunities by their next-entry date.
    for d, xs in opps.items():
        pending[d].extend(xs)

    # Need signal opportunities only if flat at signal close. Because opps were
    # precomputed independent of holdings, enforce that at entry as a conservative
    # approximation: same-symbol entries are skipped while held.
    for d in calendar:
        # 1) Existing positions: gap exits at today's open.
        for s in list(pos):
            b=bar_map[s].get(d)
            if not b:
                continue
            op,hi,lo,cl=map(float,b[1:5])
            p=pos[s]
            exit_px=None; reason=None
            if op <= p["lower"]:
                exit_px=op; reason="stop"
            elif op >= p["upper"]:
                exit_px=op; reason="target"
            if exit_px is not None:
                proceeds=p["shares"]*exit_px*(1-EXIT_COST)
                cash += proceeds
                net_ret=proceeds/p["cost_basis"]-1
                trades.append({**p,"exit_date":d,"exit_price":exit_px,"exit_reason":reason,
                               "net_return":net_ret,"hold_sessions":p["age"]+1})
                del pos[s]

        # 2) Scheduled entries at open. Remove impossible gaps and already-held.
        candidates=[]
        for sig in pending.get(d,[]):
            s=sig["symbol"]
            if s in pos:
                rejected["already_held"]+=1
                continue
            b=bar_map[s].get(d)
            if not b:
                continue
            op=float(b[1])
            if op <= sig["lower"]:
                rejected["gap_below_stop"]+=1
                continue
            if op >= sig["upper"]:
                rejected["gap_above_target"]+=1
                continue
            candidates.append((sig,op))

        # Mark opening equity before adding new trades.
        eq_open=cash
        for s,p in pos.items():
            b=bar_map[s].get(d)
            px=float(b[1]) if b else p["last"]
            eq_open += p["shares"]*px

        requested=sum(sig["requested_weight"]*eq_open for sig,_ in candidates)
        available=max(0.0,cash)
        scale=1.0 if requested<=available or requested<=0 else available/requested
        for sig,op in candidates:
            alloc=sig["requested_weight"]*eq_open*scale
            if alloc <= 1e-12:
                rejected["no_cash"]+=1
                continue
            fee=alloc*ENTRY_COST
            invest=alloc-fee
            if invest<=0 or alloc>cash+1e-10:
                rejected["no_cash"]+=1
                continue
            shares=invest/op
            cash-=alloc
            pos[sig["symbol"]]={
                "symbol":sig["symbol"],"signal_date":sig["signal_date"],"entry_date":d,
                "entry_price":op,"shares":shares,"cost_basis":alloc,
                "scale":sig["scale"],"box_id":sig["box_id"],
                "lower":sig["lower"],"upper":sig["upper"],
                "requested_weight":sig["requested_weight"],"actual_entry_weight":alloc/max(eq_open,1e-12),
                "age":0,"last":op,
            }

        # 3) Intraday stop/target. If both touched, stop first.
        for s in list(pos):
            b=bar_map[s].get(d)
            if not b:
                continue
            op,hi,lo,cl=map(float,b[1:5])
            p=pos[s]
            exit_px=None; reason=None
            hit_stop=lo <= p["lower"]
            hit_target=hi >= p["upper"]
            if hit_stop:
                exit_px=p["lower"]; reason="stop"
            elif hit_target:
                exit_px=p["upper"]; reason="target"
            if exit_px is not None:
                proceeds=p["shares"]*exit_px*(1-EXIT_COST)
                cash += proceeds
                net_ret=proceeds/p["cost_basis"]-1
                trades.append({**p,"exit_date":d,"exit_price":exit_px,"exit_reason":reason,
                               "net_return":net_ret,"hold_sessions":p["age"]+1})
                del pos[s]
            else:
                p["last"]=cl
                p["age"]+=1

        # 4) End-of-day mark.
        eq=cash
        invested=0.0
        for s,p in pos.items():
            b=bar_map[s].get(d)
            px=float(b[4]) if b else p["last"]
            p["last"]=px
            val=p["shares"]*px
            eq += val; invested += val
        equity.append((d,eq))
        exposure_series.append((d, 0.0 if eq<=0 else invested/eq))

    # Mark remaining open positions at final close for descriptive trade stats only.
    if calendar:
        final_d=calendar[-1]
        for s,p in list(pos.items()):
            b=bar_map[s].get(final_d)
            px=float(b[4]) if b else p["last"]
            proceeds=p["shares"]*px*(1-EXIT_COST)
            net_ret=proceeds/p["cost_basis"]-1
            trades.append({**p,"exit_date":final_d,"exit_price":px,"exit_reason":"end_mark",
                           "net_return":net_ret,"hold_sessions":p["age"]})
    
    vals=[x[1] for x in equity]
    start_d=date.fromisoformat(equity[0][0]); end_d=date.fromisoformat(equity[-1][0])
    years=max((end_d-start_d).days/365.2425,1/365.2425)
    total=vals[-1]/vals[0]-1
    cagr=(vals[-1]/vals[0])**(1/years)-1 if vals[0]>0 and vals[-1]>0 else None

    # SPY / QQQ buy-and-hold comparison on the same date window.
    benchmarks={}
    for s in ("SPY","QQQ","DIA"):
        bars=bars_by.get(s,[])
        if bars:
            r=float(bars[-1][4])/float(bars[0][4])-1
            benchmarks[s]={"start":bars[0][0],"end":bars[-1][0],"price_return":r}

    summary={
        "schema":"PURE-BOX-LONG-V1",
        "research_only":True,
        "dataset_generated_at":data.get("generated_at"),
        "window":[equity[0][0],equity[-1][0]],
        "universe":symbols,
        "rules":{
            "bottom_fraction":BOTTOM_FRAC,
            "small_weight":TARGET_WEIGHT["small"],
            "large_weight":TARGET_WEIGHT["large"],
            "stop":"box_lower",
            "take_profit":"box_upper",
            "both_intraday":"stop_first",
            "entry":"next_session_open",
            "cost_per_side_bps":ENTRY_COST*10000,
            "extra_filters":"none",
        },
        "portfolio":{
            "start_equity":vals[0],
            "end_equity":vals[-1],
            "total_return":total,
            "cagr":cagr,
            "max_drawdown":max_drawdown(vals),
            "daily_sharpe":sharpe_from_equity(equity),
            "avg_exposure":statistics.mean(x[1] for x in exposure_series),
            "max_exposure":max(x[1] for x in exposure_series),
        },
        "trade_stats_all":summarize_trades(trades),
        "trade_stats_small":summarize_trades(trades,"small"),
        "trade_stats_large":summarize_trades(trades,"large"),
        "rejected_entries":rejected,
        "benchmarks":benchmarks,
        "notes":[
            "ETF/index-proxy pilot only; this is not the final all-stock 2019-2026 result.",
            "No alpha filters were added beyond the pre-existing bottom-20% box location rule.",
            "End-mark trades exist only to describe currently open positions at sample end."
        ],
    }
    OUTDIR.mkdir(parents=True,exist_ok=True)
    (OUTDIR/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    with (OUTDIR/"trades.csv").open("w",newline="",encoding="utf-8") as fh:
        keys=["symbol","scale","box_id","signal_date","entry_date","entry_price","exit_date","exit_price",
              "exit_reason","net_return","hold_sessions","requested_weight","actual_entry_weight","lower","upper"]
        w=csv.DictWriter(fh,fieldnames=keys,extrasaction="ignore"); w.writeheader(); w.writerows(trades)
    with (OUTDIR/"equity.csv").open("w",newline="",encoding="utf-8") as fh:
        w=csv.writer(fh); w.writerow(["date","equity","exposure"])
        exp=dict(exposure_series)
        for d,e in equity: w.writerow([d,f"{e:.10f}",f"{exp[d]:.10f}"])
    def pct(x): return "—" if x is None else f"{100*x:.2f}%"
    t=summary["trade_stats_all"]; p=summary["portfolio"]
    md=f"""# Pure Box Long V1 — ETF pilot result

- Window: {summary['window'][0]} → {summary['window'][1]}
- Universe: {', '.join(symbols)}
- Total return: {pct(p['total_return'])}
- CAGR: {pct(p['cagr'])}
- Max drawdown: {pct(p['max_drawdown'])}
- Daily Sharpe: {p['daily_sharpe'] if p['daily_sharpe'] is not None else '—'}
- Average exposure: {pct(p['avg_exposure'])}
- Trades: {t.get('trades',0)}
- Win rate: {pct(t.get('win_rate'))}
- Mean trade return: {pct(t.get('mean_return'))}
- Median trade return: {pct(t.get('median_return'))}
- Profit factor: {t.get('profit_factor')}
- Average hold: {t.get('avg_hold_sessions')} sessions

## Small box
{json.dumps(summary['trade_stats_small'],ensure_ascii=False,indent=2)}

## Large box
{json.dumps(summary['trade_stats_large'],ensure_ascii=False,indent=2)}

## Important
This is the first public ETF/sector pilot, not the final all-stock 2019–2026 verdict.
"""
    (OUTDIR/"RESULT.md").write_text(md,encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":
    run()
