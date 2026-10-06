#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math, statistics
from collections import defaultdict
from datetime import date
from pathlib import Path
import pandas as pd
import numpy as np

ENTRY_COST=.0005
EXIT_COST=.0005
TARGET_WEIGHT={"small":.5,"large":1.0}
YEARS=(2021,2022,2023,2024,2025,2026)

def pf(rs):
    w=sum(x for x in rs if x>0); l=-sum(x for x in rs if x<0)
    return w/l if l>0 else None

def mdd(vals):
    p=vals[0]; d=0
    for x in vals:
        p=max(p,x); d=min(d,x/p-1)
    return d

def sharpe(eq):
    if len(eq)<3:return None
    r=[eq[i][1]/eq[i-1][1]-1 for i in range(1,len(eq)) if eq[i-1][1]>0]
    if len(r)<2:return None
    s=statistics.stdev(r)
    return None if s==0 else statistics.mean(r)/s*math.sqrt(252)

def load(indir):
    p=Path(indir)
    bars=pd.concat([pd.read_csv(x) for x in sorted(p.glob("**/bars_*.csv.gz"))],ignore_index=True)
    bars["date"]=bars.date.astype(str); bars["ticker"]=bars.ticker.astype(str)
    bars=bars.sort_values(["ticker","date"]).drop_duplicates(["ticker","date"],keep="last")
    sig=pd.concat([pd.read_csv(x) for x in sorted(p.glob("**/signals_*.csv"))],ignore_index=True)
    sig["signal_date"]=sig.signal_date.astype(str); sig["symbol"]=sig.symbol.astype(str)
    spy=bars[bars.ticker=="SPY"].sort_values("date").copy()
    spy["ret1"]=spy.close.pct_change()
    spy["ma50"]=spy.close.rolling(50,min_periods=50).mean()
    spy["ma200"]=spy.close.rolling(200,min_periods=200).mean()
    spy["ret20"]=spy.close.pct_change(20)
    spy["ret63"]=spy.close.pct_change(63)
    spy["roll63_high"]=spy.close.rolling(63,min_periods=20).max()
    spy["dd63"]=spy.close/spy.roll63_high-1
    spy["rv20"]=spy.ret1.rolling(20,min_periods=20).std()*math.sqrt(252)
    spy["rv20_prior252_median"]=spy.rv20.shift(1).rolling(252,min_periods=126).median()
    spy["above_ma50"]=spy.close>=spy.ma50
    spy["above_ma200"]=spy.close>=spy.ma200
    state={r["date"]:r for r in spy.to_dict("records")}
    cal=spy.date.tolist(); idx={d:i for i,d in enumerate(cal)}
    nxt={cal[i]:cal[i+1] for i in range(len(cal)-1)}
    bm={s:{r["date"]:r for r in g.to_dict("records")} for s,g in bars.groupby("ticker")}
    return sig,cal,idx,nxt,bm,state

def build_candidates(sig,cap,nxt,bm,idx,state):
    s=sig[sig.liquidity_rank<=cap].copy()
    s["ord"]=s.scale.map({"small":0,"large":1}).fillna(0)
    s=s.sort_values(["signal_date","symbol","ord","detected_at"],ascending=[True,True,False,False]).drop_duplicates(["signal_date","symbol"],keep="first")
    out=[]
    for q in s.to_dict("records"):
        ed=nxt.get(q["signal_date"])
        if not ed:continue
        b=bm.get(q["symbol"],{}).get(ed)
        st=state.get(q["signal_date"])
        if b is None or st is None:continue
        op=float(b["open"]);lo=float(q["lower"]);hi=float(q["upper"])
        if not (lo<op<hi):continue
        out.append({**q,"entry_date":ed,"entry_price":op,"lower":lo,"upper":hi,
                    "box_width_pct":(hi-lo)/op,
                    "box_age_sessions":max(0,idx[q["signal_date"]]-idx.get(str(q["detected_at"]),idx[q["signal_date"]])),
                    "spy_above_ma50":bool(st["above_ma50"]) if pd.notna(st["ma50"]) else False,
                    "spy_above_ma200":bool(st["above_ma200"]) if pd.notna(st["ma200"]) else False,
                    "spy_ret20":float(st["ret20"]) if pd.notna(st["ret20"]) else np.nan,
                    "spy_ret63":float(st["ret63"]) if pd.notna(st["ret63"]) else np.nan,
                    "spy_dd63":float(st["dd63"]) if pd.notna(st["dd63"]) else np.nan,
                    "spy_rv20":float(st["rv20"]) if pd.notna(st["rv20"]) else np.nan,
                    "spy_rv20_prior252_median":float(st["rv20_prior252_median"]) if pd.notna(st["rv20_prior252_median"]) else np.nan})
    return out

def box_thresholds(train_df):
    th={}
    for s in ("small","large"):
        g=train_df[train_df.scale==s]
        th[s]={
            "wm":float(g.box_width_pct.median()),
            "am":float(g.box_age_sessions.median())
        }
    return th

def box_rule(c,th,sleeve):
    if sleeve=="fresh":
        return c["box_age_sessions"]<=th[c["scale"]]["am"]
    if sleeve=="wide_fresh":
        return c["box_width_pct"]>=th[c["scale"]]["wm"] and c["box_age_sessions"]<=th[c["scale"]]["am"]
    raise ValueError(sleeve)

def market_gate(c,name):
    if name=="all":return True
    if name=="above_ma200":return bool(c["spy_above_ma200"])
    if name=="ret20_positive":return np.isfinite(c["spy_ret20"]) and c["spy_ret20"]>0
    if name=="ret63_positive":return np.isfinite(c["spy_ret63"]) and c["spy_ret63"]>0
    if name=="trend_confirmed":
        return bool(c["spy_above_ma200"]) and np.isfinite(c["spy_ret63"]) and c["spy_ret63"]>0
    if name=="avoid_confirmed_downtrend":
        return not ((not bool(c["spy_above_ma200"])) and np.isfinite(c["spy_ret63"]) and c["spy_ret63"]<0)
    if name=="avoid_dual_negative":
        return not (np.isfinite(c["spy_ret20"]) and np.isfinite(c["spy_ret63"]) and c["spy_ret20"]<0 and c["spy_ret63"]<0)
    if name=="shallow_drawdown":
        return np.isfinite(c["spy_dd63"]) and c["spy_dd63"]>-0.05
    if name=="calm_or_trend":
        calm=np.isfinite(c["spy_rv20"]) and np.isfinite(c["spy_rv20_prior252_median"]) and c["spy_rv20"]<=c["spy_rv20_prior252_median"]
        return bool(c["spy_above_ma200"]) or calm
    raise ValueError(name)

GATES=["all","above_ma200","ret20_positive","ret63_positive","trend_confirmed",
       "avoid_confirmed_downtrend","avoid_dual_negative","shallow_drawdown","calm_or_trend"]

def run_portfolio(cands,calendar,bm,start,end):
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
        cand.sort(key=lambda x:x["symbol"])
        eqo=cash
        for sym,p in pos.items():
            b=bm.get(sym,{}).get(d)
            eqo+=p["shares"]*(float(b["open"]) if b is not None else p["last"])
        req=sum(TARGET_WEIGHT[c["scale"]]*eqo for c in cand)
        sc=1 if req<=cash or req<=0 else cash/req
        for c in cand:
            alloc=TARGET_WEIGHT[c["scale"]]*eqo*sc
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
        val=cash;inv=0.
        for sym,p in pos.items():
            b=bm.get(sym,{}).get(d);px=float(b["close"]) if b is not None else p["last"];p["last"]=px
            z=p["shares"]*px;val+=z;inv+=z
        eq.append((d,val));ex.append(inv/val if val>0 else 0)
    if not eq:return {"total_return":None,"trades":0}
    vals=[x for _,x in eq]
    rs=[t["net_return"] for t in tr]
    yrs=max((date.fromisoformat(eq[-1][0])-date.fromisoformat(eq[0][0])).days/365.2425,1/365)
    return {"total_return":vals[-1]/vals[0]-1,"cagr":(vals[-1]/vals[0])**(1/yrs)-1,
            "max_drawdown":mdd(vals),"sharpe":sharpe(eq),"avg_exposure":statistics.mean(ex),
            "trades":len(tr),"profit_factor":pf(rs),"mean_trade":statistics.mean(rs) if rs else None}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True)
    a=ap.parse_args();out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm,state=load(a.indir)
    rows=[]; states=[]
    for cap in (300,500):
        cs=build_candidates(sig,cap,nxt,bm,idx,state)
        cdf=pd.DataFrame(cs)
        for y in YEARS:
            train=cdf[cdf.signal_date.str[:4].astype(int)<y].copy()
            test=[c for c in cs if int(c["signal_date"][:4])==y]
            if train.empty or not test:continue
            th=box_thresholds(train)
            # market-state descriptive receipt on all test signals
            sdf=pd.DataFrame(test)
            states.append({
                "rank_cap":cap,"year":y,"signals":len(sdf),
                "pct_above_ma200":float(sdf.spy_above_ma200.mean()),
                "pct_ret20_positive":float((sdf.spy_ret20>0).mean()),
                "pct_ret63_positive":float((sdf.spy_ret63>0).mean()),
                "median_dd63":float(sdf.spy_dd63.median()),
                "median_rv20":float(sdf.spy_rv20.median())
            })
            for sleeve in ("fresh","wide_fresh"):
                base=[c for c in test if box_rule(c,th,sleeve)]
                for gate in GATES:
                    filt=[c for c in base if market_gate(c,gate)]
                    res=run_portfolio(filt,cal,bm,f"{y}-01-01",f"{y}-12-31")
                    rows.append({"rank_cap":cap,"year":y,"sleeve":sleeve,"gate":gate,
                                 "eligible_candidates":len(filt),**res})
    rdf=pd.DataFrame(rows)
    rdf.to_csv(out/"annual_market_permission.csv",index=False)
    pd.DataFrame(states).to_csv(out/"market_state_receipt.csv",index=False)

    summary={"schema":"PURE-BOX-MARKET-PERMISSION-V1","lanes":{}}
    for cap in (300,500):
        summary["lanes"][f"top{cap}"]={}
        for sleeve in ("fresh","wide_fresh"):
            summary["lanes"][f"top{cap}"][sleeve]={}
            for gate in GATES:
                g=rdf[(rdf.rank_cap==cap)&(rdf.sleeve==sleeve)&(rdf.gate==gate)].sort_values("year")
                comp=1.0
                vals=[]
                for r in g.to_dict("records"):
                    if pd.notna(r["total_return"]):
                        comp*=1+float(r["total_return"]);vals.append(float(r["total_return"]))
                summary["lanes"][f"top{cap}"][sleeve][gate]={
                    "compounded_walk_forward_return":comp-1,
                    "positive_years":sum(x>0 for x in vals),
                    "years":len(vals),
                    "avg_year_return":statistics.mean(vals) if vals else None,
                    "avg_sharpe":float(g.sharpe.mean()),
                    "avg_exposure":float(g.avg_exposure.mean()),
                    "total_trades":int(g.trades.sum()),
                    "yearly":{str(int(r.year)):float(r.total_return) for r in g.itertuples()}
                }
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
