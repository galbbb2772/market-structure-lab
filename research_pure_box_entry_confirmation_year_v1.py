#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math, statistics
from collections import defaultdict
from pathlib import Path
import pandas as pd
import numpy as np

ENTRY_COST=.0005
EXIT_COST=.0005
TARGET_WEIGHT={"small":.5,"large":1.0}
VARIANTS=("baseline_next_open","hold_then_enter","no_new_low_green","lower_touch_reclaim","failed_break_reclaim")

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

def run(cands,calendar,bm,start,end):
    by=defaultdict(list)
    for c in cands:
        if start<=c["entry_date"]<=end:by[c["entry_date"]].append(c)
    days=[d for d in calendar if start<=d<=end]
    cash=1.0; pos={}; trades=[]; eq=[]; expo=[]
    for d in days:
        # Gap exits first.
        for sym in list(pos):
            b=bm.get(sym,{}).get(d)
            if b is None:continue
            p=pos[sym]; op=float(b["open"]); px=None; reason=None
            if op<=p["lower"]:px=op;reason="stop"
            elif op>=p["upper"]:px=op;reason="target"
            if px is not None:
                proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                trades.append({**p,"exit_reason":reason,"net_return":proceeds/p["cost_basis"]-1})
                del pos[sym]

        cand=[c for c in by.get(d,[]) if c["symbol"] not in pos]
        cand.sort(key=lambda x:(x["symbol"],-x["scale_order"],x["signal_date"]))
        ded=[];seen=set()
        for c in cand:
            if c["symbol"] in seen:continue
            seen.add(c["symbol"]);ded.append(c)
        cand=ded

        eq_open=cash
        for sym,p in pos.items():
            b=bm.get(sym,{}).get(d)
            eq_open+=p["shares"]*(float(b["open"]) if b is not None else p["last"])

        req=sum(TARGET_WEIGHT[c["scale"]]*eq_open for c in cand)
        scale=1.0 if req<=cash or req<=0 else cash/req
        for c in cand:
            alloc=TARGET_WEIGHT[c["scale"]]*eq_open*scale
            if alloc<=1e-12 or alloc>cash+1e-10:continue
            invest=alloc*(1-ENTRY_COST);cash-=alloc
            pos[c["symbol"]]={**c,"shares":invest/c["entry_price"],"cost_basis":alloc,"last":c["entry_price"]}

        # Same-day intraday exits, conservative stop-first.
        for sym in list(pos):
            b=bm.get(sym,{}).get(d)
            if b is None:continue
            p=pos[sym];lo=float(b["low"]);hi=float(b["high"]);cl=float(b["close"]);px=None;reason=None
            if lo<=p["lower"]:px=p["lower"];reason="stop"
            elif hi>=p["upper"]:px=p["upper"];reason="target"
            if px is not None:
                proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                trades.append({**p,"exit_reason":reason,"net_return":proceeds/p["cost_basis"]-1})
                del pos[sym]
            else:p["last"]=cl

        val=cash;inv=0.0
        for sym,p in pos.items():
            b=bm.get(sym,{}).get(d)
            px=float(b["close"]) if b is not None else p["last"];p["last"]=px
            v=p["shares"]*px;val+=v;inv+=v
        eq.append((d,val));expo.append(inv/val if val>0 else 0.0)

    if not eq:
        return {"total_return":None,"max_drawdown":None,"sharpe":None,"avg_exposure":None,
                "trades":0,"profit_factor":None,"mean_trade":None}
    vals=[v for _,v in eq]; rs=[t["net_return"] for t in trades]
    return {
        "total_return":vals[-1]/vals[0]-1,
        "max_drawdown":mdd(vals),
        "sharpe":sharpe(eq),
        "avg_exposure":statistics.mean(expo),
        "trades":len(trades),
        "profit_factor":pf(rs),
        "mean_trade":statistics.mean(rs) if rs else None,
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--year",type=int,required=True)
    ap.add_argument("--cap",type=int,required=True,choices=[300,500])
    ap.add_argument("--indir",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    p=Path(a.indir);out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

    vit=json.load(open("research/pure_box_liquid_leaders_v1/vitality_v2/summary.json"))
    annual=vit["rank_caps"][f"top{a.cap}"]["annual_walk_forward"]
    th=next(x["thresholds"] for x in annual if int(x["year"])==a.year)

    sigp=next(p.glob(f"**/signals_{a.year}.csv"))
    sig=pd.read_csv(sigp)
    sig["signal_date"]=sig.signal_date.astype(str);sig["detected_at"]=sig.detected_at.astype(str);sig["symbol"]=sig.symbol.astype(str)
    sig=sig[sig.liquidity_rank<=a.cap].copy()
    sig["scale_order"]=sig.scale.map({"small":0,"large":1}).fillna(0)
    sig=sig.sort_values(["signal_date","symbol","scale_order","detected_at"],ascending=[True,True,False,False]).drop_duplicates(["signal_date","symbol"],keep="first")

    # Cross-year bars so delayed entries and January signal history are valid.
    parts=[]
    for bp in sorted(p.glob("**/bars_*.csv.gz")):
        z=pd.read_csv(bp)
        z["date"]=z.date.astype(str);z["ticker"]=z.ticker.astype(str)
        parts.append(z)
    bars=pd.concat(parts,ignore_index=True).sort_values(["ticker","date"]).drop_duplicates(["ticker","date"],keep="last")
    spy=bars[bars.ticker=="SPY"].sort_values("date")
    calendar=spy.date.tolist(); idx={d:i for i,d in enumerate(calendar)}
    nxt={calendar[i]:calendar[i+1] for i in range(len(calendar)-1)}

    symbols=set(sig.symbol)
    sb=bars[bars.ticker.isin(symbols)].copy()
    bm={s:{r["date"]:r for r in g.to_dict("records")} for s,g in sb.groupby("ticker")}

    candidate_map={v:[] for v in VARIANTS}
    baseline_count=0
    for q in sig.to_dict("records"):
        sym=q["symbol"]; smap=bm.get(sym)
        if smap is None:continue
        d0=q["signal_date"]; d1=nxt.get(d0)
        if d1 is None:continue
        b0=smap.get(d0); b1=smap.get(d1)
        if b0 is None or b1 is None:continue
        lower=float(q["lower"]);upper=float(q["upper"]);width=max(upper-lower,1e-12)
        op1=float(b1["open"])
        if not(lower<op1<upper):continue
        age=max(0,idx[d0]-idx.get(q["detected_at"],idx[d0]))
        base={**q,"lower":lower,"upper":upper,"box_width_pct":width/op1,
              "box_age_sessions":age,"baseline_next_open":op1}

        candidate_map["baseline_next_open"].append({**base,"variant":"baseline_next_open","entry_date":d1,"entry_price":op1,
                                                     "entry_vs_baseline_next_open":0.0})
        baseline_count+=1

        d2=nxt.get(d1)
        if d2 is None:continue
        b2=smap.get(d2)
        if b2 is None:continue
        op2=float(b2["open"])
        if not(lower<op2<upper):continue

        sig_close=float(b0["close"]);sig_low=float(b0["low"])
        c_open=float(b1["open"]);c_low=float(b1["low"]);c_close=float(b1["close"])
        rules={
          "hold_then_enter": (c_low>lower and c_close>sig_close),
          "no_new_low_green": (c_low>=sig_low and c_close>c_open),
          "lower_touch_reclaim": (c_low<=lower+.12*width and c_close>=lower+.20*width),
          "failed_break_reclaim": (c_low<=lower and c_close>lower and c_close>c_open),
        }
        for variant,ok in rules.items():
            if not ok:continue
            candidate_map[variant].append({**base,"variant":variant,"confirmation_date":d1,
                                           "entry_date":d2,"entry_price":op2,
                                           "entry_vs_baseline_next_open":op2/op1-1})

    start=f"{a.year}-01-01";end=f"{a.year}-12-31"
    rows=[]
    for sleeve in ("all","fresh","wide_fresh"):
        def sleeve_ok(c):
            if sleeve=="all":return True
            t=th[c["scale"]]
            fresh=c["box_age_sessions"]<=t["am"]
            return fresh if sleeve=="fresh" else fresh and c["box_width_pct"]>=t["wm"]
        base_n=sum(1 for c in candidate_map["baseline_next_open"] if sleeve_ok(c) and start<=c["entry_date"]<=end)
        for variant in VARIANTS:
            filt=[c for c in candidate_map[variant] if sleeve_ok(c)]
            r=run(filt,calendar,bm,start,end)
            eligible=[c for c in filt if start<=c["entry_date"]<=end]
            sl=[c["entry_vs_baseline_next_open"] for c in eligible if c.get("entry_vs_baseline_next_open") is not None]
            rows.append({
              "year":a.year,"rank_cap":a.cap,"sleeve":sleeve,"variant":variant,
              "baseline_candidate_count":base_n,
              "confirmed_candidate_count":len(eligible),
              "confirmation_rate":len(eligible)/base_n if base_n else None,
              "avg_entry_vs_baseline_next_open":statistics.mean(sl) if sl else None,
              **r
            })

    df=pd.DataFrame(rows)
    df.to_csv(out/f"entry_confirmation_{a.cap}_{a.year}.csv",index=False)
    receipt={"schema":"PURE-BOX-ENTRY-CONFIRMATION-YEAR-V1","year":a.year,"rank_cap":a.cap,
             "thresholds":th,"raw_signals":int(len(sig)),"baseline_candidates":baseline_count}
    (out/f"summary_{a.cap}_{a.year}.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
    print(df.to_string(index=False))

if __name__=="__main__":
    main()
