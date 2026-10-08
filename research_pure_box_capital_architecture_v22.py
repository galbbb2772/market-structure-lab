#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,statistics,math
from collections import defaultdict,Counter
from datetime import date
from pathlib import Path
import pandas as pd
import research_pure_box_core_geometry_simplicity_v13 as v13

ENTRY_COST=v13.ENTRY_COST; EXIT_COST=v13.EXIT_COST
CAP=.50

def bottom20(cands):
    out=[]
    for c in cands:
        lo=float(c["lower"]);hi=float(c["upper"]);op=float(c["direct_entry_price"])
        if hi<=lo:continue
        ef=(op-lo)/(hi-lo)
        if ef<=.20:
            z=dict(c);z["entry_fraction"]=ef;out.append(z)
    return out

def mdd(vals):
    p=vals[0];d=0.
    for x in vals:
        p=max(p,x)
        if p>0:d=min(d,x/p-1)
    return d

def sharpe(vals):
    rs=[vals[i]/vals[i-1]-1 for i in range(1,len(vals)) if vals[i-1]>0]
    if len(rs)<2:return None
    sd=statistics.stdev(rs)
    return None if sd==0 else statistics.mean(rs)/sd*math.sqrt(252)

def pf(rs):
    w=sum(x for x in rs if x>0);l=-sum(x for x in rs if x<0)
    return w/l if l>0 else None

def rb_for(policy,opening_exposure,signal_count):
    if policy=="FIXED_R125":return .0125
    if policy=="FIXED_R150":return .015
    if policy=="EXPOSURE_AWARE":
        if opening_exposure<.25:return .015
        if opening_exposure>.60:return .01
        return .0125
    if policy=="SIGNAL_DENSITY_AWARE":
        if signal_count<=1:return .015
        if signal_count>=4:return .01
        return .0125
    raise ValueError(policy)

def run(cands,calendar,bm,policy,exit_mode):
    cidx={d:i for i,d in enumerate(calendar)}
    by=defaultdict(list)
    for c in cands:
        d=str(c["direct_entry_date"])
        if v13.VAL_START<=d<=v13.VAL_END and d in cidx:by[d].append(c)
    days=[d for d in calendar if v13.VAL_START<=d<=v13.VAL_END]
    cash=1.;pos={};eq=[];expo=[];trs=[]
    req_risk_sum=0.;real_risk_sum=0.;scaled=0;blocked=0;entries=0
    idle_days=0;concurrency=[];turnover=0.;high_exp_pnl=[]
    for d in days:
        # gap exits
        for s in list(pos):
            b=bm.get(s,{}).get(d)
            if b is None:continue
            p=pos[s];op=float(b["open"]);px=None;reason=None
            if op<=p["lower"]:px=op;reason="stop_gap"
            elif op>=p["target"]:px=op;reason="target_gap"
            if px is not None:
                proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                r=proceeds/p["cost_basis"]-1;trs.append(r)
                if p["opening_exposure"]>.60:high_exp_pnl.append(r)
                turnover+=p["cost_basis"];del pos[s]

        cand=[c for c in by.get(d,[]) if str(c["symbol"]) not in pos]
        cand.sort(key=lambda x:(str(x["symbol"]),str(x["signal_date"])))
        seen=set();ded=[]
        for c in cand:
            s=str(c["symbol"])
            if s in seen:continue
            seen.add(s);ded.append(c)
        cand=ded

        eqo=cash;invested_open=0.
        for s,p in pos.items():
            b=bm.get(s,{}).get(d);z=p["shares"]*(float(b["open"]) if b is not None else p["last"])
            eqo+=z;invested_open+=z
        opening_exposure=invested_open/eqo if eqo>0 else 0.

        valid=[]
        for c in cand:
            s=str(c["symbol"]);b=bm.get(s,{}).get(d)
            if b is None:continue
            op=float(b["open"]);lo=float(c["lower"]);hi=float(c["upper"]);target=lo+.60*(hi-lo)
            if not(lo<op<target):continue
            ef=(op-lo)/(hi-lo)
            if ef>.20:continue
            riskpd=1-(lo*(1-EXIT_COST))/(op*(1+ENTRY_COST))
            if riskpd<=0:continue
            valid.append((c,op,lo,hi,target,riskpd))

        rb=rb_for(policy,opening_exposure,len(valid))
        reqs=[]
        for c,op,lo,hi,target,riskpd in valid:
            raw=rb*eqo/riskpd
            req=min(raw,CAP*eqo)
            reqs.append(req);req_risk_sum+=rb*eqo
        total=sum(reqs);sc=min(1.,cash/total) if total>0 else 0.
        if total>cash+1e-12:scaled+=len(valid)
        for (c,op,lo,hi,target,riskpd),req in zip(valid,reqs):
            amt=req*sc
            if amt<=1e-12:
                blocked+=1;continue
            if sc<1-1e-12: pass
            real_risk_sum+=amt*riskpd;entries+=1
            invest=amt*(1-ENTRY_COST);cash-=amt;s=str(c["symbol"])
            pos[s]={"shares":invest/op,"cost_basis":amt,"entry_i":cidx[d],
                    "lower":lo,"upper":hi,"target":target,"last":op,
                    "entry_price":op,"opening_exposure":opening_exposure}
            turnover+=amt

        # intraday lifecycle + alternate exits
        for s in list(pos):
            p=pos[s];b=bm.get(s,{}).get(d)
            hold=cidx[d]-p["entry_i"]+1
            if b is None:continue
            lo=float(b["low"]);hi=float(b["high"]);cl=float(b["close"]);px=None;reason=None
            if lo<=p["lower"]:px=p["lower"];reason="stop"
            elif hi>=p["target"]:px=p["target"];reason="target60"
            else:
                if exit_mode=="H10" and hold>=10: px=cl;reason="time_h10"
                elif exit_mode=="H15" and hold>=15: px=cl;reason="time_h15"
                elif exit_mode=="EARLY_STALE_EXIT" and hold==10:
                    box=p["upper"]-p["lower"]
                    progress=(cl-p["entry_price"])/box if box>0 else 0
                    if progress<.10: px=cl;reason="stale_d10"
                if px is None and hold>=20: px=cl;reason="time_h20"
            if px is not None:
                proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                r=proceeds/p["cost_basis"]-1;trs.append(r)
                if p["opening_exposure"]>.60:high_exp_pnl.append(r)
                turnover+=p["cost_basis"];del pos[s]
            else:p["last"]=cl

        val=cash;inv=0.
        for s,p in pos.items():
            b=bm.get(s,{}).get(d);px=float(b["close"]) if b is not None else p["last"];p["last"]=px
            z=p["shares"]*px;val+=z;inv+=z
        e=inv/val if val>0 else 0.
        if e<.10:idle_days+=1
        expo.append(e);concurrency.append(len(pos));eq.append((d,val))

    vals=[v for _,v in eq]
    edf=pd.DataFrame(eq,columns=["date","equity"]);edf["year"]=edf.date.str[:4]
    roll=[]
    for i in range(251,len(edf)):
        g=edf.iloc[i-251:i+1];roll.append(float(g.equity.iloc[-1]/g.equity.iloc[0]-1))
    yrs=max((date.fromisoformat(days[-1])-date.fromisoformat(days[0])).days/365.2425,1/365)
    return {
      "total_return":vals[-1]/vals[0]-1,
      "cagr":(vals[-1]/vals[0])**(1/yrs)-1,
      "max_drawdown":mdd(vals),"daily_sharpe":sharpe(vals),
      "avg_exposure":statistics.mean(expo),"idle_day_share":idle_days/len(days),
      "median_concurrent":statistics.median(concurrency),"max_concurrent":max(concurrency),
      "completed_trades":len(trs),"profit_factor":pf(trs),
      "mean_trade":statistics.mean(trs) if trs else None,
      "win_rate":sum(x>0 for x in trs)/len(trs) if trs else None,
      "entries":entries,"scaled_entry_events":scaled,"blocked_entries":blocked,
      "requested_risk_sum":req_risk_sum,"realized_planned_risk_sum":real_risk_sum,
      "risk_realization_ratio":real_risk_sum/req_risk_sum if req_risk_sum else None,
      "turnover_proxy":turnover,
      "high_opening_exposure_trade_mean":statistics.mean(high_exp_pnl) if high_exp_pnl else None,
      "high_opening_exposure_trade_n":len(high_exp_pnl),
      "yearly_return":{y:float(g.equity.iloc[-1]/g.equity.iloc[0]-1) for y,g in edf.groupby("year")},
      "rolling_12m_min_return":min(roll) if roll else None,
      "rolling_12m_positive_share":sum(x>0 for x in roll)/len(roll) if roll else None,
      "rolling_12m_median_return":statistics.median(roll) if roll else None,
    }

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=v13.load(a.indir)
    rows=[];summary={"schema":"PURE-BOX-SIMPLE-CORE-CAPITAL-ARCHITECTURE-V22","results":{}}
    policies=("FIXED_R125","FIXED_R150","EXPOSURE_AWARE","SIGNAL_DENSITY_AWARE")
    exits=("H20","H15","H10","EARLY_STALE_EXIT")
    for cap in (300,500):
        base=bottom20(v13.strict_signals(sig,cap,cal,idx,nxt,bm))
        # risk-budget policies use H20 anchor
        for pol in policies:
            r=run(base,cal,bm,pol,"H20")
            key=f"top{cap}__risk__{pol}"
            summary["results"][key]={**r,"rank_cap":cap,"axis":"risk","policy":pol,"exit_mode":"H20","candidate_n":len(base)}
            rows.append(summary["results"][key])
        # exit recycling uses frozen 1.25% risk
        for ex in exits:
            r=run(base,cal,bm,"FIXED_R125",ex)
            key=f"top{cap}__exit__{ex}"
            summary["results"][key]={**r,"rank_cap":cap,"axis":"exit","policy":"FIXED_R125","exit_mode":ex,"candidate_n":len(base)}
            rows.append(summary["results"][key])
    pd.DataFrame(rows).to_csv(out/"results.csv",index=False)
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    cols=["rank_cap","axis","policy","exit_mode","total_return","cagr","max_drawdown","daily_sharpe",
          "avg_exposure","idle_day_share","risk_realization_ratio","turnover_proxy","completed_trades",
          "rolling_12m_min_return","rolling_12m_positive_share"]
    print(pd.DataFrame(rows)[cols].to_string(index=False))
if __name__=="__main__":main()
