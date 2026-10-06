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
ADV_FLOOR=25_000_000.0
YEARS=(2021,2022,2023,2024,2025,2026)
GATES=["all","breadth_ma50","breadth_ret20","breadth_ma200","breadth_dual","breadth_any",
       "avoid_internal_breakdown","avoid_broad_weakness","low_new_lows","composite_3of4"]

def pf(rs):
    w=sum(x for x in rs if x>0); l=-sum(x for x in rs if x<0)
    return w/l if l>0 else None
def mdd(vals):
    p=vals[0];d=0
    for x in vals:p=max(p,x);d=min(d,x/p-1)
    return d
def sharpe(eq):
    r=[eq[i][1]/eq[i-1][1]-1 for i in range(1,len(eq)) if eq[i-1][1]>0]
    if len(r)<2:return None
    s=statistics.stdev(r)
    return None if s==0 else statistics.mean(r)/s*math.sqrt(252)

def load(indir):
    p=Path(indir)
    bars=pd.concat([pd.read_csv(x) for x in sorted(p.glob("**/bars_*.csv.gz"))],ignore_index=True)
    bars["date"]=bars.date.astype(str);bars["ticker"]=bars.ticker.astype(str)
    bars=bars.sort_values(["ticker","date"]).drop_duplicates(["ticker","date"],keep="last")
    sig=pd.concat([pd.read_csv(x) for x in sorted(p.glob("**/signals_*.csv"))],ignore_index=True)
    sig["signal_date"]=sig.signal_date.astype(str);sig["symbol"]=sig.symbol.astype(str)
    spy=bars[bars.ticker=="SPY"].sort_values("date")
    cal=spy.date.tolist();idx={d:i for i,d in enumerate(cal)}
    nxt={cal[i]:cal[i+1] for i in range(len(cal)-1)}
    bm={s:{r["date"]:r for r in g.to_dict("records")} for s,g in bars.groupby("ticker")}
    return bars,sig,cal,idx,nxt,bm

def build_breadth(bars,cap):
    x=bars[bars.ticker!="SPY"].copy()
    x["dollar_volume"]=x.close*x.volume
    x=x.sort_values(["ticker","date"])
    gp=x.groupby("ticker",group_keys=False)
    x["adv20_prior"]=gp.dollar_volume.transform(lambda s:s.shift(1).rolling(20,min_periods=20).mean())
    x["ma50"]=gp.close.transform(lambda s:s.rolling(50,min_periods=50).mean())
    x["ma200"]=gp.close.transform(lambda s:s.rolling(200,min_periods=200).mean())
    x["ret1"]=gp.close.pct_change(1)
    x["ret20"]=gp.close.pct_change(20)
    x["ret63"]=gp.close.pct_change(63)
    x["prior20_low"]=gp.close.transform(lambda s:s.shift(1).rolling(20,min_periods=20).min())
    x["prior63_low"]=gp.close.transform(lambda s:s.shift(1).rolling(63,min_periods=63).min())
    valid=(x.close>=5)&x.adv20_prior.notna()&(x.adv20_prior>=ADV_FLOOR)
    z=x.loc[valid].copy()
    z=z.sort_values(["date","adv20_prior","ticker"],ascending=[True,False,True])
    z["liq_rank"]=z.groupby("date").cumcount()+1
    z=z[z.liq_rank<=cap].copy()
    rows=[]
    for d,g in z.groupby("date",sort=True):
        rows.append({
            "date":d,
            "n":len(g),
            "pct_above_ma50":float((g.close>=g.ma50).mean()),
            "pct_above_ma200":float((g.close>=g.ma200).mean()),
            "pct_ret20_positive":float((g.ret20>0).mean()),
            "pct_ret63_positive":float((g.ret63>0).mean()),
            "pct_up_1d":float((g.ret1>0).mean()),
            "median_ret20":float(g.ret20.median()),
            "median_ret63":float(g.ret63.median()),
            "pct_new_20d_low":float((g.close<=g.prior20_low).mean()),
            "pct_new_63d_low":float((g.close<=g.prior63_low).mean()),
            "ret20_dispersion":float(g.ret20.std())
        })
    return pd.DataFrame(rows)

def gate_ok(b,name):
    if b is None:return False
    if name=="all":return True
    if name=="breadth_ma50":return b["pct_above_ma50"]>=.50
    if name=="breadth_ret20":return b["pct_ret20_positive"]>=.50
    if name=="breadth_ma200":return b["pct_above_ma200"]>=.50
    if name=="breadth_dual":return b["pct_above_ma50"]>=.50 and b["pct_ret20_positive"]>=.50
    if name=="breadth_any":return b["pct_above_ma50"]>=.50 or b["pct_ret20_positive"]>=.50
    if name=="avoid_internal_breakdown":
        return not (b["pct_above_ma50"]<.35 and b["pct_ret20_positive"]<.35)
    if name=="avoid_broad_weakness":
        return not (b["pct_above_ma200"]<.40 and b["pct_ret63_positive"]<.40)
    if name=="low_new_lows":return b["pct_new_20d_low"]<.20
    if name=="composite_3of4":
        score=sum([
            b["pct_above_ma50"]>=.50,b["pct_above_ma200"]>=.50,
            b["pct_ret20_positive"]>=.50,b["pct_ret63_positive"]>=.50])
        return score>=3
    raise ValueError(name)

def build_candidates(sig,cap,nxt,bm,idx,breadth_map):
    s=sig[sig.liquidity_rank<=cap].copy()
    s["ord"]=s.scale.map({"small":0,"large":1}).fillna(0)
    s=s.sort_values(["signal_date","symbol","ord","detected_at"],ascending=[True,True,False,False]).drop_duplicates(["signal_date","symbol"],keep="first")
    out=[]
    for q in s.to_dict("records"):
        ed=nxt.get(q["signal_date"]);b=bm.get(q["symbol"],{}).get(ed) if ed else None
        if b is None:continue
        op=float(b["open"]);lo=float(q["lower"]);hi=float(q["upper"])
        if not(lo<op<hi):continue
        out.append({**q,"entry_date":ed,"entry_price":op,"lower":lo,"upper":hi,
                    "box_width_pct":(hi-lo)/op,
                    "box_age_sessions":max(0,idx[q["signal_date"]]-idx.get(str(q["detected_at"]),idx[q["signal_date"]])),
                    "_breadth":breadth_map.get(q["signal_date"])})
    return out

def thresholds(train):
    th={}
    for s in ("small","large"):
        g=train[train.scale==s]
        th[s]={"wm":float(g.box_width_pct.median()),"am":float(g.box_age_sessions.median())}
    return th
def box_ok(c,th,sleeve):
    if sleeve=="fresh":return c["box_age_sessions"]<=th[c["scale"]]["am"]
    return c["box_age_sessions"]<=th[c["scale"]]["am"] and c["box_width_pct"]>=th[c["scale"]]["wm"]

def run(cands,cal,bm,start,end):
    by=defaultdict(list)
    for c in cands:
        if start<=c["entry_date"]<=end:by[c["entry_date"]].append(c)
    days=[d for d in cal if start<=d<=end]
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
            z=p["shares"]*px;val+=z;inv+=z
        eq.append((d,val));ex.append(inv/val if val>0 else 0)
    vals=[v for _,v in eq];rs=[t["net_return"] for t in tr]
    yrs=max((date.fromisoformat(eq[-1][0])-date.fromisoformat(eq[0][0])).days/365.2425,1/365)
    return {"total_return":vals[-1]/vals[0]-1,"cagr":(vals[-1]/vals[0])**(1/yrs)-1,
            "max_drawdown":mdd(vals),"sharpe":sharpe(eq),"avg_exposure":statistics.mean(ex),
            "trades":len(tr),"profit_factor":pf(rs),"mean_trade":statistics.mean(rs) if rs else None}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True)
    a=ap.parse_args();out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    bars,sig,cal,idx,nxt,bm=load(a.indir)
    rows=[]; breadth_receipt=[]
    summary={"schema":"PURE-BOX-BREADTH-PERMISSION-V1","lanes":{}}
    for cap in (300,500):
        breadth=build_breadth(bars,cap)
        breadth.to_csv(out/f"breadth_top{cap}.csv.gz",index=False,compression="gzip")
        bmap={r["date"]:r for r in breadth.to_dict("records")}
        cs=build_candidates(sig,cap,nxt,bm,idx,bmap)
        cdf=pd.DataFrame([{k:v for k,v in c.items() if k!="_breadth"} for c in cs])
        for y in YEARS:
            gy=breadth[breadth.date.str[:4].astype(int)==y]
            if len(gy):
                breadth_receipt.append({"rank_cap":cap,"year":y,"days":len(gy),
                    "mean_pct_above_ma50":float(gy.pct_above_ma50.mean()),
                    "mean_pct_above_ma200":float(gy.pct_above_ma200.mean()),
                    "mean_pct_ret20_positive":float(gy.pct_ret20_positive.mean()),
                    "mean_pct_ret63_positive":float(gy.pct_ret63_positive.mean()),
                    "mean_pct_new_20d_low":float(gy.pct_new_20d_low.mean()),
                    "median_cross_section_ret20":float(gy.median_ret20.median())})
            train=cdf[cdf.signal_date.str[:4].astype(int)<y]
            test=[c for c in cs if int(c["signal_date"][:4])==y]
            if train.empty or not test:continue
            th=thresholds(train)
            for sleeve in ("fresh","wide_fresh"):
                base=[c for c in test if box_ok(c,th,sleeve)]
                for gate in GATES:
                    filt=[c for c in base if gate_ok(c["_breadth"],gate)]
                    res=run(filt,cal,bm,f"{y}-01-01",f"{y}-12-31")
                    rows.append({"rank_cap":cap,"year":y,"sleeve":sleeve,"gate":gate,
                                 "eligible_candidates":len(filt),**res})
    rdf=pd.DataFrame(rows)
    rdf.to_csv(out/"annual_breadth_permission.csv",index=False)
    pd.DataFrame(breadth_receipt).to_csv(out/"breadth_year_receipt.csv",index=False)
    for cap in (300,500):
        summary["lanes"][f"top{cap}"]={}
        for sleeve in ("fresh","wide_fresh"):
            summary["lanes"][f"top{cap}"][sleeve]={}
            for gate in GATES:
                g=rdf[(rdf.rank_cap==cap)&(rdf.sleeve==sleeve)&(rdf.gate==gate)].sort_values("year")
                comp=1.;vals=[]
                for r in g.to_dict("records"):
                    comp*=1+float(r["total_return"]);vals.append(float(r["total_return"]))
                summary["lanes"][f"top{cap}"][sleeve][gate]={
                    "compounded_walk_forward_return":comp-1,
                    "positive_years":sum(v>0 for v in vals),"years":len(vals),
                    "avg_year_return":statistics.mean(vals),"avg_sharpe":float(g.sharpe.mean()),
                    "avg_exposure":float(g.avg_exposure.mean()),"total_trades":int(g.trades.sum()),
                    "yearly":{str(int(r.year)):float(r.total_return) for r in g.itertuples()}
                }
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
