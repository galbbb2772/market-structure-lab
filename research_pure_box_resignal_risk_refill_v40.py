#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,statistics,math
from collections import defaultdict
from datetime import date
from pathlib import Path
import pandas as pd
import research_pure_box_core_geometry_simplicity_v13 as v13
import research_pure_box_capital_architecture_v22 as v22

EC=v13.ENTRY_COST; XC=v13.EXIT_COST
RB=.0125; CAP=.50; H=15

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

def target_risk(policy):
    return {
      "SKIP_OVERLAP":None,
      "REFILL_TO_R125":.0125,
      "REFILL_TO_R150":.015,
      "PYRAMID_TO_R250":.025
    }[policy]

def run(cands,calendar,bm,policy):
    cidx={d:i for i,d in enumerate(calendar)}
    by=defaultdict(list)
    for c in cands:
        d=str(c["direct_entry_date"])
        if v13.VAL_START<=d<=v13.VAL_END and d in cidx: by[d].append(c)
    days=[d for d in calendar if v13.VAL_START<=d<=v13.VAL_END]

    cash=1.;pos={};eq=[];expo=[];trs=[];funded=defaultdict(float)
    blocked_new=partial_new=0; add_events=0;add_capital=0.;cap_hits=0
    risk_after_add=[];max_pos_risk=0.;turnover=0.

    for d in days:
        # age + gap exits
        for s in list(pos):
            b=bm.get(s,{}).get(d)
            if b is None:continue
            p=pos[s];p["hold"]+=1;o=float(b["open"]);px=None
            if o<=p["lower"]:px=o
            elif o>=p["target"]:px=o
            if px is not None:
                proceeds=p["shares"]*px*(1-XC);cash+=proceeds;turnover+=proceeds
                r=proceeds/p["cost_basis"]-1;trs.append(r);funded[s]+=p["cost_basis"]*r
                del pos[s]

        eqo=cash;open_value={}
        for s,p in pos.items():
            b=bm.get(s,{}).get(d);op=float(b["open"]) if b is not None else p["last"]
            v=p["shares"]*op;open_value[s]=v;eqo+=v

        actions=[];seen=set()
        for c in sorted(by.get(d,[]),key=lambda x:(str(x["symbol"]),str(x["signal_date"]))):
            s=str(c["symbol"])
            if s in seen:continue
            seen.add(s)
            b=bm.get(s,{}).get(d)
            if b is None:continue
            op=float(b["open"]);lo=float(c["lower"]);hi=float(c["upper"]);target=lo+.60*(hi-lo)
            if not(lo<op<target):continue
            ef=(op-lo)/(hi-lo)
            if ef>.20:continue
            riskpd=1-(lo*(1-XC))/(op*(1+EC))
            if riskpd<=0:continue

            if s in pos:
                if policy=="SKIP_OVERLAP":continue
                p=pos[s]
                # same-box invariant is diagnostic from V39; use existing stop/target/age.
                curr_risk_dollars=max(0.,p["shares"]*(op-lo*(1-XC)))
                tgt=target_risk(policy)*eqo
                add_risk=max(0.,tgt-curr_risk_dollars)
                if add_risk<=1e-12:continue
                headroom=max(0.,CAP*eqo-open_value.get(s,0.))
                req=min(add_risk/riskpd,headroom)
                if req<=1e-12:continue
                actions.append({
                  "kind":"addon","symbol":s,"liquidity_rank":int(c["liquidity_rank"]),
                  "entry_fraction":ef,"request":req,"entry_price":op,"lower":lo,
                  "upper":hi,"target":target,"risk_per_dollar":riskpd
                })
            else:
                req=min(RB*eqo/riskpd,CAP*eqo)
                actions.append({
                  "kind":"new","symbol":s,"liquidity_rank":int(c["liquidity_rank"]),
                  "entry_fraction":ef,"request":req,"entry_price":op,"lower":lo,
                  "upper":hi,"target":target,"risk_per_dollar":riskpd
                })

        actions.sort(key=lambda x:(x["liquidity_rank"],x["entry_fraction"],x["symbol"],0 if x["kind"]=="new" else 1))
        rem=cash
        for a in actions:
            amt=min(a["request"],rem) if rem>0 else 0.
            rem-=amt
            if amt<=1e-12:
                if a["kind"]=="new":blocked_new+=1
                continue
            invest=amt*(1-EC);cash-=amt;turnover+=amt
            if a["kind"]=="new":
                if amt+1e-12<a["request"]:partial_new+=1
                pos[a["symbol"]]={**a,"shares":invest/a["entry_price"],"cost_basis":amt,
                                  "hold":1,"last":a["entry_price"]}
            else:
                p=pos[a["symbol"]]
                p["shares"]+=invest/a["entry_price"];p["cost_basis"]+=amt
                # do not reset age/stop/target.
                add_events+=1;add_capital+=amt
                post_risk=max(0.,p["shares"]*(a["entry_price"]-p["lower"]*(1-XC)))/eqo
                risk_after_add.append(post_risk);max_pos_risk=max(max_pos_risk,post_risk)
                post_weight=p["shares"]*a["entry_price"]/eqo
                if post_weight>=CAP-1e-6:cap_hits+=1

        # intraday exits
        for s in list(pos):
            p=pos[s];b=bm.get(s,{}).get(d)
            if b is None:continue
            lo=float(b["low"]);hi=float(b["high"]);cl=float(b["close"]);px=None
            if lo<=p["lower"]:px=p["lower"]
            elif hi>=p["target"]:px=p["target"]
            elif p["hold"]>=H:px=cl
            if px is not None:
                proceeds=p["shares"]*px*(1-XC);cash+=proceeds;turnover+=proceeds
                r=proceeds/p["cost_basis"]-1;trs.append(r);funded[s]+=p["cost_basis"]*r
                del pos[s]
            else:p["last"]=cl

        val=cash;inv=0.
        for s,p in pos.items():
            b=bm.get(s,{}).get(d);px=float(b["close"]) if b is not None else p["last"];p["last"]=px
            v=p["shares"]*px;val+=v;inv+=v
        eq.append((d,val));expo.append(inv/val if val>0 else 0.)

    vals=[v for _,v in eq]
    edf=pd.DataFrame(eq,columns=["date","equity"]);edf["year"]=edf.date.str[:4]
    roll=[]
    for i in range(251,len(edf)):
        g=edf.iloc[i-251:i+1];roll.append(float(g.equity.iloc[-1]/g.equity.iloc[0]-1))
    yrs=max((date.fromisoformat(days[-1])-date.fromisoformat(days[0])).days/365.2425,1/365)
    absvals=sorted((abs(v) for v in funded.values()),reverse=True);tot=sum(absvals)
    return {
      "total_return":vals[-1]/vals[0]-1,"cagr":(vals[-1]/vals[0])**(1/yrs)-1,
      "max_drawdown":mdd(vals),"daily_sharpe":sharpe(vals),
      "avg_exposure":statistics.mean(expo),"idle_day_share":sum(x<.10 for x in expo)/len(expo),
      "completed_trades":len(trs),"profit_factor":pf(trs),"mean_trade":statistics.mean(trs) if trs else None,
      "blocked_new_entries":blocked_new,"partial_new_entries":partial_new,
      "add_on_events":add_events,"add_on_capital":add_capital,
      "mean_position_risk_after_add":statistics.mean(risk_after_add) if risk_after_add else None,
      "max_position_risk_after_add":max_pos_risk if risk_after_add else None,
      "single_name_cap_hit_count":cap_hits,
      "turnover_proxy":turnover,
      "top5_abs_funded_pnl_share":sum(absvals[:5])/tot if tot else None,
      "top10_abs_funded_pnl_share":sum(absvals[:10])/tot if tot else None,
      "yearly_return":{y:float(g.equity.iloc[-1]/g.equity.iloc[0]-1) for y,g in edf.groupby("year")},
      "rolling_12m_min_return":min(roll) if roll else None,
      "rolling_12m_positive_share":sum(x>0 for x in roll)/len(roll) if roll else None,
      "rolling_12m_median_return":statistics.median(roll) if roll else None
    }

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=v13.load(a.indir)
    rows=[];summary={"schema":"PURE-BOX-SIMPLE-CORE-RESIGNAL-RISK-REFILL-V40","results":{}}
    for cap in (300,500):
        cs=v22.bottom20(v13.strict_signals(sig,cap,cal,idx,nxt,bm))
        for pol in ("SKIP_OVERLAP","REFILL_TO_R125","REFILL_TO_R150","PYRAMID_TO_R250"):
            r=run(cs,cal,bm,pol)
            row={"rank_cap":cap,"policy":pol,**r};rows.append(row)
            summary["results"][f"top{cap}__{pol}"]=row
    pd.DataFrame(rows).to_csv(out/"results.csv",index=False)
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(pd.DataFrame(rows)[["rank_cap","policy","total_return","cagr","max_drawdown","daily_sharpe",
                              "rolling_12m_min_return","add_on_events","mean_position_risk_after_add",
                              "max_position_risk_after_add"]].to_string(index=False))
if __name__=="__main__":main()
