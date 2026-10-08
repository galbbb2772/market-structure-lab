#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,statistics
from collections import defaultdict
from pathlib import Path
import pandas as pd
import research_pure_box_core_geometry_simplicity_v13 as v13
import research_pure_box_capital_architecture_v22 as v22

ENTRY_COST=v13.ENTRY_COST; EXIT_COST=v13.EXIT_COST
CAP=.50; RB=.0125; MAX_HOLD=15

def run(cands,calendar,bm,delay):
    cidx={d:i for i,d in enumerate(calendar)}
    by=defaultdict(list)
    for c in cands:
        sd=str(c["direct_entry_date"])
        if sd not in cidx:continue
        j=cidx[sd]+delay
        if j>=len(calendar):continue
        ed=calendar[j]
        if v13.VAL_START<=ed<=v13.VAL_END:
            z=dict(c);z["_exec_date"]=ed;by[ed].append(z)
    days=[d for d in calendar if v13.VAL_START<=d<=v13.VAL_END]
    cash=1.;pos={};entries=[];trades=[]
    for d in days:
        for s in list(pos):
            b=bm.get(s,{}).get(d)
            if b is None:continue
            p=pos[s]
            if p["entry_date"]!=d:p["hold_sessions"]+=1
            o=float(b["open"]);px=None;reason=None
            if o<=p["lower"]:px=o;reason="stop_gap"
            elif o>=p["target"]:px=o;reason="target_gap"
            if px is not None:
                proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                trades.append({**p,"exit_date":d,"exit_reason":reason,"net_return":proceeds/p["cost_basis"]-1,
                               "pnl":proceeds-p["cost_basis"]});del pos[s]

        eqo=cash
        for s,p in pos.items():
            b=bm.get(s,{}).get(d)
            eqo+=p["shares"]*(float(b["open"]) if b is not None else p["last"])

        raw=[];seen=set()
        for c in sorted(by.get(d,[]),key=lambda x:(int(x["liquidity_rank"]),str(x["symbol"]))):
            s=str(c["symbol"])
            if s in seen or s in pos:continue
            seen.add(s)
            b=bm.get(s,{}).get(d)
            if b is None:continue
            op=float(b["open"]);lo=float(c["lower"]);hi=float(c["upper"]);target=lo+.60*(hi-lo)
            if not(lo<op<target):continue
            ef=(op-lo)/(hi-lo)
            if ef>.20:continue
            riskpd=1-(lo*(1-EXIT_COST))/(op*(1+ENTRY_COST))
            if riskpd<=0:continue
            rq=min(RB*eqo/riskpd,CAP*eqo)
            raw.append({**c,"symbol":s,"entry_date":d,"entry_price":op,"lower":lo,"upper":hi,"target":target,
                        "entry_fraction":ef,"risk_per_dollar":riskpd,"rr_to_target":(target-op)/(op-lo),
                        "request":rq})
        raw=sorted(raw,key=lambda x:(int(x["liquidity_rank"]),x["entry_fraction"],x["symbol"]))
        rem=cash
        for x in raw:
            if rem<=1e-12:continue
            amt=min(x["request"],rem)
            if amt<=1e-12:continue
            rem-=amt;cash-=amt
            invest=amt*(1-ENTRY_COST)
            rec={**x,"shares":invest/x["entry_price"],"cost_basis":amt,"hold_sessions":1,"last":x["entry_price"],
                 "entry_weight":amt/eqo if eqo else None}
            pos[x["symbol"]]=rec
            entries.append({k:rec[k] for k in ["symbol","signal_date","entry_date","entry_price","entry_fraction",
                                               "risk_per_dollar","rr_to_target","liquidity_rank","scale","entry_weight"]})

        for s in list(pos):
            p=pos[s];b=bm.get(s,{}).get(d)
            if b is None:continue
            lo=float(b["low"]);hi=float(b["high"]);cl=float(b["close"]);px=None;reason=None
            if lo<=p["lower"]:px=p["lower"];reason="stop"
            elif hi>=p["target"]:px=p["target"];reason="target60"
            elif p["hold_sessions"]>=MAX_HOLD:px=cl;reason="time_h15"
            if px is not None:
                proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                trades.append({**p,"exit_date":d,"exit_reason":reason,"net_return":proceeds/p["cost_basis"]-1,
                               "pnl":proceeds-p["cost_basis"]});del pos[s]
            else:p["last"]=cl
    return pd.DataFrame(entries),pd.DataFrame(trades)

def stats(v):
    if len(v)==0:return None
    return {"n":int(len(v)),"mean":float(v.mean()),"median":float(v.median())}

def concentration(t):
    if t.empty:return {"top5":None,"top10":None}
    b=t.groupby("symbol").pnl.sum().abs().sort_values(ascending=False);tot=float(b.sum())
    return {"top5":float(b.head(5).sum()/tot) if tot else None,
            "top10":float(b.head(10).sum()/tot) if tot else None}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=v13.load(a.indir)
    cs=v22.bottom20(v13.strict_signals(sig,500,cal,idx,nxt,bm))
    e0,t0=run(cs,cal,bm,0);e1,t1=run(cs,cal,bm,1)
    e0.to_csv(out/"direct_entries.csv",index=False);e1.to_csv(out/"delay_entries.csv",index=False)
    t0.to_csv(out/"direct_trades.csv",index=False);t1.to_csv(out/"delay_trades.csv",index=False)
    k0={(r.symbol,str(r.signal_date)):r for r in e0.itertuples(index=False)}
    k1={(r.symbol,str(r.signal_date)):r for r in e1.itertuples(index=False)}
    same=set(k0)&set(k1);only0=set(k0)-set(k1);only1=set(k1)-set(k0)
    tm0={(str(r.symbol),str(r.signal_date)):r for r in t0.itertuples(index=False)}
    tm1={(str(r.symbol),str(r.signal_date)):r for r in t1.itertuples(index=False)}
    def rets(keys,tm):
        return pd.Series([float(tm[k].net_return) for k in keys if k in tm],dtype=float)
    byyear={}
    years=sorted(set(e0.entry_date.str[:4])|set(e1.entry_date.str[:4]))
    for y in years:
        a0=e0[e0.entry_date.str.startswith(y)];a1=e1[e1.entry_date.str.startswith(y)]
        byyear[y]={"direct_entries":int(len(a0)),"delay_entries":int(len(a1)),
                   "same_symbol_signal":int(len(set(zip(a0.symbol,a0.signal_date))&set(zip(a1.symbol,a1.signal_date))))}
    summary={
      "schema":"PURE-BOX-SIMPLE-CORE-CAPITAL-ROUTE-TIMING-ANATOMY-V32",
      "entry_counts":{"direct":len(e0),"delay":len(e1),"same":len(same),"direct_only":len(only0),"delay_only":len(only1),
                      "delay_retention_vs_direct":len(same)/len(e0) if len(e0) else None},
      "geometry":{
        "direct_entry_fraction":stats(e0.entry_fraction),"delay_entry_fraction":stats(e1.entry_fraction),
        "direct_stop_risk":stats(e0.risk_per_dollar),"delay_stop_risk":stats(e1.risk_per_dollar),
        "direct_rr":stats(e0.rr_to_target),"delay_rr":stats(e1.rr_to_target),
        "direct_liquidity_rank":stats(e0.liquidity_rank),"delay_liquidity_rank":stats(e1.liquidity_rank),
      },
      "pnl_cohorts":{
        "same_direct":stats(rets(same,tm0)),"same_delay":stats(rets(same,tm1)),
        "direct_only":stats(rets(only0,tm0)),"delay_only":stats(rets(only1,tm1))
      },
      "concentration":{"direct":concentration(t0),"delay":concentration(t1)},
      "yearly":byyear
    }
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
