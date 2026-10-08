#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,statistics,math
from collections import defaultdict
from pathlib import Path
import pandas as pd
import research_pure_box_core_geometry_simplicity_v13 as v13
import research_pure_box_capital_architecture_v22 as v22
import research_pure_box_capital_priority_v26 as v26

ENTRY_COST=v13.ENTRY_COST; EXIT_COST=v13.EXIT_COST

def pf(rs):
    w=sum(x for x in rs if x>0);l=-sum(x for x in rs if x<0)
    return w/l if l>0 else None

def independent_trade(c,cal,bm,max_hold=15):
    s=str(c["symbol"]);d=str(c["direct_entry_date"])
    idx={x:i for i,x in enumerate(cal)}
    if d not in idx:return None
    b0=bm.get(s,{}).get(d)
    if b0 is None:return None
    op=float(b0["open"]);lo=float(c["lower"]);hi=float(c["upper"]);target=lo+.60*(hi-lo)
    if not(lo<op<target):return None
    ef=(op-lo)/(hi-lo)
    if ef>.20:return None
    start=idx[d]
    entry_costed=op*(1+ENTRY_COST)
    px=op;reason=""
    for age in range(1,max_hold+1):
        if start+age-1>=len(cal):break
        day=cal[start+age-1];b=bm.get(s,{}).get(day)
        if b is None:continue
        o=float(b["open"])
        if o<=lo:px=o;reason="stop_gap"
        elif o>=target:px=o;reason="target_gap"
        elif float(b["low"])<=lo:px=lo;reason="stop"
        elif float(b["high"])>=target:px=target;reason="target60"
        elif age>=max_hold:px=float(b["close"]);reason=f"time_h{max_hold}"
        else:continue
        break
    net=px*(1-EXIT_COST)/entry_costed-1
    return {
      "symbol":s,"entry_date":d,"signal_date":str(c["signal_date"]),"year":d[:4],
      "liquidity_rank":int(c["liquidity_rank"]),"entry_fraction":ef,
      "box_width_pct":(hi-lo)/op,"scale":str(c["scale"]),
      "net_return":net,"exit_reason":reason
    }

def band(r):
    r=int(r)
    if r<=100:return "001_100"
    if r<=200:return "101_200"
    if r<=300:return "201_300"
    if r<=400:return "301_400"
    return "401_500"

def stats(g):
    rs=[float(x) for x in g.net_return.tolist()]
    return {
      "n":len(rs),
      "mean_trade":statistics.mean(rs) if rs else None,
      "median_trade":statistics.median(rs) if rs else None,
      "profit_factor":pf(rs) if rs else None,
      "win_rate":sum(x>0 for x in rs)/len(rs) if rs else None,
      "sum_trade_return":sum(rs)
    }

def patched_run(cands,cal,bm,policy):
    if policy!="REVERSE_LIQUIDITY_FIRST":
        return v26.run(cands,cal,bm,policy)
    # temporarily mirror v26 by mapping ranks so normal LIQUIDITY_FIRST orders worst liquidity first
    cc=[]
    for c in cands:
        z=dict(c);z["liquidity_rank"]=100000-int(c["liquidity_rank"]);cc.append(z)
    r=v26.run(cc,cal,bm,"LIQUIDITY_FIRST")
    return r

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=v13.load(a.indir)
    summary={"schema":"PURE-BOX-SIMPLE-CORE-CAPITAL-PRIORITY-ROBUSTNESS-V27","results":{}}
    portrows=[];tradeframes=[]
    for cap in (300,500):
        cs=v22.bottom20(v13.strict_signals(sig,cap,cal,idx,nxt,bm))
        # independent H15 trade outcomes
        tr=[independent_trade(c,cal,bm,15) for c in cs]
        tdf=pd.DataFrame([x for x in tr if x is not None])
        tdf["rank_band"]=tdf.liquidity_rank.map(band)
        # same-day priority position under liquidity ordering
        tdf=tdf.sort_values(["entry_date","liquidity_rank","entry_fraction","symbol"])
        tdf["same_day_liq_position"]=tdf.groupby("entry_date").cumcount()+1
        tdf["priority_bucket"]=tdf.same_day_liq_position.map(lambda x:"rank1" if x==1 else ("rank2" if x==2 else "rank3plus"))
        bands={b:stats(g) for b,g in tdf.groupby("rank_band")}
        priority={b:stats(g) for b,g in tdf.groupby("priority_bucket")}
        yearly={y:stats(g) for y,g in tdf.groupby("year")}
        loyo={}
        years=sorted(tdf.year.unique())
        for y in years:
            loyo[y]=stats(tdf[tdf.year!=y])
        policies=("PRO_RATA","LIQUIDITY_FIRST","REVERSE_LIQUIDITY_FIRST","LOW_ENTRY_FRACTION_FIRST")
        ports={}
        for pol in policies:
            r=patched_run(cs,cal,bm,pol)
            ports[pol]=r
            portrows.append({"rank_cap":cap,"policy":pol,**r})
        summary["results"][f"top{cap}"]={
          "candidate_n":len(cs),
          "trade_level":{"liquidity_bands":bands,"same_day_priority":priority,"yearly":yearly,"leave_one_year_out":loyo},
          "portfolio":ports
        }
        tdf["rank_cap"]=cap;tradeframes.append(tdf)
    pd.concat(tradeframes,ignore_index=True).to_csv(out/"trade_anatomy.csv",index=False)
    pd.DataFrame(portrows).to_csv(out/"portfolio_results.csv",index=False)
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
