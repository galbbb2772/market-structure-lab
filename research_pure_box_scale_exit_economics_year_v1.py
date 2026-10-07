#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math, statistics
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd

ENTRY_COST=.0005
EXIT_COST=.0005
ALLOC=.10
TARGETS={"50":.50,"60":.60,"80":.80,"100":1.00}
HORIZONS=(10,20,40)
FRESH={
  300:{"small":12,"large":23},
  500:{"small":12,"large":24},
}

def pf(rs):
    w=sum(x for x in rs if x>0);l=-sum(x for x in rs if x<0)
    return w/l if l>0 else None

def mdd(vals):
    peak=vals[0];dd=0.0
    for x in vals:
        peak=max(peak,x);dd=min(dd,x/peak-1)
    return dd

def sharpe(vals):
    if len(vals)<3:return None
    r=[vals[i]/vals[i-1]-1 for i in range(1,len(vals)) if vals[i-1]>0]
    if len(r)<2:return None
    s=statistics.stdev(r)
    return None if s==0 else statistics.mean(r)/s*math.sqrt(252)

def load(indir,year):
    p=Path(indir)
    sigp=next(p.glob(f"**/signals_{year}.csv"))
    sig=pd.read_csv(sigp)
    sig["signal_date"]=sig.signal_date.astype(str)
    sig["detected_at"]=sig.detected_at.astype(str)
    sig["symbol"]=sig.symbol.astype(str)
    sig=sig[sig.liquidity_rank<=500].copy()
    sig["scale_order"]=sig.scale.map({"small":0,"large":1}).fillna(0)
    sig=sig.sort_values(["signal_date","symbol","scale_order","detected_at"],
                        ascending=[True,True,False,False]).drop_duplicates(
                            ["signal_date","symbol"],keep="first")
    syms=set(sig.symbol)
    kept=[];dates=set()
    for bp in sorted(p.glob("**/bars_*.csv.gz")):
        for ch in pd.read_csv(bp,chunksize=300000):
            ch["date"]=ch.date.astype(str);ch["ticker"]=ch.ticker.astype(str)
            dates.update(ch.date.unique().tolist())
            z=ch[ch.ticker.isin(syms)].copy()
            if len(z):kept.append(z)
    bars=pd.concat(kept,ignore_index=True)
    bars=bars.sort_values(["ticker","date"]).drop_duplicates(["ticker","date"],keep="last")
    cal=sorted(dates)
    idx={d:i for i,d in enumerate(cal)}
    nxt={cal[i]:cal[i+1] for i in range(len(cal)-1)}
    bm={s:{r["date"]:r for r in g.to_dict("records")} for s,g in bars.groupby("ticker")}
    return sig,cal,idx,nxt,bm

def confirmed(sig,cal,idx,nxt,bm):
    out=[]
    for q in sig.to_dict("records"):
        d0=q["signal_date"];d1=nxt.get(d0);d2=nxt.get(d1) if d1 else None
        if not d1 or not d2:continue
        sm=bm.get(q["symbol"],{})
        b0=sm.get(d0);b1=sm.get(d1);b2=sm.get(d2)
        if b0 is None or b1 is None or b2 is None:continue
        lo=float(q["lower"]);hi=float(q["upper"]);width=max(hi-lo,1e-12)
        op1=float(b1["open"]);op2=float(b2["open"])
        if not(lo<op1<hi and lo<op2<hi):continue
        if float(b1["low"])<float(b0["low"]):continue
        if float(b1["close"])<=float(b1["open"]):continue
        age=max(0,idx[d0]-idx.get(q["detected_at"],idx[d0]))
        out.append({
          **q,"lower":lo,"upper":hi,"box_age_sessions":age,
          "confirmation_date":d1,"entry_date":d2,"entry_price":op2,
          "entry_box_position":(op2-lo)/width,
        })
    return pd.DataFrame(out)

def run(cands,calendar,bm,year,target_frac,max_hold):
    year_days=[d for d in calendar if d.startswith(str(year))]
    if not year_days:
        raise RuntimeError(f"no calendar for {year}")
    year_set=set(year_days);yidx={d:i for i,d in enumerate(year_days)}
    last_i=len(year_days)-1
    cands=cands[cands.entry_date.astype(str).isin(year_set)].copy()
    # Require a full holding window to remain inside the entry year.
    cands=cands[cands.entry_date.map(lambda d:yidx.get(str(d),10**9)+max_hold-1<=last_i)]
    by=defaultdict(list)
    for c in cands.to_dict("records"):by[str(c["entry_date"])].append(c)

    cash=1.0;pos={};tr=[];vals=[];exposures=[];concurrency=[]
    entry_alloc_sum=0.0;entry_count=0

    for d in year_days:
        # Opening gaps.
        for sym in list(pos):
            b=bm.get(sym,{}).get(d)
            if b is None:continue
            p=pos[sym];op=float(b["open"]);px=None;reason=None
            if op<=p["lower"]:px=op;reason="stop_gap"
            elif op>=p["target"]:px=op;reason="target_gap"
            if px is not None:
                hold=yidx[d]-p["entry_i"]+1
                proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                tr.append({**p,"exit_date":d,"exit_price":px,"exit_reason":reason,
                           "holding_sessions":hold,"net_return":proceeds/p["cost_basis"]-1,
                           "mfe_return":max(p["max_price"],op)/p["entry_price"]-1,
                           "mae_return":min(p["min_price"],op)/p["entry_price"]-1})
                del pos[sym]

        cand=[c for c in by.get(d,[]) if c["symbol"] not in pos]
        cand.sort(key=lambda x:(x["symbol"],x["signal_date"]))
        ded=[];seen=set()
        for c in cand:
            if c["symbol"] in seen:continue
            seen.add(c["symbol"]);ded.append(c)
        cand=ded

        eq_open=cash
        for sym,p in pos.items():
            b=bm.get(sym,{}).get(d)
            eq_open+=p["shares"]*(float(b["open"]) if b is not None else p["last"])

        if cand:
            req=[ALLOC*eq_open]*len(cand)
            total=min(cash,sum(req))
            scale=total/sum(req) if sum(req)>0 else 0
            alloc=[r*scale for r in req]
            for c,a in zip(cand,alloc):
                if a<=1e-12:continue
                sm=bm.get(c["symbol"],{});b=sm.get(d)
                if b is None:continue
                op=float(b["open"]);lo=float(c["lower"]);hi=float(c["upper"])
                target=lo+target_frac*(hi-lo)
                if not(lo<op<target):continue
                invest=a*(1-ENTRY_COST);cash-=a
                pos[c["symbol"]]={
                  **c,"target":target,"shares":invest/op,"cost_basis":a,
                  "entry_price":op,"entry_equity":eq_open,"entry_i":yidx[d],
                  "last":op,"max_price":op,"min_price":op
                }
                entry_alloc_sum+=a;entry_count+=1

        # Intraday barriers / max hold.
        for sym in list(pos):
            b=bm.get(sym,{}).get(d)
            p=pos[sym]
            hold=yidx[d]-p["entry_i"]+1
            if b is None:
                if hold>=max_hold:
                    px=float(p["last"]);reason="max_hold_stale"
                    proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                    tr.append({**p,"exit_date":d,"exit_price":px,"exit_reason":reason,
                               "holding_sessions":hold,"net_return":proceeds/p["cost_basis"]-1,
                               "mfe_return":p["max_price"]/p["entry_price"]-1,
                               "mae_return":p["min_price"]/p["entry_price"]-1})
                    del pos[sym]
                continue
            lo=float(b["low"]);hi=float(b["high"]);cl=float(b["close"])
            px=None;reason=None
            if lo<=p["lower"]:
                px=float(p["lower"]);reason="stop"
                p["min_price"]=min(p["min_price"],px)
            elif hi>=p["target"]:
                px=float(p["target"]);reason="target"
                p["max_price"]=max(p["max_price"],px);p["min_price"]=min(p["min_price"],lo)
            elif hold>=max_hold:
                px=cl;reason="max_hold"
                p["max_price"]=max(p["max_price"],hi);p["min_price"]=min(p["min_price"],lo)
            else:
                p["max_price"]=max(p["max_price"],hi);p["min_price"]=min(p["min_price"],lo);p["last"]=cl

            if px is not None:
                proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                tr.append({**p,"exit_date":d,"exit_price":px,"exit_reason":reason,
                           "holding_sessions":hold,"net_return":proceeds/p["cost_basis"]-1,
                           "mfe_return":p["max_price"]/p["entry_price"]-1,
                           "mae_return":p["min_price"]/p["entry_price"]-1})
                del pos[sym]

        val=cash;inv=0.0
        for sym,p in pos.items():
            b=bm.get(sym,{}).get(d)
            px=float(b["close"]) if b is not None else p["last"];p["last"]=px
            q=p["shares"]*px;val+=q;inv+=q
        vals.append(val);exposures.append(inv/val if val>0 else 0.0);concurrency.append(len(pos))

    if pos:
        raise RuntimeError(f"positions remained despite full-window eligibility: {len(pos)}")

    rs=[float(t["net_return"]) for t in tr]
    holds=[int(t["holding_sessions"]) for t in tr]
    capdays=sum((float(t["cost_basis"])/float(t["entry_equity"]))*int(t["holding_sessions"]) for t in tr)
    reasons=pd.Series([t["exit_reason"] for t in tr],dtype=str).value_counts()
    total_ret=vals[-1]-1 if vals else 0.0
    avgexp=statistics.mean(exposures) if exposures else 0.0
    return {
      "total_return":total_ret,
      "max_drawdown":mdd(vals),
      "sharpe":sharpe(vals),
      "avg_exposure":avgexp,
      "avg_concurrent_positions":statistics.mean(concurrency) if concurrency else 0.0,
      "entries":entry_count,
      "completed_trades":len(tr),
      "win_rate":sum(x>0 for x in rs)/len(rs) if rs else None,
      "mean_trade":statistics.mean(rs) if rs else None,
      "median_trade":statistics.median(rs) if rs else None,
      "profit_factor":pf(rs),
      "gross_positive_return_sum":sum(x for x in rs if x>0),
      "gross_negative_return_abs_sum":-sum(x for x in rs if x<0),
      "mean_holding_sessions":statistics.mean(holds) if holds else None,
      "median_holding_sessions":statistics.median(holds) if holds else None,
      "target_exit_share":int(reasons.get("target",0)+reasons.get("target_gap",0))/len(tr) if tr else None,
      "stop_exit_share":int(reasons.get("stop",0)+reasons.get("stop_gap",0))/len(tr) if tr else None,
      "max_hold_exit_share":int(reasons.get("max_hold",0)+reasons.get("max_hold_stale",0))/len(tr) if tr else None,
      "mean_mfe_return":statistics.mean([float(t["mfe_return"]) for t in tr]) if tr else None,
      "mean_mae_return":statistics.mean([float(t["mae_return"]) for t in tr]) if tr else None,
      "turnover_alloc_over_mean_equity":entry_alloc_sum/(statistics.mean(vals) if vals else 1.0),
      "capital_days":capdays,
      "return_per_100_capital_days":total_ret/capdays*100 if capdays>0 else None,
      "return_over_avg_exposure":total_ret/avgexp if avgexp>0 else None,
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--year",type=int,required=True)
    ap.add_argument("--indir",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

    sig,cal,idx,nxt,bm=load(a.indir,a.year)
    c=confirmed(sig,cal,idx,nxt,bm)
    rows=[]
    for cap in (300,500):
        for scale in ("small","large"):
            z=c[(c.liquidity_rank<=cap)&(c.scale==scale)&(c.box_age_sessions<=FRESH[cap][scale])].copy()
            for sample in ("common_eligible","target_specific"):
                for label,frac in TARGETS.items():
                    if sample=="common_eligible":
                        base=z[z.entry_box_position<.50].copy()
                    else:
                        base=z[z.entry_box_position<frac].copy()
                    for h in HORIZONS:
                        r=run(base,cal,bm,a.year,frac,h)
                        rows.append({
                          "year":a.year,"rank_cap":cap,"scale":scale,
                          "sample_panel":sample,"target_fraction":frac,
                          "max_hold":h,"candidate_count_before_full_window":int(len(base)),**r
                        })
    df=pd.DataFrame(rows)
    df.to_csv(out/f"scale_exit_economics_{a.year}.csv",index=False)
    print(df.to_string(index=False))

if __name__=="__main__":
    main()
