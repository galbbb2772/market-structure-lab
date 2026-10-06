#!/usr/bin/env python3
from __future__ import annotations

import argparse, csv, glob, json, math, statistics
from collections import defaultdict
from datetime import date
from pathlib import Path

import pandas as pd

ENTRY_COST=0.0005
EXIT_COST=0.0005
TARGET_WEIGHT={"small":0.50,"large":1.00}

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
        "trades":len(z),"win_rate":sum(x>0 for x in rr)/len(rr),
        "mean_return":statistics.mean(rr),"median_return":statistics.median(rr),
        "profit_factor":pf,"avg_hold_sessions":statistics.mean(t["hold_sessions"] for t in z),
        "target_exits":sum(t["exit_reason"]=="target" for t in z),
        "stop_exits":sum(t["exit_reason"]=="stop" for t in z),
        "end_mark_exits":sum(t["exit_reason"]=="end_mark" for t in z),
    }

def run_lane(rank_cap,bars,signals,calendar,bar_map):
    cash=1.0; pos={}; trades=[]; equity=[]; exposure=[]
    rejected=defaultdict(int)
    # large box wins if both scales fire same symbol/date; newest detection as tie-break.
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
        if nd:
            pending[nd].extend(rows)

    for d in calendar:
        # Gap exits
        for sym in list(pos):
            b=bar_map.get(sym,{}).get(d)
            if b is None:continue
            op=float(b["open"]); p=pos[sym]
            px=None;reason=None
            if op<=p["lower"]:px=op;reason="stop"
            elif op>=p["upper"]:px=op;reason="target"
            if px is not None:
                proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                trades.append({**p,"exit_date":d,"exit_price":px,"exit_reason":reason,
                               "net_return":proceeds/p["cost_basis"]-1,
                               "hold_sessions":p["age"]+1})
                del pos[sym]

        # Entries
        candidates=[]
        for q in pending.get(d,[]):
            sym=q["symbol"]
            if sym in pos:
                rejected["already_held"]+=1;continue
            b=bar_map.get(sym,{}).get(d)
            if b is None:
                rejected["missing_next_open"]+=1;continue
            op=float(b["open"]); lo=float(q["lower"]); hi=float(q["upper"])
            if op<=lo:
                rejected["gap_below_stop"]+=1;continue
            if op>=hi:
                rejected["gap_above_target"]+=1;continue
            candidates.append((q,op))

        eq_open=cash
        for sym,p in pos.items():
            b=bar_map.get(sym,{}).get(d)
            px=float(b["open"]) if b is not None else p["last"]
            eq_open += p["shares"]*px
        requested=sum(TARGET_WEIGHT[q["scale"]]*eq_open for q,_ in candidates)
        avail=max(0.0,cash)
        scale=1.0 if requested<=avail or requested<=0 else avail/requested
        for q,op in candidates:
            alloc=TARGET_WEIGHT[q["scale"]]*eq_open*scale
            if alloc<=1e-12 or alloc>cash+1e-10:
                rejected["no_cash"]+=1;continue
            invest=alloc*(1-ENTRY_COST); shares=invest/op; cash-=alloc
            pos[q["symbol"]]={
                "symbol":q["symbol"],"scale":q["scale"],"signal_date":q["signal_date"],
                "entry_date":d,"entry_price":op,"shares":shares,"cost_basis":alloc,
                "lower":float(q["lower"]),"upper":float(q["upper"]),
                "liquidity_rank":int(q["liquidity_rank"]),"adv20_prior":float(q["adv20_prior"]),
                "requested_weight":TARGET_WEIGHT[q["scale"]],
                "actual_entry_weight":alloc/max(eq_open,1e-12),"age":0,"last":op,
            }

        # Intraday exits, stop first if both.
        for sym in list(pos):
            b=bar_map.get(sym,{}).get(d)
            if b is None:continue
            p=pos[sym]; lo=float(b["low"]); hi=float(b["high"]); cl=float(b["close"])
            px=None;reason=None
            if lo<=p["lower"]:px=p["lower"];reason="stop"
            elif hi>=p["upper"]:px=p["upper"];reason="target"
            if px is not None:
                proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                trades.append({**p,"exit_date":d,"exit_price":px,"exit_reason":reason,
                               "net_return":proceeds/p["cost_basis"]-1,
                               "hold_sessions":p["age"]+1})
                del pos[sym]
            else:
                p["last"]=cl;p["age"]+=1

        eq=cash;invested=0.0
        for sym,p in pos.items():
            b=bar_map.get(sym,{}).get(d)
            px=float(b["close"]) if b is not None else p["last"]
            p["last"]=px;v=p["shares"]*px;eq+=v;invested+=v
        equity.append((d,eq));exposure.append((d,0 if eq<=0 else invested/eq))

    if calendar:
        fd=calendar[-1]
        for sym,p in list(pos.items()):
            b=bar_map.get(sym,{}).get(fd)
            px=float(b["close"]) if b is not None else p["last"]
            proceeds=p["shares"]*px*(1-EXIT_COST)
            trades.append({**p,"exit_date":fd,"exit_price":px,"exit_reason":"end_mark",
                           "net_return":proceeds/p["cost_basis"]-1,"hold_sessions":p["age"]})

    vals=[e for _,e in equity]
    y=max((date.fromisoformat(equity[-1][0])-date.fromisoformat(equity[0][0])).days/365.2425,1/365.2425)
    yearly={}
    eqdf=pd.DataFrame(equity,columns=["date","equity"]);eqdf["year"]=eqdf.date.str[:4]
    for yr,g in eqdf.groupby("year"):
        first=float(g.equity.iloc[0]);last=float(g.equity.iloc[-1]);yearly[yr]=last/first-1 if first else None
    out={
        "rank_cap":rank_cap,
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
    }
    return out,trades,equity,exposure

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True)
    args=ap.parse_args();indir=Path(args.indir);outdir=Path(args.outdir);outdir.mkdir(parents=True,exist_ok=True)

    bars_parts=[]
    for p in sorted(indir.glob("**/bars_*.csv.gz")):
        bars_parts.append(pd.read_csv(p))
    if not bars_parts:raise RuntimeError("No yearly bar artifacts")
    bars=pd.concat(bars_parts,ignore_index=True)
    bars["date"]=bars.date.astype(str);bars["ticker"]=bars.ticker.astype(str)
    bars=bars.sort_values(["ticker","date"]).drop_duplicates(["ticker","date"],keep="last")

    sig_parts=[pd.read_csv(p) for p in sorted(indir.glob("**/signals_*.csv"))]
    signals=pd.concat(sig_parts,ignore_index=True) if sig_parts else pd.DataFrame()
    if signals.empty:raise RuntimeError("No signals")
    signals["signal_date"]=signals.signal_date.astype(str);signals["symbol"]=signals.symbol.astype(str)

    spy=bars[bars.ticker=="SPY"].sort_values("date")
    if spy.empty:raise RuntimeError("SPY calendar missing")
    calendar=spy.date.tolist()
    bar_map={}
    for sym,g in bars.groupby("ticker"):
        bar_map[sym]={r["date"]:r for r in g.to_dict("records")}

    results={};primary=None
    for cap in (200,300,500):
        res,tr,eq,ex=run_lane(cap,bars,signals,calendar,bar_map)
        results[f"top{cap}"]=res
        if cap==300:primary=(tr,eq,ex)

    sp0=float(spy.iloc[0].close);sp1=float(spy.iloc[-1].close)
    summary={
        "schema":"PURE-BOX-LIQUID-LEADERS-V1","research_only":True,
        "primary_lane":"top300","window":[calendar[0],calendar[-1]],
        "source":"mito0o852/OHLCV-1m",
        "universe_definition":{
            "rank_metric":"prior-20-session average dollar volume",
            "adv_floor":25_000_000,"price_floor":5.0,
            "lanes":[200,300,500],
            "security_type_caveat":"source has no point-in-time security-type/market-cap/industry master; this is a high-liquidity leader proxy, not exact historical industry leaders"
        },
        "rules":{
            "bottom_fraction":0.20,"small_weight":0.50,"large_weight":1.00,
            "stop":"box_lower","take_profit":"box_upper","both_intraday":"stop_first",
            "entry":"next_US_session_open","cost_per_side_bps":5.0,"extra_alpha_filters":"none"
        },
        "benchmark_SPY_price_return":sp1/sp0-1,
        "lanes":results,
    }
    (outdir/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")

    tr,eq,ex=primary
    keys=["symbol","scale","signal_date","entry_date","entry_price","exit_date","exit_price","exit_reason",
          "net_return","hold_sessions","liquidity_rank","adv20_prior","requested_weight","actual_entry_weight","lower","upper"]
    with (outdir/"top300_trades.csv").open("w",newline="",encoding="utf-8") as fh:
        w=csv.DictWriter(fh,fieldnames=keys,extrasaction="ignore");w.writeheader();w.writerows(tr)
    exmap=dict(ex)
    with (outdir/"top300_equity.csv").open("w",newline="",encoding="utf-8") as fh:
        w=csv.writer(fh);w.writerow(["date","equity","exposure"])
        for d,e in eq:w.writerow([d,f"{e:.10f}",f"{exmap[d]:.10f}"])

    def pc(v):return "—" if v is None else f"{100*v:.2f}%"
    lines=["# Pure Box Long — Liquid Leaders V1","","Primary lane: **Top 300 by prior ADV20**",""]
    for cap in (200,300,500):
        r=results[f"top{cap}"];p=r["portfolio"];t=r["trade_stats_all"]
        lines += [f"## Top {cap}",
                  f"- Total return: {pc(p['total_return'])}",
                  f"- CAGR: {pc(p['cagr'])}",
                  f"- Max drawdown: {pc(p['max_drawdown'])}",
                  f"- Daily Sharpe: {p['daily_sharpe']}",
                  f"- Average exposure: {pc(p['avg_exposure'])}",
                  f"- Trades: {t.get('trades',0)}",
                  f"- Win rate: {pc(t.get('win_rate'))}",
                  f"- Mean trade return: {pc(t.get('mean_return'))}",
                  f"- Profit factor: {t.get('profit_factor')}",
                  ""]
    lines += ["## Caveat","This is a causal high-liquidity leader proxy. The source does not contain a point-in-time stock/ETF type, market-cap or industry master, so it is not yet an exact historical industry-leader universe."]
    (outdir/"RESULT.md").write_text("\n".join(lines),encoding="utf-8")
    print(json.dumps(summary,indent=2))

if __name__=="__main__":
    main()
