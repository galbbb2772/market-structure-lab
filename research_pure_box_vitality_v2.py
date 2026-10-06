#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math, statistics
from collections import defaultdict
from datetime import date
from pathlib import Path
import numpy as np
import pandas as pd

ENTRY_COST=.0005
EXIT_COST=.0005
TARGET_WEIGHT={"small":.5,"large":1.0}
VAL_START="2023-01-01"
DISC_END="2022-12-31"

def pf(rs):
    w=sum(x for x in rs if x>0); l=-sum(x for x in rs if x<0)
    return w/l if l>0 else None

def mdd(vals):
    p=vals[0];d=0
    for x in vals:
        p=max(p,x);d=min(d,x/p-1)
    return d

def sharpe(eq):
    if len(eq)<3:return None
    r=[eq[i][1]/eq[i-1][1]-1 for i in range(1,len(eq))]
    s=statistics.stdev(r)
    return None if s==0 else statistics.mean(r)/s*math.sqrt(252)

def load(indir):
    p=Path(indir)
    bars=pd.concat([pd.read_csv(x) for x in sorted(p.glob("**/bars_*.csv.gz"))],ignore_index=True)
    bars["date"]=bars.date.astype(str); bars["ticker"]=bars.ticker.astype(str)
    bars=bars.sort_values(["ticker","date"]).drop_duplicates(["ticker","date"],keep="last")
    sig=pd.concat([pd.read_csv(x) for x in sorted(p.glob("**/signals_*.csv"))],ignore_index=True)
    sig["signal_date"]=sig.signal_date.astype(str); sig["symbol"]=sig.symbol.astype(str)
    spy=bars[bars.ticker=="SPY"].sort_values("date")
    cal=spy.date.tolist(); idx={d:i for i,d in enumerate(cal)}
    nxt={cal[i]:cal[i+1] for i in range(len(cal)-1)}
    bm={s:{r["date"]:r for r in g.to_dict("records")} for s,g in bars.groupby("ticker")}
    return sig,cal,idx,nxt,bm

def build_candidates(sig,cap,nxt,bm,idx):
    s=sig[sig.liquidity_rank<=cap].copy()
    s["ord"]=s.scale.map({"small":0,"large":1}).fillna(0)
    s=s.sort_values(["signal_date","symbol","ord","detected_at"],ascending=[True,True,False,False]).drop_duplicates(["signal_date","symbol"],keep="first")
    out=[]
    for q in s.to_dict("records"):
        ed=nxt.get(q["signal_date"])
        if not ed: continue
        b=bm.get(q["symbol"],{}).get(ed)
        if b is None: continue
        op=float(b["open"]);lo=float(q["lower"]);hi=float(q["upper"])
        if not (lo<op<hi): continue
        width=(hi-lo)/op
        age=max(0,idx[q["signal_date"]]-idx.get(str(q["detected_at"]),idx[q["signal_date"]]))
        out.append({**q,"entry_date":ed,"entry_price":op,"lower":lo,"upper":hi,
                    "box_width_pct":width,"box_age_sessions":age})
    return out

def isolated_trades(cands,calendar,bm):
    by=defaultdict(list)
    for c in cands:by[c["entry_date"]].append(c)
    active={};tr=[]
    for d in calendar:
        for sym in list(active):
            b=bm.get(sym,{}).get(d)
            if b is None:continue
            p=active[sym];op=float(b["open"]);px=None;reason=None
            if op<=p["lower"]:px=op;reason="stop"
            elif op>=p["upper"]:px=op;reason="target"
            if px is not None:
                net=(px*(1-EXIT_COST))/(p["entry_price"]/(1-ENTRY_COST))-1
                tr.append({**p,"exit_date":d,"exit_reason":reason,"net_return":net,"hold_sessions":p["age"]+1})
                del active[sym]
        for c in by.get(d,[]):
            if c["symbol"] not in active:active[c["symbol"]]={**c,"age":0}
        for sym in list(active):
            b=bm.get(sym,{}).get(d)
            if b is None:continue
            p=active[sym];lo=float(b["low"]);hi=float(b["high"]);px=None;reason=None
            if lo<=p["lower"]:px=p["lower"];reason="stop"
            elif hi>=p["upper"]:px=p["upper"];reason="target"
            if px is not None:
                net=(px*(1-EXIT_COST))/(p["entry_price"]/(1-ENTRY_COST))-1
                tr.append({**p,"exit_date":d,"exit_reason":reason,"net_return":net,"hold_sessions":p["age"]+1})
                del active[sym]
            else:p["age"]+=1
    return pd.DataFrame(tr)

def qcuts(train,field):
    vals=train[field].astype(float)
    qs=[float(vals.quantile(q)) for q in (.2,.4,.6,.8)]
    # preserve nondecreasing edges even if ties
    return qs

def assign_fixed(v,cuts):
    return 1+sum(float(v)>x for x in cuts)

def cell_stats(df):
    if df.empty:return {"n":0}
    rs=df.net_return.astype(float).tolist()
    return {
        "n":len(df),"mean_return":float(df.net_return.mean()),"median_return":float(df.net_return.median()),
        "profit_factor":pf(rs),"win_rate":float((df.net_return>0).mean()),
        "target_rate":float((df.exit_reason=="target").mean()),
        "avg_hold_sessions":float(df.hold_sessions.mean())
    }

def run_portfolio(cands,calendar,bm,rule=lambda c:True,priority=None,start=None,end=None):
    by=defaultdict(list)
    for c in cands:
        if start and c["entry_date"]<start:continue
        if end and c["entry_date"]>end:continue
        if rule(c):by[c["entry_date"]].append(c)
    days=[d for d in calendar if (not start or d>=start) and (not end or d<=end)]
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
        if priority is not None:cand.sort(key=priority)
        else:cand.sort(key=lambda x:x["symbol"])
        eqo=cash
        for sym,p in pos.items():
            b=bm.get(sym,{}).get(d);eqo+=p["shares"]*(float(b["open"]) if b is not None else p["last"])
        if priority is None:
            req=sum(TARGET_WEIGHT[c["scale"]]*eqo for c in cand)
            sc=1 if req<=cash or req<=0 else cash/req
            allocs=[(c,TARGET_WEIGHT[c["scale"]]*eqo*sc) for c in cand]
        else:
            rem=cash;allocs=[]
            for c in cand:
                want=TARGET_WEIGHT[c["scale"]]*eqo;alloc=min(want,rem)
                if alloc>1e-12:allocs.append((c,alloc));rem-=alloc
                if rem<=1e-12:break
        for c,alloc in allocs:
            if alloc<=1e-12 or alloc>cash+1e-10:continue
            invest=alloc*(1-ENTRY_COST);cash-=alloc
            pos[c["symbol"]]={**c,"shares":invest/c["entry_price"],"cost_basis":alloc,"age":0,"last":c["entry_price"]}
        for sym in list(pos):
            b=bm.get(sym,{}).get(d)
            if b is None:continue
            p=pos[sym];lo=float(b["low"]);hi=float(b["high"]);cl=float(b["close"]);px=None;reason=None
            if lo<=p["lower"]:px=p["lower"];reason="stop"
            elif hi>=p["upper"]:px=p["upper"];reason="target"
            if px is not None:
                proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                tr.append({**p,"exit_reason":reason,"net_return":proceeds/p["cost_basis"]-1});del pos[sym]
            else:p["last"]=cl;p["age"]+=1
        val=cash;inv=0
        for sym,p in pos.items():
            b=bm.get(sym,{}).get(d);px=float(b["close"]) if b is not None else p["last"];p["last"]=px
            z=p["shares"]*px;val+=z;inv+=z
        eq.append((d,val));ex.append(inv/val if val>0 else 0)
    if not eq:return {"portfolio":{"total_return":None},"trades":0}
    vals=[v for _,v in eq]
    yrs=max((date.fromisoformat(eq[-1][0])-date.fromisoformat(eq[0][0])).days/365.2425,1/365)
    rs=[x["net_return"] for x in tr]
    return {"portfolio":{"total_return":vals[-1]/vals[0]-1,"cagr":(vals[-1]/vals[0])**(1/yrs)-1,
                         "max_drawdown":mdd(vals),"sharpe":sharpe(eq),"avg_exposure":statistics.mean(ex)},
            "trades":len(tr),"profit_factor":pf(rs),"mean_trade":statistics.mean(rs) if rs else None}

def pct_rank(train,field,v):
    a=np.sort(train[field].astype(float).to_numpy())
    if len(a)==0:return .5
    return float(np.searchsorted(a,float(v),side="right")/len(a))

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True)
    a=ap.parse_args();out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=load(a.indir)
    summary={"schema":"PURE-BOX-VITALITY-V2","rank_caps":{}}
    grids=[]
    walk=[]
    for cap in (300,500):
        cs=build_candidates(sig,cap,nxt,bm,idx)
        iso=isolated_trades(cs,cal,bm)
        disc=iso[iso.signal_date<=DISC_END].copy(); val=iso[iso.signal_date>=VAL_START].copy()

        # 5x5 grid from discovery-frozen cuts, separately by scale
        for scale in ("small","large"):
            tr=disc[disc.scale==scale]; va=val[val.scale==scale].copy()
            wc=qcuts(tr,"box_width_pct"); ac=qcuts(tr,"box_age_sessions")
            va["width_q"]=va.box_width_pct.map(lambda v:assign_fixed(v,wc))
            va["age_q"]=va.box_age_sessions.map(lambda v:assign_fixed(v,ac))
            for wq in range(1,6):
                for aq in range(1,6):
                    g=va[(va.width_q==wq)&(va.age_q==aq)]
                    grids.append({"rank_cap":cap,"scale":scale,"width_q":wq,"age_q":aq,**cell_stats(g)})

        # discovery percentile vitality ranking mapped to validation
        train_by_scale={s:disc[disc.scale==s].copy() for s in ("small","large")}
        valc=[c for c in cs if c["signal_date"]>=VAL_START]
        for c in valc:
            tr=train_by_scale[c["scale"]]
            ws=pct_rank(tr,"box_width_pct",c["box_width_pct"])
            fs=1-pct_rank(tr,"box_age_sessions",c["box_age_sessions"])
            c["vitality_score"]=.5*ws+.5*fs
        base_val=run_portfolio(valc,cal,bm,start=VAL_START)
        pri_val=run_portfolio(valc,cal,bm,priority=lambda x:(-x["vitality_score"],x["symbol"]),start=VAL_START)

        # annual walk-forward thresholds formed only from prior years
        annual=[]
        years=[2021,2022,2023,2024,2025,2026]
        for y in years:
            train=pd.DataFrame([c for c in cs if int(c["signal_date"][:4])<y])
            test=[c for c in cs if int(c["signal_date"][:4])==y]
            if train.empty or not test:continue
            th={}
            for s in ("small","large"):
                g=train[train.scale==s]
                th[s]={"wm":float(g.box_width_pct.median()),"am":float(g.box_age_sessions.median()),
                       "w80":float(g.box_width_pct.quantile(.8)),"a20":float(g.box_age_sessions.quantile(.2))}
            def base(c):return True
            def wide(c):return c["box_width_pct"]>=th[c["scale"]]["wm"]
            def fresh(c):return c["box_age_sessions"]<=th[c["scale"]]["am"]
            def wf(c):return wide(c) and fresh(c)
            def strict(c):return c["box_width_pct"]>=th[c["scale"]]["w80"] and c["box_age_sessions"]<=th[c["scale"]]["a20"]
            start=f"{y}-01-01";end=f"{y}-12-31"
            lanes={n:run_portfolio(test,cal,bm,rule=f,start=start,end=end) for n,f in
                   [("baseline",base),("wide",wide),("fresh",fresh),("wide_fresh",wf),("strict",strict)]}
            annual.append({"year":y,"thresholds":th,"lanes":lanes})
            for n,r in lanes.items():
                walk.append({"rank_cap":cap,"year":y,"lane":n,**r["portfolio"],"trades":r["trades"],
                             "profit_factor":r.get("profit_factor"),"mean_trade":r.get("mean_trade")})

        summary["rank_caps"][f"top{cap}"]={
            "validation_baseline":base_val,
            "validation_vitality_priority":pri_val,
            "annual_walk_forward":annual,
        }

    pd.DataFrame(grids).to_csv(out/"validation_width_age_grid.csv",index=False)
    pd.DataFrame(walk).to_csv(out/"annual_walk_forward.csv",index=False)
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps({
        cap:{
            "base":v["validation_baseline"],
            "priority":v["validation_vitality_priority"]
        } for cap,v in summary["rank_caps"].items()
    },indent=2))
if __name__=="__main__":main()
