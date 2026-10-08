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
CAP=.50; H=15

def mdd(vals):
    p=vals[0];d=0.0
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

def build_regimes(calendar,bm):
    spy=[]
    for d in calendar:
        b=bm.get("SPY",{}).get(d)
        if b is not None:spy.append((d,float(b["close"])))
    s=pd.Series({d:c for d,c in spy}).sort_index()
    r=s.pct_change()
    ma50=s.rolling(50,min_periods=50).mean()
    ma200=s.rolling(200,min_periods=200).mean()
    rv20=r.rolling(20,min_periods=20).std()*math.sqrt(252)
    regs={}
    vals=[]
    dates=list(s.index)
    for i,d in enumerate(dates):
        if i<200:continue
        prev=dates[i-1]
        pc=float(s.loc[prev]);m50=float(ma50.loc[prev]);m200=float(ma200.loc[prev]);rv=float(rv20.loc[prev])
        hist=rv20.loc[:prev].dropna()
        q70=float(hist.quantile(.70)) if len(hist) else float("nan")
        if pc>m200 and m50>m200:trend="UP"
        elif pc<m200 and m50<m200:trend="DOWN"
        else:trend="TRANSITION"
        vol="HIGH" if pd.notna(q70) and rv>q70 else "LOW"
        regs[d]=f"{trend}_{vol}"
    return regs

def risk_spec(policy,reg):
    if policy=="CONSTANT":return .0125,.025
    trend,vol=reg.rsplit("_",1)
    if policy=="DEFENSIVE_DOWN":
        if trend=="DOWN":return .0075,.015
        if trend=="TRANSITION":return .010,.020
        return .0125,.025
    if policy=="VOLATILITY_AWARE":
        return (.009,.018) if vol=="HIGH" else (.0125,.025)
    if policy=="UP_AGGRESSIVE":
        return (.015,.030) if reg=="UP_LOW" else (.010,.020)
    if policy=="ASYMMETRIC":
        return {
          "UP_LOW":(.015,.030),"UP_HIGH":(.0125,.025),
          "TRANSITION_LOW":(.011,.022),"TRANSITION_HIGH":(.009,.018),
          "DOWN_LOW":(.009,.018),"DOWN_HIGH":(.0075,.015)
        }[reg]
    raise ValueError(policy)

def run(cands,calendar,bm,regs,policy):
    cidx={d:i for i,d in enumerate(calendar)}
    by=defaultdict(list)
    for c in cands:
        d=str(c["direct_entry_date"])
        if v13.VAL_START<=d<=v13.VAL_END and d in cidx:by[d].append(c)
    days=[d for d in calendar if v13.VAL_START<=d<=v13.VAL_END]
    cash=1.;pos={};eq=[];expo=[];trs=[];trade_reg=[];addon_rows=[]
    blocked=partial=0
    regime_days=defaultdict(int)
    for d in days:
        reg=regs.get(d,"TRANSITION_LOW");regime_days[reg]+=1
        for s in list(pos):
            b=bm.get(s,{}).get(d)
            if b is None:continue
            p=pos[s];p["hold"]+=1;o=float(b["open"]);px=None
            if o<=p["lower"]:px=o
            elif o>=p["target"]:px=o
            if px is not None:
                proceeds=p["shares"]*px*(1-XC);cash+=proceeds
                rr=proceeds/p["cost_basis"]-1;trs.append(rr);trade_reg.append((p["entry_regime"],rr))
                for a in p.get("addon_ids",[]):addon_rows[a]["ret"]=px*(1-XC)/(addon_rows[a]["entry"]*(1+EC))-1
                del pos[s]
        eqo=cash;openval={}
        for s,p in pos.items():
            b=bm.get(s,{}).get(d);op=float(b["open"]) if b is not None else p["last"]
            v=p["shares"]*op;openval[s]=v;eqo+=v
        init_r,addon_ceiling=risk_spec(policy,reg)
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
            riskpd=1-(lo*(1-XC))/(op*(1+EC))
            if riskpd<=0:continue
            if s in pos:
                p=pos[s]
                if int(p["hold"])>3:continue
                curr=max(0.,p["shares"]*(op-p["lower"]*(1-XC)))
                add=max(0.,addon_ceiling*eqo-curr)
                head=max(0.,CAP*eqo-openval.get(s,0.))
                req=min(add/riskpd,head)
                if req<=1e-12:continue
                acts.append({"kind":"addon","symbol":s,"liquidity_rank":int(c["liquidity_rank"]),"entry_fraction":ef,
                             "request":req,"entry_price":op,"lower":lo,"target":target,"risk_per_dollar":riskpd,"regime":reg})
            else:
                req=min(init_r*eqo/riskpd,CAP*eqo)
                acts.append({"kind":"new","symbol":s,"liquidity_rank":int(c["liquidity_rank"]),"entry_fraction":ef,
                             "request":req,"entry_price":op,"lower":lo,"target":target,"risk_per_dollar":riskpd,"regime":reg})
        acts.sort(key=lambda x:(x["liquidity_rank"],x["entry_fraction"],x["symbol"],0 if x["kind"]=="new" else 1))
        rem=cash
        for a in acts:
            amt=min(a["request"],rem) if rem>0 else 0.;rem-=amt
            if amt<=1e-12:
                if a["kind"]=="new":blocked+=1
                continue
            if a["kind"]=="new" and amt+1e-12<a["request"]:partial+=1
            inv=amt*(1-EC);cash-=amt
            if a["kind"]=="new":
                pos[a["symbol"]]={**a,"shares":inv/a["entry_price"],"cost_basis":amt,"hold":1,"last":a["entry_price"],
                                  "entry_regime":reg,"addon_ids":[]}
            else:
                p=pos[a["symbol"]];p["shares"]+=inv/a["entry_price"];p["cost_basis"]+=amt
                addon_rows.append({"symbol":a["symbol"],"regime":reg,"capital":amt,"entry":a["entry_price"],"ret":None})
                p["addon_ids"].append(len(addon_rows)-1)
        for s in list(pos):
            p=pos[s];b=bm.get(s,{}).get(d)
            if b is None:continue
            lo=float(b["low"]);hi=float(b["high"]);cl=float(b["close"]);px=None
            if lo<=p["lower"]:px=p["lower"]
            elif hi>=p["target"]:px=p["target"]
            elif p["hold"]>=H:px=cl
            if px is not None:
                proceeds=p["shares"]*px*(1-XC);cash+=proceeds
                rr=proceeds/p["cost_basis"]-1;trs.append(rr);trade_reg.append((p["entry_regime"],rr))
                for a in p.get("addon_ids",[]):addon_rows[a]["ret"]=px*(1-XC)/(addon_rows[a]["entry"]*(1+EC))-1
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
    trdf=pd.DataFrame(trade_reg,columns=["regime","ret"]) if trade_reg else pd.DataFrame(columns=["regime","ret"])
    adf=pd.DataFrame(addon_rows)
    regstats={}
    for rg,g in trdf.groupby("regime"):
        rs=g.ret.tolist();regstats[rg]={"n":len(rs),"mean_trade":float(g.ret.mean()),"profit_factor":pf(rs)}
    addstats={}
    if len(adf):
        done=adf.dropna(subset=["ret"])
        for rg,g in done.groupby("regime"):
            rs=g.ret.tolist();addstats[rg]={"n":len(rs),"mean_addon_return":float(g.ret.mean()),"profit_factor":pf(rs),
                                          "sum_pnl":float((g.capital*g.ret).sum())}
    return {
      "total_return":vals[-1]/vals[0]-1,"cagr":(vals[-1]/vals[0])**(1/yrs)-1,
      "max_drawdown":mdd(vals),"daily_sharpe":sharpe(vals),"avg_exposure":statistics.mean(expo),
      "completed_trades":len(trs),"profit_factor":pf(trs),"blocked_new_entries":blocked,"partial_new_entries":partial,
      "add_on_events":int(len(adf)),"add_on_capital":float(adf.capital.sum()) if len(adf) else 0.,
      "yearly_return":{y:float(g.equity.iloc[-1]/g.equity.iloc[0]-1) for y,g in edf.groupby("year")},
      "rolling_12m_min_return":min(roll) if roll else None,
      "rolling_12m_positive_share":sum(x>0 for x in roll)/len(roll) if roll else None,
      "rolling_12m_median_return":statistics.median(roll) if roll else None,
      "regime_trade_stats":regstats,"regime_addon_stats":addstats,"regime_days":dict(regime_days)
    }

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=v13.load(a.indir)
    regs=build_regimes(cal,bm)
    policies=("CONSTANT","DEFENSIVE_DOWN","VOLATILITY_AWARE","UP_AGGRESSIVE","ASYMMETRIC")
    rows=[];summary={"schema":"PURE-BOX-SIMPLE-CORE-REGIME-CAPITAL-INTENSITY-V45","results":{}}
    for cap in (300,500):
        cs=v22.bottom20(v13.strict_signals(sig,cap,cal,idx,nxt,bm))
        for p in policies:
            r=run(cs,cal,bm,regs,p);summary["results"][f"top{cap}__{p}"]=r;rows.append({"rank_cap":cap,"policy":p,**r})
    pd.DataFrame(rows).to_csv(out/"results.csv",index=False)
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(pd.DataFrame(rows)[["rank_cap","policy","total_return","cagr","max_drawdown","daily_sharpe","rolling_12m_min_return","add_on_events"]].to_string(index=False))
if __name__=="__main__":main()
