#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,statistics
from collections import defaultdict
from pathlib import Path
import pandas as pd
import research_pure_box_core_geometry_simplicity_v13 as v13
import research_pure_box_capital_architecture_v22 as v22

ENTRY_COST=v13.ENTRY_COST; EXIT_COST=v13.EXIT_COST
CAP=.50; RB=.0125

def simulate(cands,cal,bm,max_hold):
    cidx={d:i for i,d in enumerate(cal)}
    by=defaultdict(list)
    for c in cands:
        d=str(c["direct_entry_date"])
        if v13.VAL_START<=d<=v13.VAL_END: by[d].append(c)
    days=[d for d in cal if v13.VAL_START<=d<=v13.VAL_END]
    cash=1.;pos={};trades=[];entries=[];daily=[];blocked=0;scaled=0
    for d in days:
        # gap exits
        for s in list(pos):
            b=bm.get(s,{}).get(d)
            if b is None: continue
            p=pos[s]; p["hold_sessions"]+=1
            op=float(b["open"]); px=None;reason=None
            if op<=p["lower"]:px=op;reason="stop_gap"
            elif op>=p["target"]:px=op;reason="target_gap"
            if px is not None:
                proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                trades.append({**p,"exit_date":d,"exit_price":px,"exit_reason":reason,
                               "net_return":proceeds/p["cost_basis"]-1})
                del pos[s]

        eqo=cash;inv_open=0.
        for s,p in pos.items():
            b=bm.get(s,{}).get(d);v=p["shares"]*(float(b["open"]) if b is not None else p["last"])
            eqo+=v;inv_open+=v
        exp_open=inv_open/eqo if eqo>0 else 0.

        cand=[];seen=set()
        for c in sorted(by.get(d,[]),key=lambda x:(str(x["symbol"]),str(x["signal_date"]))):
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
            cand.append((c,op,lo,hi,target,riskpd))
        req=[]
        for c,op,lo,hi,target,riskpd in cand:
            req.append(min(RB*eqo/riskpd,CAP*eqo))
        sc=min(1.,cash/sum(req)) if req and sum(req)>0 else 0.
        if sc<1-1e-12: scaled+=len(cand)
        for (c,op,lo,hi,target,riskpd),rq in zip(cand,req):
            amt=rq*sc
            if amt<=1e-12:blocked+=1;continue
            invest=amt*(1-ENTRY_COST);cash-=amt;s=str(c["symbol"])
            rec={**c,"symbol":s,"entry_date":d,"entry_price":op,"entry_weight":amt/eqo if eqo else None,
                 "cost_basis":amt,"shares":invest/op,"lower":lo,"upper":hi,"target":target,
                 "last":op,"entry_i":cidx[d],"hold_sessions":1,"opening_exposure":exp_open}
            pos[s]=rec
            entries.append({"symbol":s,"entry_date":d,"signal_date":c["signal_date"],
                            "entry_weight":rec["entry_weight"],"cost_basis":amt,
                            "opening_equity":eqo,"opening_exposure":exp_open})

        # intraday
        for s in list(pos):
            p=pos[s];b=bm.get(s,{}).get(d)
            if b is None:continue
            # do not double-count hold increment on entry day
            if p["entry_date"]!=d and p["hold_sessions"]<1:p["hold_sessions"]=1
            lo=float(b["low"]);hi=float(b["high"]);cl=float(b["close"]);px=None;reason=None
            if lo<=p["lower"]:px=p["lower"];reason="stop"
            elif hi>=p["target"]:px=p["target"];reason="target60"
            elif p["hold_sessions"]>=max_hold:px=cl;reason=f"time_h{max_hold}"
            if px is not None:
                proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                trades.append({**p,"exit_date":d,"exit_price":px,"exit_reason":reason,
                               "net_return":proceeds/p["cost_basis"]-1})
                del pos[s]
            else:p["last"]=cl

        val=cash;inv=0.
        for s,p in pos.items():
            b=bm.get(s,{}).get(d);px=float(b["close"]) if b is not None else p["last"];p["last"]=px
            v=p["shares"]*px;val+=v;inv+=v
        daily.append({"date":d,"equity":val,"cash":cash,"exposure":inv/val if val>0 else 0.})
    return pd.DataFrame(trades),pd.DataFrame(entries),pd.DataFrame(daily),{"blocked":blocked,"scaled":scaled}

def tail_from_h15_trade(t,bm,cal):
    # Only time_h15 exits have foregone H20 tail.
    if str(t["exit_reason"])!="time_h15":return None
    s=str(t["symbol"]);d=str(t["exit_date"]);idx={x:i for i,x in enumerate(cal)}
    if d not in idx:return None
    px0=float(t["exit_price"]);lo=float(t["lower"]);target=float(t["target"])
    last=px0
    for j in range(idx[d]+1,min(idx[d]+6,len(cal))):
        day=cal[j];b=bm.get(s,{}).get(day)
        if b is None:continue
        op=float(b["open"]);px=None
        if op<=lo:px=op
        elif op>=target:px=op
        elif float(b["low"])<=lo:px=lo
        elif float(b["high"])>=target:px=target
        else:px=float(b["close"])
        last=px
        # stop/target terminal
        if op<=lo or op>=target or float(b["low"])<=lo or float(b["high"])>=target:break
    return last/px0-1

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=v13.load(a.indir)
    summary={"schema":"PURE-BOX-SIMPLE-CORE-CAPITAL-RECYCLING-ATTRIBUTION-V25","results":{}}
    allrows=[]
    for cap in (300,500):
        cs=v22.bottom20(v13.strict_signals(sig,cap,cal,idx,nxt,bm))
        t20,e20,d20,s20=simulate(cs,cal,bm,20)
        t15,e15,d15,s15=simulate(cs,cal,bm,15)
        # pair entries by symbol/date
        k20={(r.symbol,str(r.entry_date)):r for r in e20.itertuples(index=False)}
        k15={(r.symbol,str(r.entry_date)):r for r in e15.itertuples(index=False)}
        only15=set(k15)-set(k20); only20=set(k20)-set(k15); both=set(k15)&set(k20)
        extra_weight=sum(max(0,float(k15[k].entry_weight)-float(k20[k].entry_weight)) for k in both)
        reduced_weight=sum(max(0,float(k20[k].entry_weight)-float(k15[k].entry_weight)) for k in both)

        tail=[]
        for _,r in t15.iterrows():
            x=tail_from_h15_trade(r,bm,cal)
            if x is not None:tail.append(float(x))
        # realized PnL for H15-only entries and common entry cohorts
        t15map=defaultdict(list);t20map=defaultdict(list)
        for _,r in t15.iterrows():t15map[(str(r.symbol),str(r.entry_date))].append(float(r.net_return))
        for _,r in t20.iterrows():t20map[(str(r.symbol),str(r.entry_date))].append(float(r.net_return))
        only15_trade_returns=[x for k in only15 for x in t15map.get(k,[])]
        only20_trade_returns=[x for k in only20 for x in t20map.get(k,[])]

        end20=float(d20.equity.iloc[-1]);end15=float(d15.equity.iloc[-1])
        res={
          "candidate_n":len(cs),
          "h20_total_return":end20/float(d20.equity.iloc[0])-1,
          "h15_total_return":end15/float(d15.equity.iloc[0])-1,
          "portfolio_return_delta":(end15-end20)/float(d20.equity.iloc[0]),
          "h20_avg_exposure":float(d20.exposure.mean()),"h15_avg_exposure":float(d15.exposure.mean()),
          "h20_avg_cash":float(d20.cash.mean()),"h15_avg_cash":float(d15.cash.mean()),
          "h20_scaled_events":s20["scaled"],"h15_scaled_events":s15["scaled"],
          "h20_blocked":s20["blocked"],"h15_blocked":s15["blocked"],
          "entry_keys_h20":len(k20),"entry_keys_h15":len(k15),
          "entries_only_h15":len(only15),"entries_only_h20":len(only20),
          "common_entry_keys":len(both),
          "common_extra_entry_weight_sum_h15_minus_h20":extra_weight,
          "common_reduced_entry_weight_sum_h15_minus_h20":reduced_weight,
          "h15_time_exit_count":len(tail),
          "foregone_d16_20_tail_mean_return":statistics.mean(tail) if tail else None,
          "foregone_d16_20_tail_median_return":statistics.median(tail) if tail else None,
          "foregone_d16_20_tail_positive_share":sum(x>0 for x in tail)/len(tail) if tail else None,
          "h15_only_entry_completed_trade_n":len(only15_trade_returns),
          "h15_only_entry_mean_trade_return":statistics.mean(only15_trade_returns) if only15_trade_returns else None,
          "h15_only_entry_sum_trade_return":sum(only15_trade_returns),
          "h20_only_entry_completed_trade_n":len(only20_trade_returns),
          "h20_only_entry_mean_trade_return":statistics.mean(only20_trade_returns) if only20_trade_returns else None,
          "mean_daily_cash_advantage_h15_minus_h20":float((d15.set_index("date").cash-d20.set_index("date").cash).mean()),
          "mean_daily_exposure_delta_h15_minus_h20":float((d15.set_index("date").exposure-d20.set_index("date").exposure).mean()),
        }
        summary["results"][f"top{cap}"]=res
        pd.DataFrame(t20).to_csv(out/f"top{cap}_h20_trades.csv",index=False)
        pd.DataFrame(t15).to_csv(out/f"top{cap}_h15_trades.csv",index=False)
        pd.DataFrame(e20).to_csv(out/f"top{cap}_h20_entries.csv",index=False)
        pd.DataFrame(e15).to_csv(out/f"top{cap}_h15_entries.csv",index=False)
        allrows.append({"rank_cap":cap,**res})
    pd.DataFrame(allrows).to_csv(out/"results.csv",index=False)
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
