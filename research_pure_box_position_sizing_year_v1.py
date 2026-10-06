#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math, statistics
from collections import defaultdict
from pathlib import Path
import pandas as pd

ENTRY_COST=.0005
EXIT_COST=.0005
TARGET_WEIGHT={"small":.5,"large":1.0}
METHODS=("baseline_pro_rata","width_age_borda","confirmation_borda","composite_borda")
ENTRY_VARIANTS=("hold_then_enter","no_new_low_green")

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

def rank_points(vals, higher=True):
    s=pd.Series(vals,dtype=float)
    if not higher:s=-s
    return s.rank(method="average",ascending=True).tolist()

def quality_scores(cand,method):
    n=len(cand)
    if method=="baseline_pro_rata":return [1.0]*n
    rw=rank_points([c["box_width_pct"] for c in cand],True)
    ra=rank_points([c["box_age_sessions"] for c in cand],False)
    rc=rank_points([c["confirmation_strength"] for c in cand],True)
    if method=="width_age_borda":return [rw[i]+ra[i] for i in range(n)]
    if method=="confirmation_borda":return rc
    if method=="composite_borda":return [rw[i]+ra[i]+rc[i] for i in range(n)]
    raise ValueError(method)

def waterfill(req,scores,budget):
    n=len(req);alloc=[0.0]*n
    if n==0 or budget<=0:return alloc
    active=set(range(n));remaining=budget
    for _ in range(n+2):
        if remaining<=1e-12 or not active:break
        sw=sum(max(scores[i],1e-12) for i in active)
        tentative={i:remaining*max(scores[i],1e-12)/sw for i in active}
        capped=[]
        for i in list(active):
            room=req[i]-alloc[i]
            if tentative[i]>=room-1e-12:
                alloc[i]+=max(room,0.0);remaining-=max(room,0.0);capped.append(i)
        if capped:
            for i in capped:active.discard(i)
            continue
        for i in active:alloc[i]+=tentative[i]
        remaining=0.0
        break
    return alloc

def run(cands,calendar,bm,start,end,method):
    by=defaultdict(list)
    for c in cands:
        if start<=c["entry_date"]<=end:by[c["entry_date"]].append(c)
    days=[d for d in calendar if start<=d<=end]
    cash=1.;pos={};tr=[];eq=[];ex=[]
    hh=[];mx=[];entry_days=0;constrained=0
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

        if cand:
            req=[TARGET_WEIGHT[c["scale"]]*eqo for c in cand]
            budget=min(cash,sum(req))
            scores=quality_scores(cand,method)
            if method=="baseline_pro_rata":
                scale=0 if sum(req)<=0 else budget/sum(req)
                alloc=[r*scale for r in req]
            else:
                alloc=waterfill(req,scores,budget)
            if budget>1e-12:
                shares=[a/budget for a in alloc if a>1e-12]
                hh.append(sum(s*s for s in shares));mx.append(max(shares) if shares else 0.0)
                entry_days+=1
                if sum(req)>cash+1e-12:constrained+=1

            for c,a in zip(cand,alloc):
                if a<=1e-12 or a>cash+1e-10:continue
                invest=a*(1-ENTRY_COST);cash-=a
                pos[c["symbol"]]={**c,"shares":invest/c["entry_price"],"cost_basis":a,"last":c["entry_price"]}

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
      "mean_trade":statistics.mean(rs) if rs else None,
      "avg_entry_hhi":statistics.mean(hh) if hh else None,
      "avg_largest_entry_share":statistics.mean(mx) if mx else None,
      "entry_days":entry_days,
      "cash_constrained_days":constrained,
      "cash_constrained_fraction":constrained/entry_days if entry_days else None
    }

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

    sigp=next(p.glob(f"**/signals_{a.year}.csv"))
    sig=pd.read_csv(sigp)
    sig["signal_date"]=sig.signal_date.astype(str);sig["detected_at"]=sig.detected_at.astype(str);sig["symbol"]=sig.symbol.astype(str)
    sig=sig[sig.liquidity_rank<=a.cap].copy()
    sig["scale_order"]=sig.scale.map({"small":0,"large":1}).fillna(0)
    sig=sig.sort_values(["signal_date","symbol","scale_order","detected_at"],ascending=[True,True,False,False]).drop_duplicates(["signal_date","symbol"],keep="first")

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
        if b0 is None or b1 is None or b2 is None:continue
        lo=float(q["lower"]);hi=float(q["upper"]);width=max(hi-lo,1e-12)
        op1=float(b1["open"]);op2=float(b2["open"])
        if not(lo<op1<hi and lo<op2<hi):continue
        age=max(0,idx[d0]-idx.get(q["detected_at"],idx[d0]))
        sig_close=float(b0["close"]);sig_low=float(b0["low"])
        c_open=float(b1["open"]);c_low=float(b1["low"]);c_close=float(b1["close"])
        common={**q,"lower":lo,"upper":hi,"box_age_sessions":age,"box_width_pct":width/op1,
                "entry_date":d2,"entry_price":op2,"confirmation_date":d1}
        if c_low>lo and c_close>sig_close:
            strength=(c_close-sig_close)/width
            cmap["hold_then_enter"].append({**common,"confirmation_strength":strength,"entry_variant":"hold_then_enter"})
        if c_low>=sig_low and c_close>c_open:
            strength=(c_close-c_open)/width
            cmap["no_new_low_green"].append({**common,"confirmation_strength":strength,"entry_variant":"no_new_low_green"})

    start=f"{a.year}-01-01";end=f"{a.year}-12-31"
    rows=[]
    for sleeve in ("fresh","wide_fresh"):
        def sleeve_ok(c):
            t=th[c["scale"]];fresh=c["box_age_sessions"]<=t["am"]
            return fresh if sleeve=="fresh" else fresh and c["box_width_pct"]>=t["wm"]
        for ev in ENTRY_VARIANTS:
            raw=[c for c in cmap[ev] if sleeve_ok(c)]
            for method in METHODS:
                r=run(raw,calendar,bm,start,end,method)
                rows.append({"year":a.year,"rank_cap":a.cap,"sleeve":sleeve,
                             "entry_variant":ev,"sizing_method":method,**r})

    df=pd.DataFrame(rows)
    df.to_csv(out/f"position_sizing_{a.cap}_{a.year}.csv",index=False)
    print(df.to_string(index=False))

if __name__=="__main__":main()
