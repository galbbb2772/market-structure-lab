#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,statistics,math
from collections import defaultdict
from datetime import date
from pathlib import Path
import pandas as pd
import research_pure_box_core_geometry_simplicity_v13 as v13
import research_pure_box_capital_architecture_v22 as v22

CAP=.50; H=15; INITIAL_RISK=.0125; ADDON_RISK=.025

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

def allow_addon(policy,age,op,entry):
    if policy=="EARLY_R250_BASE": return age<=3
    if policy=="NEGATIVE_ONLY_R250": return age<=3 and op<=entry
    if policy=="AGE3_ONLY_R250": return age==3
    if policy=="AGE3_NEGATIVE_R250": return age==3 and op<=entry
    if policy=="AGE2_NEGATIVE_R250": return age==2 and op<=entry
    raise ValueError(policy)

def run(cands,calendar,bm,policy,bps):
    ec=xc=bps/10000.0
    cidx={d:i for i,d in enumerate(calendar)}
    by=defaultdict(list)
    for c in cands:
        d=str(c["direct_entry_date"])
        if v13.VAL_START<=d<=v13.VAL_END and d in cidx:by[d].append(c)
    days=[d for d in calendar if v13.VAL_START<=d<=v13.VAL_END]
    cash=1.;pos={};eq=[];expo=[];trs=[];funded=defaultdict(float)
    addons=[];blocked=partial=0

    for d in days:
        for s in list(pos):
            b=bm.get(s,{}).get(d)
            if b is None: continue
            p=pos[s];p["hold"]+=1;o=float(b["open"]);px=None
            if o<=p["lower"]:px=o
            elif o>=p["target"]:px=o
            if px is not None:
                proceeds=p["shares"]*px*(1-xc);cash+=proceeds
                r=proceeds/p["cost_basis"]-1;trs.append(r);funded[s]+=p["cost_basis"]*r
                for a in p.get("addon_ids",[]):addons[a]["ret"]=px*(1-xc)/(addons[a]["entry"]*(1+ec))-1
                del pos[s]

        eqo=cash;openval={}
        for s,p in pos.items():
            b=bm.get(s,{}).get(d);op=float(b["open"]) if b is not None else p["last"]
            v=p["shares"]*op;openval[s]=v;eqo+=v

        acts=[];seen=set()
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
            riskpd=1-(lo*(1-xc))/(op*(1+ec))
            if riskpd<=0:continue

            if s in pos:
                p=pos[s];age=int(p["hold"]);entry=float(p["entry_price"])
                if not allow_addon(policy,age,op,entry):continue
                curr=max(0.,p["shares"]*(op-p["lower"]*(1-xc)))
                add=max(0.,ADDON_RISK*eqo-curr)
                if add<=1e-12:continue
                head=max(0.,CAP*eqo-openval.get(s,0.))
                req=min(add/riskpd,head)
                if req<=1e-12:continue
                acts.append({"kind":"addon","symbol":s,"liquidity_rank":int(c["liquidity_rank"]),
                             "entry_fraction":ef,"request":req,"entry_price":op,"lower":lo,"target":target,
                             "existing_age":age})
            else:
                req=min(INITIAL_RISK*eqo/riskpd,CAP*eqo)
                acts.append({"kind":"new","symbol":s,"liquidity_rank":int(c["liquidity_rank"]),
                             "entry_fraction":ef,"request":req,"entry_price":op,"lower":lo,"target":target})
        acts.sort(key=lambda x:(x["liquidity_rank"],x["entry_fraction"],x["symbol"],0 if x["kind"]=="new" else 1))
        rem=cash
        for a in acts:
            amt=min(a["request"],rem) if rem>0 else 0.;rem-=amt
            if amt<=1e-12:
                if a["kind"]=="new":blocked+=1
                continue
            if a["kind"]=="new" and amt+1e-12<a["request"]:partial+=1
            inv=amt*(1-ec);cash-=amt
            if a["kind"]=="new":
                pos[a["symbol"]]={**a,"shares":inv/a["entry_price"],"cost_basis":amt,"hold":1,
                                  "last":a["entry_price"],"addon_ids":[]}
            else:
                p=pos[a["symbol"]];p["shares"]+=inv/a["entry_price"];p["cost_basis"]+=amt
                addons.append({"symbol":a["symbol"],"date":d,"year":d[:4],"age":a["existing_age"],
                               "capital":amt,"entry":a["entry_price"],"ret":None})
                p["addon_ids"].append(len(addons)-1)

        for s in list(pos):
            p=pos[s];b=bm.get(s,{}).get(d)
            if b is None:continue
            lo=float(b["low"]);hi=float(b["high"]);cl=float(b["close"]);px=None
            if lo<=p["lower"]:px=p["lower"]
            elif hi>=p["target"]:px=p["target"]
            elif p["hold"]>=H:px=cl
            if px is not None:
                proceeds=p["shares"]*px*(1-xc);cash+=proceeds
                r=proceeds/p["cost_basis"]-1;trs.append(r);funded[s]+=p["cost_basis"]*r
                for a in p.get("addon_ids",[]):addons[a]["ret"]=px*(1-xc)/(addons[a]["entry"]*(1+ec))-1
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
    yr={y:float(g.equity.iloc[-1]/g.equity.iloc[0]-1) for y,g in edf.groupby("year")}
    block=1.0
    for y in sorted(yr):
        if y!="2025":block*=1+yr[y]
    adf=pd.DataFrame(addons)
    if len(adf):
        adone=adf.dropna(subset=["ret"]).copy()
        adone["pnl"]=adone.capital*adone.ret
    else:
        adone=pd.DataFrame()
    return {
      "total_return":vals[-1]/vals[0]-1,"cagr":(vals[-1]/vals[0])**(1/yrs)-1,
      "max_drawdown":mdd(vals),"daily_sharpe":sharpe(vals),
      "avg_exposure":statistics.mean(expo),"completed_trades":len(trs),"profit_factor":pf(trs),
      "blocked_new_entries":blocked,"partial_new_entries":partial,
      "add_on_events":int(len(adone)),"add_on_capital":float(adone.capital.sum()) if len(adone) else 0.,
      "yearly_return":yr,"ex_2025_block_compound":block-1,
      "rolling_12m_min_return":min(roll) if roll else None,
      "rolling_12m_median_return":statistics.median(roll) if roll else None,
      "rolling_12m_positive_share":sum(x>0 for x in roll)/len(roll) if roll else None,
      "top5_abs_funded_pnl_share":sum(absvals[:5])/tot if tot else None,
      "top10_abs_funded_pnl_share":sum(absvals[:10])/tot if tot else None,
      "addon_mean_return":float(adone.ret.mean()) if len(adone) else None,
      "addon_pf":pf(adone.ret.tolist()) if len(adone) else None,
      "addon_sum_pnl":float(adone.pnl.sum()) if len(adone) else 0.
    }

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=v13.load(a.indir)
    policies=("EARLY_R250_BASE","NEGATIVE_ONLY_R250","AGE3_ONLY_R250","AGE3_NEGATIVE_R250","AGE2_NEGATIVE_R250")
    rows=[];summary={"schema":"PURE-BOX-SIMPLE-CORE-PATH-STATE-ROBUSTNESS-V47","results":{}}
    for cap in (300,500):
        cs=v22.bottom20(v13.strict_signals(sig,cap,cal,idx,nxt,bm))
        for bps in (5,10,20):
            for p in policies:
                r=run(cs,cal,bm,p,bps)
                key=f"top{cap}__{bps}bps__{p}"
                summary["results"][key]=r
                rows.append({"rank_cap":cap,"bps":bps,"policy":p,**r})
    pd.DataFrame(rows).to_csv(out/"results.csv",index=False)
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(pd.DataFrame(rows)[["rank_cap","bps","policy","total_return","max_drawdown","daily_sharpe","rolling_12m_min_return","ex_2025_block_compound","add_on_events"]].to_string(index=False))
if __name__=="__main__":main()
