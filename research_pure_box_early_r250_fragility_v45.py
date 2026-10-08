#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,statistics,math
from collections import defaultdict
from datetime import date
from pathlib import Path
import pandas as pd
import research_pure_box_core_geometry_simplicity_v13 as v13
import research_pure_box_capital_architecture_v22 as v22
import research_pure_box_early_resignal_pyramiding_v43 as v43

EC=v13.ENTRY_COST; XC=v13.EXIT_COST
RB=.0125; CAP=.50; H=15; TARGET_RISK=.025

def pf(rs):
    w=sum(x for x in rs if x>0);l=-sum(x for x in rs if x<0)
    return w/l if l>0 else None

def event_log(cands,calendar,bm):
    cidx={d:i for i,d in enumerate(calendar)}
    by=defaultdict(list)
    for c in cands:
        d=str(c["direct_entry_date"])
        if v13.VAL_START<=d<=v13.VAL_END and d in cidx:by[d].append(c)
    days=[d for d in calendar if v13.VAL_START<=d<=v13.VAL_END]
    cash=1.;pos={};events=[];eid=0
    for d in days:
        for s in list(pos):
            b=bm.get(s,{}).get(d)
            if b is None:continue
            p=pos[s];p["hold"]+=1;o=float(b["open"]);px=None;reason=None
            if o<=p["lower"]:px=o;reason="stop_gap"
            elif o>=p["target"]:px=o;reason="target_gap"
            if px is not None:
                proceeds=p["shares"]*px*(1-XC);cash+=proceeds
                for e in p.get("addon_ids",[]):
                    rec=events[e];rec["exit_date"]=d;rec["exit_reason"]=reason
                    rec["addon_slice_return"]=px*(1-XC)/(rec["addon_entry_price"]*(1+EC))-1
                    rec["addon_slice_pnl"]=rec["addon_funded_capital"]*rec["addon_slice_return"]
                del pos[s]
        eqo=cash;openv={}
        for s,p in pos.items():
            b=bm.get(s,{}).get(d);op=float(b["open"]) if b is not None else p["last"]
            v=p["shares"]*op;openv[s]=v;eqo+=v
        actions=[];seen=set()
        for c in sorted(by.get(d,[]),key=lambda x:(str(x["symbol"]),str(x["signal_date"]))):
            s=str(c["symbol"])
            if s in seen:continue
            seen.add(s);b=bm.get(s,{}).get(d)
            if b is None:continue
            op=float(b["open"]);lo=float(c["lower"]);hi=float(c["upper"]);target=lo+.60*(hi-lo)
            if not(lo<op<target):continue
            ef=(op-lo)/(hi-lo)
            if ef>.20:continue
            riskpd=1-(lo*(1-XC))/(op*(1+EC))
            if riskpd<=0:continue
            if s in pos:
                p=pos[s]
                if int(p["hold"])>3:continue
                curr=max(0.,p["shares"]*(op-p["lower"]*(1-XC)))
                add_risk=max(0.,TARGET_RISK*eqo-curr)
                if add_risk<=1e-12:continue
                raw=add_risk/riskpd;head=max(0.,CAP*eqo-openv.get(s,0.));req=min(raw,head)
                if req<=1e-12:continue
                actions.append({"kind":"addon","symbol":s,"liquidity_rank":int(c["liquidity_rank"]),
                                "entry_fraction":ef,"request":req,"entry_price":op,"lower":lo,"upper":hi,
                                "target":target,"risk_per_dollar":riskpd,"existing_age":int(p["hold"]),
                                "risk_before":curr/eqo if eqo else None})
            else:
                req=min(RB*eqo/riskpd,CAP*eqo)
                actions.append({"kind":"new","symbol":s,"liquidity_rank":int(c["liquidity_rank"]),
                                "entry_fraction":ef,"request":req,"entry_price":op,"lower":lo,"upper":hi,
                                "target":target,"risk_per_dollar":riskpd})
        actions.sort(key=lambda x:(x["liquidity_rank"],x["entry_fraction"],x["symbol"],0 if x["kind"]=="new" else 1))
        rem=cash
        for a in actions:
            amt=min(a["request"],rem) if rem>0 else 0.;rem-=amt
            if amt<=1e-12:continue
            invest=amt*(1-EC);cash-=amt
            if a["kind"]=="new":
                pos[a["symbol"]]={**a,"shares":invest/a["entry_price"],"cost_basis":amt,"hold":1,"last":a["entry_price"],"addon_ids":[]}
            else:
                p=pos[a["symbol"]];p["shares"]+=invest/a["entry_price"];p["cost_basis"]+=amt
                rr=max(0.,p["shares"]*(a["entry_price"]-p["lower"]*(1-XC)))/eqo if eqo else None
                ev={"event_id":eid,"date":d,"year":d[:4],"symbol":a["symbol"],"existing_age":a["existing_age"],
                    "entry_fraction":a["entry_fraction"],"risk_before":a["risk_before"],"risk_after":rr,
                    "addon_funded_capital":amt,"addon_entry_price":a["entry_price"],
                    "exit_date":None,"exit_reason":None,"addon_slice_return":None,"addon_slice_pnl":None}
                events.append(ev);p["addon_ids"].append(eid);eid+=1
        for s in list(pos):
            p=pos[s];b=bm.get(s,{}).get(d)
            if b is None:continue
            lo=float(b["low"]);hi=float(b["high"]);cl=float(b["close"]);px=None;reason=None
            if lo<=p["lower"]:px=p["lower"];reason="stop"
            elif hi>=p["target"]:px=p["target"];reason="target60"
            elif p["hold"]>=H:px=cl;reason="time_h15"
            if px is not None:
                proceeds=p["shares"]*px*(1-XC);cash+=proceeds
                for e in p.get("addon_ids",[]):
                    rec=events[e];rec["exit_date"]=d;rec["exit_reason"]=reason
                    rec["addon_slice_return"]=px*(1-XC)/(rec["addon_entry_price"]*(1+EC))-1
                    rec["addon_slice_pnl"]=rec["addon_funded_capital"]*rec["addon_slice_return"]
                del pos[s]
            else:p["last"]=cl
    return pd.DataFrame(events)

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

def run_ablate_2025(cands,calendar,bm):
    cidx={d:i for i,d in enumerate(calendar)}
    by=defaultdict(list)
    for c in cands:
        d=str(c["direct_entry_date"])
        if v13.VAL_START<=d<=v13.VAL_END and d in cidx:by[d].append(c)
    days=[d for d in calendar if v13.VAL_START<=d<=v13.VAL_END]
    cash=1.;pos={};eq=[];expo=[];trs=[]
    for d in days:
        for s in list(pos):
            b=bm.get(s,{}).get(d)
            if b is None:continue
            p=pos[s];p["hold"]+=1;o=float(b["open"]);px=None
            if o<=p["lower"]:px=o
            elif o>=p["target"]:px=o
            if px is not None:
                proceeds=p["shares"]*px*(1-XC);cash+=proceeds;trs.append(proceeds/p["cost_basis"]-1);del pos[s]
        eqo=cash;openv={}
        for s,p in pos.items():
            b=bm.get(s,{}).get(d);op=float(b["open"]) if b is not None else p["last"]
            v=p["shares"]*op;openv[s]=v;eqo+=v
        actions=[];seen=set()
        for c in sorted(by.get(d,[]),key=lambda x:(str(x["symbol"]),str(x["signal_date"]))):
            s=str(c["symbol"])
            if s in seen:continue
            seen.add(s);b=bm.get(s,{}).get(d)
            if b is None:continue
            op=float(b["open"]);lo=float(c["lower"]);hi=float(c["upper"]);target=lo+.60*(hi-lo)
            if not(lo<op<target):continue
            ef=(op-lo)/(hi-lo)
            if ef>.20:continue
            riskpd=1-(lo*(1-XC))/(op*(1+EC))
            if riskpd<=0:continue
            if s in pos:
                p=pos[s]
                if d[:4]=="2025" or int(p["hold"])>3:continue
                curr=max(0.,p["shares"]*(op-p["lower"]*(1-XC)));add=max(0.,TARGET_RISK*eqo-curr)
                if add<=1e-12:continue
                head=max(0.,CAP*eqo-openv.get(s,0.));req=min(add/riskpd,head)
                if req<=1e-12:continue
                actions.append({"kind":"addon","symbol":s,"liquidity_rank":int(c["liquidity_rank"]),
                                "entry_fraction":ef,"request":req,"entry_price":op,"lower":lo,"upper":hi,"target":target})
            else:
                req=min(RB*eqo/riskpd,CAP*eqo)
                actions.append({"kind":"new","symbol":s,"liquidity_rank":int(c["liquidity_rank"]),
                                "entry_fraction":ef,"request":req,"entry_price":op,"lower":lo,"upper":hi,"target":target})
        actions.sort(key=lambda x:(x["liquidity_rank"],x["entry_fraction"],x["symbol"],0 if x["kind"]=="new" else 1))
        rem=cash
        for a in actions:
            amt=min(a["request"],rem) if rem>0 else 0.;rem-=amt
            if amt<=1e-12:continue
            invest=amt*(1-EC);cash-=amt
            if a["kind"]=="new":
                pos[a["symbol"]]={**a,"shares":invest/a["entry_price"],"cost_basis":amt,"hold":1,"last":a["entry_price"]}
            else:
                p=pos[a["symbol"]];p["shares"]+=invest/a["entry_price"];p["cost_basis"]+=amt
        for s in list(pos):
            p=pos[s];b=bm.get(s,{}).get(d)
            if b is None:continue
            lo=float(b["low"]);hi=float(b["high"]);cl=float(b["close"]);px=None
            if lo<=p["lower"]:px=p["lower"]
            elif hi>=p["target"]:px=p["target"]
            elif p["hold"]>=H:px=cl
            if px is not None:
                proceeds=p["shares"]*px*(1-XC);cash+=proceeds;trs.append(proceeds/p["cost_basis"]-1);del pos[s]
            else:p["last"]=cl
        val=cash;inv=0.
        for s,p in pos.items():
            b=bm.get(s,{}).get(d);px=float(b["close"]) if b is not None else p["last"];p["last"]=px
            v=p["shares"]*px;val+=v;inv+=v
        eq.append((d,val));expo.append(inv/val if val else 0.)
    vals=[v for _,v in eq]
    edf=pd.DataFrame(eq,columns=["date","equity"]);edf["year"]=edf.date.str[:4]
    roll=[]
    for i in range(251,len(edf)):
        g=edf.iloc[i-251:i+1];roll.append(float(g.equity.iloc[-1]/g.equity.iloc[0]-1))
    yrs=max((date.fromisoformat(days[-1])-date.fromisoformat(days[0])).days/365.2425,1/365)
    return {"total_return":vals[-1]/vals[0]-1,"cagr":(vals[-1]/vals[0])**(1/yrs)-1,
            "max_drawdown":mdd(vals),"daily_sharpe":sharpe(vals),
            "rolling_12m_min_return":min(roll) if roll else None,
            "rolling_12m_positive_share":sum(x>0 for x in roll)/len(roll) if roll else None,
            "yearly_return":{y:float(g.equity.iloc[-1]/g.equity.iloc[0]-1) for y,g in edf.groupby("year")}}

def summarize_events(df):
    d=df.dropna(subset=["addon_slice_pnl"]).copy()
    abs_event=d.addon_slice_pnl.abs().sort_values(ascending=False)
    etot=float(abs_event.sum()) if len(abs_event) else 0.
    bysym=d.groupby("symbol").addon_slice_pnl.sum().abs().sort_values(ascending=False)
    stot=float(bysym.sum()) if len(bysym) else 0.
    positive=d[d.addon_slice_pnl>0].addon_slice_pnl
    pos_total=float(positive.sum()) if len(positive) else 0.
    pos2025=float(d[(d.year=="2025")&(d.addon_slice_pnl>0)].addon_slice_pnl.sum()) if len(d) else 0.
    ex=d[d.year!="2025"]
    rs=ex.addon_slice_return.tolist()
    return {
      "n":int(len(d)),"unique_symbols":int(d.symbol.nunique()) if len(d) else 0,
      "sum_slice_pnl":float(d.addon_slice_pnl.sum()) if len(d) else 0.,
      "top1_event_abs_share":float(abs_event.head(1).sum()/etot) if etot else None,
      "top3_event_abs_share":float(abs_event.head(3).sum()/etot) if etot else None,
      "top5_event_abs_share":float(abs_event.head(5).sum()/etot) if etot else None,
      "top1_symbol_abs_share":float(bysym.head(1).sum()/stot) if stot else None,
      "top3_symbol_abs_share":float(bysym.head(3).sum()/stot) if stot else None,
      "top5_symbol_abs_share":float(bysym.head(5).sum()/stot) if stot else None,
      "positive_pnl_share_from_2025":pos2025/pos_total if pos_total else None,
      "ex2025_n":int(len(ex)),"ex2025_mean_return":float(ex.addon_slice_return.mean()) if len(ex) else None,
      "ex2025_sum_pnl":float(ex.addon_slice_pnl.sum()) if len(ex) else None,
      "ex2025_profit_factor":pf(rs) if rs else None,
      "by_year":{str(y):{"n":int(len(g)),"sum_pnl":float(g.addon_slice_pnl.sum()),
                         "mean_return":float(g.addon_slice_return.mean())} for y,g in d.groupby("year")}
    }

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=v13.load(a.indir)
    cs=v22.bottom20(v13.strict_signals(sig,500,cal,idx,nxt,bm))
    df=event_log(cs,cal,bm);df.to_csv(out/"addon_events.csv",index=False)
    event_summary=summarize_events(df)
    normal=v43.run(cs,cal,bm,"EARLY_R250")
    baseline=v43.run(cs,cal,bm,"SKIP_OVERLAP")
    ablated=run_ablate_2025(cs,cal,bm)
    summary={"schema":"PURE-BOX-SIMPLE-CORE-EARLY-R250-FRAGILITY-V45",
             "events":event_summary,
             "portfolio":{"baseline_skip":baseline,"early_r250":normal,"early_r250_no_2025_addons":ablated}}
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
