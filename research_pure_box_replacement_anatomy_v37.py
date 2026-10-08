#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,statistics
from collections import defaultdict
from pathlib import Path
import pandas as pd
import research_pure_box_core_geometry_simplicity_v13 as v13
import research_pure_box_capital_architecture_v22 as v22

EC=v13.ENTRY_COST; XC=v13.EXIT_COST
RB=.0125; CAP=.50; H=15

def cf_hold_return(p,d,calendar,cidx,bm):
    s=p["symbol"]; lo=p["lower"]; target=p["target"]; age=int(p["hold"])
    start=cidx[d]; op0=float(bm[s][d]["open"])
    px=op0; reason="open_mark"
    for k in range(start,min(start+(H-age+1),len(calendar))):
        day=calendar[k]; b=bm.get(s,{}).get(day)
        if b is None: continue
        o=float(b["open"])
        if k>start:
            if o<=lo: px=o; reason="stop_gap"; break
            if o>=target: px=o; reason="target_gap"; break
        if float(b["low"])<=lo: px=lo; reason="stop"; break
        if float(b["high"])>=target: px=target; reason="target60"; break
        if age+(k-start)>=H:
            px=float(b["close"]); reason="time_h15"; break
        px=float(b["close"])
    return px*(1-XC)/op0-1,reason

def run(cands,calendar,bm):
    cidx={d:i for i,d in enumerate(calendar)}
    by=defaultdict(list)
    for c in cands:
        d=str(c["direct_entry_date"])
        if v13.VAL_START<=d<=v13.VAL_END and d in cidx: by[d].append(c)
    days=[d for d in calendar if v13.VAL_START<=d<=v13.VAL_END]
    cash=1.;pos={};events=[];eid=0
    for d in days:
        # age + gap exits
        for s in list(pos):
            b=bm.get(s,{}).get(d)
            if b is None: continue
            p=pos[s]; p["hold"]+=1; o=float(b["open"]); px=None
            if o<=p["lower"]: px=o
            elif o>=p["target"]: px=o
            if px is not None:
                proceeds=p["shares"]*px*(1-XC); cash+=proceeds
                r=proceeds/p["cost_basis"]-1
                for e in p.get("event_ids",[]): events[e]["incoming_realized_return"]=r
                del pos[s]

        eqo=cash
        for s,p in pos.items():
            b=bm.get(s,{}).get(d)
            eqo+=p["shares"]*(float(b["open"]) if b is not None else p["last"])

        raw=[];seen=set()
        for c in sorted(by.get(d,[]),key=lambda x:(str(x["symbol"]),str(x["signal_date"]))):
            s=str(c["symbol"])
            if s in seen or s in pos: continue
            seen.add(s)
            b=bm.get(s,{}).get(d)
            if b is None: continue
            op=float(b["open"]);lo=float(c["lower"]);hi=float(c["upper"]);target=lo+.60*(hi-lo)
            if not(lo<op<target): continue
            ef=(op-lo)/(hi-lo)
            if ef>.20: continue
            riskpd=1-(lo*(1-XC))/(op*(1+EC))
            if riskpd<=0: continue
            rq=min(RB*eqo/riskpd,CAP*eqo)
            raw.append({**c,"symbol":s,"entry_price":op,"lower":lo,"upper":hi,"target":target,
                        "entry_fraction":ef,"risk_per_dollar":riskpd,"request":rq})
        raw.sort(key=lambda x:(x["liquidity_rank"],x["entry_fraction"],x["symbol"]))

        for x in raw:
            need=x["request"]; this_event_ids=[]
            if cash+1e-12<need:
                repl=[]
                for s,p in pos.items():
                    b=bm.get(s,{}).get(d)
                    if b is None: continue
                    if int(p["liquidity_rank"])<=int(x["liquidity_rank"]): continue
                    if int(p["hold"])<10: continue
                    op=float(b["open"])
                    denom=max(p["target"]-p["entry_price"],1e-12)
                    prog=(op-p["entry_price"])/denom
                    if prog>=.25: continue
                    repl.append((int(p["liquidity_rank"]),s,op,prog))
                repl.sort(reverse=True)
                for liq,s,op,prog in repl:
                    if cash+1e-12>=need: break
                    p=pos[s]
                    full_val=p["shares"]*op*(1-XC)
                    short=need-cash
                    frac=min(1.0,short/max(full_val,1e-12))
                    shares_to_sell=p["shares"]*frac
                    proceeds=shares_to_sell*op*(1-XC)
                    basis=p["cost_basis"]*frac
                    cf_ret,cf_reason=cf_hold_return(p,d,calendar,cidx,bm)
                    displaced_ret=proceeds/basis-1 if basis>0 else 0.
                    events.append({
                      "event_id":eid,"date":d,"year":d[:4],
                      "displaced_symbol":s,"incoming_symbol":x["symbol"],
                      "displaced_age":int(p["hold"]),
                      "displaced_liquidity_rank":int(p["liquidity_rank"]),
                      "incoming_liquidity_rank":int(x["liquidity_rank"]),
                      "displaced_progress":prog,
                      "displaced_realized_return":displaced_ret,
                      "capital_released":proceeds,
                      "incoming_funded_amount":None,
                      "incoming_realized_return":None,
                      "displaced_counterfactual_return":cf_ret,
                      "displaced_counterfactual_exit_reason":cf_reason
                    })
                    this_event_ids.append(eid); eid+=1
                    cash+=proceeds
                    p["shares"]-=shares_to_sell; p["cost_basis"]-=basis
                    if p["shares"]<=1e-10 or p["cost_basis"]<=1e-10: del pos[s]

            amt=min(need,cash)
            if amt<=1e-12: continue
            invest=amt*(1-EC); cash-=amt
            pos[x["symbol"]]={**x,"shares":invest/x["entry_price"],"cost_basis":amt,
                              "hold":1,"last":x["entry_price"],"event_ids":this_event_ids}
            for e in this_event_ids: events[e]["incoming_funded_amount"]=amt

        # intraday exits
        for s in list(pos):
            p=pos[s];b=bm.get(s,{}).get(d)
            if b is None: continue
            lo=float(b["low"]);hi=float(b["high"]);cl=float(b["close"]);px=None
            if lo<=p["lower"]: px=p["lower"]
            elif hi>=p["target"]: px=p["target"]
            elif p["hold"]>=H: px=cl
            if px is not None:
                proceeds=p["shares"]*px*(1-XC); cash+=proceeds
                r=proceeds/p["cost_basis"]-1
                for e in p.get("event_ids",[]): events[e]["incoming_realized_return"]=r
                del pos[s]
            else: p["last"]=cl

    df=pd.DataFrame(events)
    if not df.empty:
        df["pair_delta"]=df["incoming_realized_return"]-df["displaced_counterfactual_return"]
    return df

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=v13.load(a.indir)
    cs=v22.bottom20(v13.strict_signals(sig,500,cal,idx,nxt,bm))
    df=run(cs,cal,bm)
    df.to_csv(out/"events.csv",index=False)
    pair=df.dropna(subset=["pair_delta"]) if not df.empty else df
    summary={
      "schema":"PURE-BOX-SIMPLE-CORE-REPLACEMENT-ANATOMY-V37",
      "event_count":int(len(df)),
      "paired_count":int(len(pair)),
      "mean_pair_delta":float(pair.pair_delta.mean()) if len(pair) else None,
      "median_pair_delta":float(pair.pair_delta.median()) if len(pair) else None,
      "positive_pair_share":float((pair.pair_delta>0).mean()) if len(pair) else None,
      "mean_displaced_realized_return":float(df.displaced_realized_return.mean()) if len(df) else None,
      "mean_displaced_counterfactual_return":float(df.displaced_counterfactual_return.mean()) if len(df) else None,
      "mean_incoming_realized_return":float(pair.incoming_realized_return.mean()) if len(pair) else None,
      "mean_age":float(df.displaced_age.mean()) if len(df) else None,
      "mean_progress":float(df.displaced_progress.mean()) if len(df) else None,
      "events_by_year":{str(k):int(v) for k,v in df.year.value_counts().sort_index().items()} if len(df) else {},
      "pair_delta_by_year":{str(y):{
          "n":int(len(g)),"mean":float(g.pair_delta.mean()),"median":float(g.pair_delta.median()),
          "positive_share":float((g.pair_delta>0).mean())
        } for y,g in pair.groupby("year")} if len(pair) else {}
    }
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2));print(df.to_string(index=False))
if __name__=="__main__":main()
