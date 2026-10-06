#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math, statistics
from collections import defaultdict
from pathlib import Path
import pandas as pd

ENTRY_COST=.0005
EXIT_COST=.0005
TARGET_WEIGHT={"small":.5,"large":1.0}
ENTRY_VARIANTS=("hold_then_enter","no_new_low_green")
TRANSITION_LANES=("confirm_only","ma50_improving","ret20_improving","breadth_either_improving",
                  "breadth_both_improving","no_newlow_worsening","transition_core")

def pf(rs):
    w=sum(x for x in rs if x>0); l=-sum(x for x in rs if x<0)
    return w/l if l>0 else None
def mdd(vals):
    p=vals[0];d=0.
    for x in vals:p=max(p,x);d=min(d,x/p-1)
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
    cash=1.;pos={};tr=[];eq=[];ex=[]
    for d in days:
        for sym in list(pos):
            b=bm.get(sym,{}).get(d)
            if b is None:continue
            p=pos[sym];op=float(b["open"]);px=None;reason=None
            if op<=p["lower"]:px=op;reason="stop"
            elif op>=p["upper"]:px=op;reason="target"
            if px is not None:
                proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                tr.append({**p,"exit_reason":reason,"net_return":proceeds/p["cost_basis"]-1});del pos[sym]
        cand=[c for c in by.get(d,[]) if c["symbol"] not in pos]
        cand.sort(key=lambda x:(x["symbol"],-x["scale_order"],x["signal_date"]))
        ded=[];seen=set()
        for c in cand:
            if c["symbol"] in seen:continue
            seen.add(c["symbol"]);ded.append(c)
        cand=ded
        eqo=cash
        for sym,p in pos.items():
            b=bm.get(sym,{}).get(d);eqo+=p["shares"]*(float(b["open"]) if b is not None else p["last"])
        req=sum(TARGET_WEIGHT[c["scale"]]*eqo for c in cand)
        sc=1 if req<=cash or req<=0 else cash/req
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
                tr.append({**p,"exit_reason":reason,"net_return":proceeds/p["cost_basis"]-1});del pos[sym]
            else:p["last"]=cl
        val=cash;inv=0.
        for sym,p in pos.items():
            b=bm.get(sym,{}).get(d);px=float(b["close"]) if b is not None else p["last"];p["last"]=px
            q=p["shares"]*px;val+=q;inv+=q
        eq.append((d,val));ex.append(inv/val if val>0 else 0.)
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

def transition_ok(c,lane):
    if lane=="confirm_only":return True
    ma=c["delta_ma50"];r20=c["delta_ret20"];nl=c["delta_newlow"]
    if lane=="ma50_improving":return ma>0
    if lane=="ret20_improving":return r20>0
    if lane=="breadth_either_improving":return ma>0 or r20>0
    if lane=="breadth_both_improving":return ma>0 and r20>0
    if lane=="no_newlow_worsening":return nl<=0
    if lane=="transition_core":return (ma>0 or r20>0) and nl<=0
    raise ValueError(lane)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--year",type=int,required=True)
    ap.add_argument("--cap",type=int,choices=[300,500],required=True)
    ap.add_argument("--indir",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    p=Path(a.indir);out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

    vit=json.load(open("research/pure_box_liquid_leaders_v1/vitality_v2/summary.json"))
    annual=vit["rank_caps"][f"top{a.cap}"]["annual_walk_forward"]
    th=next(x["thresholds"] for x in annual if int(x["year"])==a.year)

    bdf=pd.read_csv(f"research/pure_box_liquid_leaders_v1/breadth_permission_v1/breadth_top{a.cap}.csv.gz")
    bdf["date"]=bdf.date.astype(str)
    breadth={r["date"]:r for r in bdf.to_dict("records")}

    sigp=next(p.glob(f"**/signals_{a.year}.csv"))
    sig=pd.read_csv(sigp)
    sig["signal_date"]=sig.signal_date.astype(str);sig["detected_at"]=sig.detected_at.astype(str);sig["symbol"]=sig.symbol.astype(str)
    sig=sig[sig.liquidity_rank<=a.cap].copy()
    sig["scale_order"]=sig.scale.map({"small":0,"large":1}).fillna(0)
    sig=sig.sort_values(["signal_date","symbol","scale_order","detected_at"],
                        ascending=[True,True,False,False]).drop_duplicates(["signal_date","symbol"],keep="first")

    parts=[]
    for bp in sorted(p.glob("**/bars_*.csv.gz")):
        z=pd.read_csv(bp);z["date"]=z.date.astype(str);z["ticker"]=z.ticker.astype(str);parts.append(z)
    bars=pd.concat(parts,ignore_index=True).sort_values(["ticker","date"]).drop_duplicates(["ticker","date"],keep="last")
    spy=bars[bars.ticker=="SPY"].sort_values("date")
    calendar=spy.date.tolist();idx={d:i for i,d in enumerate(calendar)}
    nxt={calendar[i]:calendar[i+1] for i in range(len(calendar)-1)}

    symbols=set(sig.symbol)
    sb=bars[bars.ticker.isin(symbols)]
    bm={s:{r["date"]:r for r in g.to_dict("records")} for s,g in sb.groupby("ticker")}

    cmap={v:[] for v in ENTRY_VARIANTS}
    for q in sig.to_dict("records"):
        smap=bm.get(q["symbol"]);d0=q["signal_date"]
        if smap is None:continue
        d1=nxt.get(d0);d2=nxt.get(d1) if d1 else None
        if d1 is None or d2 is None:continue
        b0=smap.get(d0);b1=smap.get(d1);b2=smap.get(d2)
        br0=breadth.get(d0);br1=breadth.get(d1)
        if b0 is None or b1 is None or b2 is None or br0 is None or br1 is None:continue
        lo=float(q["lower"]);hi=float(q["upper"]);width=max(hi-lo,1e-12)
        op2=float(b2["open"])
        if not(lo<op2<hi):continue
        age=max(0,idx[d0]-idx.get(q["detected_at"],idx[d0]))
        sig_close=float(b0["close"]);sig_low=float(b0["low"])
        c_open=float(b1["open"]);c_low=float(b1["low"]);c_close=float(b1["close"])
        common={**q,"lower":lo,"upper":hi,"box_age_sessions":age,
                "box_width_pct":width/float(b1["open"]),
                "entry_date":d2,"entry_price":op2,"confirmation_date":d1,
                "delta_ma50":float(br1["pct_above_ma50"])-float(br0["pct_above_ma50"]),
                "delta_ret20":float(br1["pct_ret20_positive"])-float(br0["pct_ret20_positive"]),
                "delta_newlow":float(br1["pct_new_20d_low"])-float(br0["pct_new_20d_low"])}
        if c_low>lo and c_close>sig_close:
            cmap["hold_then_enter"].append({**common,"entry_variant":"hold_then_enter"})
        if c_low>=sig_low and c_close>c_open:
            cmap["no_new_low_green"].append({**common,"entry_variant":"no_new_low_green"})

    start=f"{a.year}-01-01";end=f"{a.year}-12-31"
    rows=[]
    for sleeve in ("fresh","wide_fresh"):
        def sleeve_ok(c):
            t=th[c["scale"]];fresh=c["box_age_sessions"]<=t["am"]
            return fresh if sleeve=="fresh" else fresh and c["box_width_pct"]>=t["wm"]
        for ev in ENTRY_VARIANTS:
            raw=[c for c in cmap[ev] if sleeve_ok(c)]
            base_n=sum(1 for c in raw if start<=c["entry_date"]<=end)
            for lane in TRANSITION_LANES:
                filt=[c for c in raw if transition_ok(c,lane)]
                elig=[c for c in filt if start<=c["entry_date"]<=end]
                r=run(filt,calendar,bm,start,end)
                rows.append({"year":a.year,"rank_cap":a.cap,"sleeve":sleeve,"entry_variant":ev,
                             "transition_lane":lane,"confirm_candidate_count":base_n,
                             "eligible_candidates":len(elig),
                             "transition_acceptance_rate":len(elig)/base_n if base_n else None,**r})

    df=pd.DataFrame(rows)
    df.to_csv(out/f"transition_{a.cap}_{a.year}.csv",index=False)
    print(df.to_string(index=False))

if __name__=="__main__":main()
