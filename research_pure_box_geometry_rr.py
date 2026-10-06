#!/usr/bin/env python3
from __future__ import annotations

import argparse, json, math, statistics
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ENTRY_COST=0.0005
EXIT_COST=0.0005
TARGET_WEIGHT={"small":0.50,"large":1.00}
RANK_CAPS=(300,500)

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

def pf(rr):
    w=[x for x in rr if x>0]; l=[x for x in rr if x<0]
    return sum(w)/abs(sum(l)) if l else (float("inf") if w else None)

def trade_stats(z):
    if not z:return {"trades":0}
    rr=[float(t["net_return"]) for t in z]
    return {
        "trades":len(z),
        "win_rate":sum(x>0 for x in rr)/len(rr),
        "mean_return":statistics.mean(rr),
        "median_return":statistics.median(rr),
        "profit_factor":pf(rr),
        "avg_hold_sessions":statistics.mean(float(t["hold_sessions"]) for t in z),
        "target_rate":sum(t["exit_reason"]=="target" for t in z)/len(z),
        "stop_rate":sum(t["exit_reason"]=="stop" for t in z)/len(z),
    }

def load_inputs(indir):
    bars=pd.concat([pd.read_csv(p) for p in sorted(Path(indir).glob("**/bars_*.csv.gz"))],ignore_index=True)
    bars["date"]=bars.date.astype(str); bars["ticker"]=bars.ticker.astype(str)
    bars=bars.sort_values(["ticker","date"]).drop_duplicates(["ticker","date"],keep="last")
    signals=pd.concat([pd.read_csv(p) for p in sorted(Path(indir).glob("**/signals_*.csv"))],ignore_index=True)
    signals["signal_date"]=signals.signal_date.astype(str); signals["symbol"]=signals.symbol.astype(str)
    spy=bars[bars.ticker=="SPY"].sort_values("date")
    calendar=spy.date.tolist()
    idx={d:i for i,d in enumerate(calendar)}
    next_session={calendar[i]:calendar[i+1] for i in range(len(calendar)-1)}
    bar_map={sym:{r["date"]:r for r in g.to_dict("records")} for sym,g in bars.groupby("ticker")}
    return bars,signals,calendar,idx,next_session,bar_map

def dedup_signals(signals,rank_cap):
    s=signals[signals.liquidity_rank<=rank_cap].copy()
    s["scale_order"]=s.scale.map({"small":0,"large":1}).fillna(0)
    s=s.sort_values(["signal_date","symbol","scale_order","detected_at"],
                    ascending=[True,True,False,False])
    return s.drop_duplicates(["signal_date","symbol"],keep="first")

def candidate(q,entry_date,bar,idx):
    op=float(bar["open"]); lower=float(q["lower"]); upper=float(q["upper"])
    if op<=lower or op>=upper:return None
    width=upper-lower
    downside=(op-lower)/op
    upside=(upper-op)/op
    if downside<=0 or width<=0:return None
    return {
        **q,
        "entry_date":entry_date,
        "entry_price":op,
        "lower":lower,
        "upper":upper,
        "entry_fraction":(op-lower)/width,
        "downside_pct":downside,
        "upside_pct":upside,
        "rr":upside/downside,
        "box_width_pct":width/op,
        "box_age_sessions":max(0,idx.get(str(q["signal_date"]),0)-idx.get(str(q["detected_at"]),idx.get(str(q["signal_date"]),0))),
    }

def build_candidates(signals,rank_cap,next_session,bar_map,idx):
    s=dedup_signals(signals,rank_cap)
    out=[]
    for q in s.to_dict("records"):
        d=next_session.get(str(q["signal_date"]))
        if not d:continue
        b=bar_map.get(str(q["symbol"]),{}).get(d)
        if b is None:continue
        c=candidate(q,d,b,idx)
        if c is not None:out.append(c)
    return out

def isolated_opportunities(candidates,calendar,bar_map):
    # One executable opportunity at a time per symbol; repeated signals while
    # an isolated position is open are skipped.
    by_entry=defaultdict(list)
    for c in candidates:by_entry[c["entry_date"]].append(c)
    active={}
    trades=[]
    for d in calendar:
        # Existing gap exits.
        for sym in list(active):
            b=bar_map.get(sym,{}).get(d)
            if b is None:continue
            p=active[sym]; op=float(b["open"])
            px=reason=None
            if op<=p["lower"]:px=op;reason="stop"
            elif op>=p["upper"]:px=op;reason="target"
            if px is not None:
                net=(px*(1-EXIT_COST))/(p["entry_price"]/(1-ENTRY_COST))-1
                trades.append({**p,"exit_date":d,"exit_price":px,"exit_reason":reason,"net_return":net,"hold_sessions":p["age"]+1})
                del active[sym]
        # New entries.
        for c in by_entry.get(d,[]):
            if c["symbol"] in active:continue
            active[c["symbol"]]={**c,"age":0}
        # Intraday exits, conservative stop-first.
        for sym in list(active):
            b=bar_map.get(sym,{}).get(d)
            if b is None:continue
            p=active[sym]; lo=float(b["low"]); hi=float(b["high"])
            px=reason=None
            if lo<=p["lower"]:px=p["lower"];reason="stop"
            elif hi>=p["upper"]:px=p["upper"];reason="target"
            if px is not None:
                net=(px*(1-EXIT_COST))/(p["entry_price"]/(1-ENTRY_COST))-1
                trades.append({**p,"exit_date":d,"exit_price":px,"exit_reason":reason,"net_return":net,"hold_sessions":p["age"]+1})
                del active[sym]
            else:p["age"]+=1
    if calendar:
        fd=calendar[-1]
        for sym,p in active.items():
            b=bar_map.get(sym,{}).get(fd)
            px=float(b["close"]) if b is not None else p["entry_price"]
            net=(px*(1-EXIT_COST))/(p["entry_price"]/(1-ENTRY_COST))-1
            trades.append({**p,"exit_date":fd,"exit_price":px,"exit_reason":"end_mark","net_return":net,"hold_sessions":p["age"]})
    return trades

def bin_feature(df,feature,period,scale):
    z=df.copy()
    if period=="discovery":z=z[z.signal_date<="2022-12-31"]
    elif period=="validation":z=z[z.signal_date>="2023-01-01"]
    if scale!="all":z=z[z.scale==scale]
    z=z[np.isfinite(z[feature].astype(float))].copy()
    if len(z)<25:return []
    try:
        z["bin"]=pd.qcut(z[feature],5,labels=False,duplicates="drop")+1
    except ValueError:return []
    rows=[]
    for b,g in z.groupby("bin",sort=True):
        rr=g.net_return.astype(float).tolist()
        rows.append({
            "feature":feature,"period":period,"scale":scale,"quintile":int(b),
            "n":len(g),"feature_min":float(g[feature].min()),"feature_median":float(g[feature].median()),"feature_max":float(g[feature].max()),
            "mean_return":float(g.net_return.mean()),"median_return":float(g.net_return.median()),
            "win_rate":float((g.net_return>0).mean()),"profit_factor":pf(rr),
            "target_rate":float((g.exit_reason=="target").mean()),"stop_rate":float((g.exit_reason=="stop").mean()),
            "avg_hold_sessions":float(g.hold_sessions.mean()),
        })
    return rows

def portfolio(candidates,calendar,bar_map,mode="baseline",min_rr=None):
    by_entry=defaultdict(list)
    for c in candidates:
        if min_rr is None or c["rr"]>=min_rr:by_entry[c["entry_date"]].append(c)
    cash=1.0;pos={};trades=[];eq=[];expo=[]
    for d in calendar:
        for sym in list(pos):
            b=bar_map.get(sym,{}).get(d)
            if b is None:continue
            p=pos[sym];op=float(b["open"]);px=reason=None
            if op<=p["lower"]:px=op;reason="stop"
            elif op>=p["upper"]:px=op;reason="target"
            if px is not None:
                proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                trades.append({**p,"exit_date":d,"exit_price":px,"exit_reason":reason,
                               "net_return":proceeds/p["cost_basis"]-1,"hold_sessions":p["age"]+1})
                del pos[sym]
        cand=[c for c in by_entry.get(d,[]) if c["symbol"] not in pos]
        if mode=="rr_priority":cand.sort(key=lambda x:(-x["rr"],x["symbol"]))
        elif mode=="upside_priority":cand.sort(key=lambda x:(-x["upside_pct"],x["symbol"]))
        elif mode=="lower_edge_priority":cand.sort(key=lambda x:(x["entry_fraction"],x["symbol"]))
        else:cand.sort(key=lambda x:x["symbol"])

        eq_open=cash
        for sym,p in pos.items():
            b=bar_map.get(sym,{}).get(d)
            px=float(b["open"]) if b is not None else p["last"]
            eq_open+=p["shares"]*px
        if mode=="baseline":
            req=sum(TARGET_WEIGHT[c["scale"]]*eq_open for c in cand)
            scale=1.0 if req<=cash or req<=0 else cash/req
            allocs=[(c,TARGET_WEIGHT[c["scale"]]*eq_open*scale) for c in cand]
        else:
            rem=cash;allocs=[]
            for c in cand:
                want=TARGET_WEIGHT[c["scale"]]*eq_open
                alloc=min(want,rem)
                if alloc>1e-12:
                    allocs.append((c,alloc));rem-=alloc
                if rem<=1e-12:break
        for c,alloc in allocs:
            if alloc<=1e-12 or alloc>cash+1e-10:continue
            op=c["entry_price"];invest=alloc*(1-ENTRY_COST);shares=invest/op;cash-=alloc
            pos[c["symbol"]]={**c,"shares":shares,"cost_basis":alloc,
                              "requested_weight":TARGET_WEIGHT[c["scale"]],
                              "actual_entry_weight":alloc/max(eq_open,1e-12),"age":0,"last":op}
        for sym in list(pos):
            b=bar_map.get(sym,{}).get(d)
            if b is None:continue
            p=pos[sym];lo=float(b["low"]);hi=float(b["high"]);cl=float(b["close"]);px=reason=None
            if lo<=p["lower"]:px=p["lower"];reason="stop"
            elif hi>=p["upper"]:px=p["upper"];reason="target"
            if px is not None:
                proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                trades.append({**p,"exit_date":d,"exit_price":px,"exit_reason":reason,
                               "net_return":proceeds/p["cost_basis"]-1,"hold_sessions":p["age"]+1})
                del pos[sym]
            else:p["last"]=cl;p["age"]+=1
        v=cash;inv=0.0
        for sym,p in pos.items():
            b=bar_map.get(sym,{}).get(d)
            px=float(b["close"]) if b is not None else p["last"];p["last"]=px
            q=p["shares"]*px;v+=q;inv+=q
        eq.append((d,v));expo.append(inv/v if v>0 else 0.0)
    if calendar:
        fd=calendar[-1]
        for sym,p in pos.items():
            b=bar_map.get(sym,{}).get(fd);px=float(b["close"]) if b is not None else p["last"]
            proceeds=p["shares"]*px*(1-EXIT_COST)
            trades.append({**p,"exit_date":fd,"exit_price":px,"exit_reason":"end_mark",
                           "net_return":proceeds/p["cost_basis"]-1,"hold_sessions":p["age"]})
    vals=[v for _,v in eq]
    y=max((date.fromisoformat(eq[-1][0])-date.fromisoformat(eq[0][0])).days/365.2425,1/365.2425)
    edf=pd.DataFrame(eq,columns=["date","equity"]);edf["year"]=edf.date.str[:4]
    yearly={yr:float(g.equity.iloc[-1]/g.equity.iloc[0]-1) for yr,g in edf.groupby("year")}
    return {
        "mode":mode,"min_rr":min_rr,
        "portfolio":{"total_return":vals[-1]/vals[0]-1,"cagr":(vals[-1]/vals[0])**(1/y)-1,
                     "max_drawdown":mdd(vals),"daily_sharpe":sharpe(eq),
                     "avg_exposure":statistics.mean(expo)},
        "trade_stats_all":trade_stats(trades),
        "trade_stats_small":trade_stats([t for t in trades if t["scale"]=="small"]),
        "trade_stats_large":trade_stats([t for t in trades if t["scale"]=="large"]),
        "yearly_returns":yearly,
    }

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True)
    a=ap.parse_args();out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    bars,signals,calendar,idx,next_session,bar_map=load_inputs(a.indir)
    summary={"schema":"PURE-BOX-GEOMETRY-RR-V1","window":[calendar[0],calendar[-1]],"research_only":True,"rank_caps":{}}
    bin_rows=[]
    for cap in RANK_CAPS:
        candidates=build_candidates(signals,cap,next_session,bar_map,idx)
        opp=isolated_opportunities(candidates,calendar,bar_map)
        df=pd.DataFrame(opp)
        for feature in ["rr","entry_fraction","downside_pct","upside_pct","box_width_pct","box_age_sessions"]:
            for period in ["full","discovery","validation"]:
                for scale in ["all","small","large"]:
                    bin_rows.extend(bin_feature(df,feature,period,scale))
        portfolios={}
        for mode in ["baseline","rr_priority","upside_priority","lower_edge_priority"]:
            portfolios[mode]=portfolio(candidates,calendar,bar_map,mode=mode)
        for thr in [1.0,2.0,3.0,4.0]:
            portfolios[f"rr_min_{int(thr)}"]=portfolio(candidates,calendar,bar_map,mode="rr_priority",min_rr=thr)
        summary["rank_caps"][f"top{cap}"]={
            "candidate_count":len(candidates),"isolated_opportunity_count":len(opp),
            "isolated_trade_stats":trade_stats(opp),"portfolios":portfolios,
        }
        pd.DataFrame(opp).to_csv(out/f"top{cap}_isolated_trades.csv.gz",index=False,compression="gzip")
    bdf=pd.DataFrame(bin_rows);bdf.to_csv(out/"geometry_quintiles.csv",index=False)
    # Compact monotonicity receipt: Q1 vs Q5 and rank correlation of quintile with mean return/PF.
    receipt=[]
    for (feature,period,scale),g in bdf.groupby(["feature","period","scale"]):
        g=g.sort_values("quintile")
        if len(g)<2:continue
        receipt.append({
            "feature":feature,"period":period,"scale":scale,
            "q1_mean":float(g.iloc[0].mean_return),"q5_mean":float(g.iloc[-1].mean_return),
            "q1_pf":float(g.iloc[0].profit_factor),"q5_pf":float(g.iloc[-1].profit_factor),
            "mean_spearman":float(g.quintile.corr(g.mean_return,method="spearman")),
            "pf_spearman":float(g.quintile.corr(g.profit_factor,method="spearman")),
        })
    pd.DataFrame(receipt).to_csv(out/"monotonicity_receipt.csv",index=False)
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps({
        cap:{m:{**r["portfolio"],"pf":r["trade_stats_all"].get("profit_factor"),"trades":r["trade_stats_all"].get("trades")}
             for m,r in v["portfolios"].items()}
        for cap,v in summary["rank_caps"].items()
    },indent=2))

if __name__=="__main__":
    main()
