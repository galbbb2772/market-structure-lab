#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,statistics
from collections import defaultdict
from pathlib import Path
import pandas as pd
import research_pure_box_core_geometry_simplicity_v13 as v13
import research_pure_box_capital_architecture_v22 as v22

EC=v13.ENTRY_COST; XC=v13.EXIT_COST
RB=.0125; CAP=.50; H=15; TARGET_RISK=.025

def pf(rs):
    w=sum(x for x in rs if x>0);l=-sum(x for x in rs if x<0)
    return w/l if l>0 else None

def age_bucket(a):
    if a<=3:return "age01_03"
    if a<=5:return "age04_05"
    if a<=10:return "age06_10"
    return "age11_plus"

def run(cands,calendar,bm):
    cidx={d:i for i,d in enumerate(calendar)}
    by=defaultdict(list)
    for c in cands:
        d=str(c["direct_entry_date"])
        if v13.VAL_START<=d<=v13.VAL_END and d in cidx:by[d].append(c)
    days=[d for d in calendar if v13.VAL_START<=d<=v13.VAL_END]
    cash=1.;pos={};events=[];eid=0
    for d in days:
        # age + gap exits
        for s in list(pos):
            b=bm.get(s,{}).get(d)
            if b is None:continue
            p=pos[s];p["hold"]+=1;o=float(b["open"]);px=None;reason=None
            if o<=p["lower"]:px=o;reason="stop_gap"
            elif o>=p["target"]:px=o;reason="target_gap"
            if px is not None:
                proceeds=p["shares"]*px*(1-XC);cash+=proceeds
                for e in p.get("addon_event_ids",[]):
                    rec=events[e]
                    rec["exit_date"]=d;rec["exit_reason"]=reason
                    rec["addon_slice_return"]=px*(1-XC)/(rec["addon_entry_price"]*(1+EC))-1
                    rec["addon_slice_pnl"]=rec["addon_funded_capital"]*rec["addon_slice_return"]
                del pos[s]

        eqo=cash;open_val={}
        for s,p in pos.items():
            b=bm.get(s,{}).get(d);op=float(b["open"]) if b is not None else p["last"]
            v=p["shares"]*op;open_val[s]=v;eqo+=v

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
                p=pos[s]
                curr_risk=max(0.,p["shares"]*(op-lo*(1-XC)))
                tgt=TARGET_RISK*eqo
                add_risk=max(0.,tgt-curr_risk)
                if add_risk<=1e-12:continue
                raw_req=add_risk/riskpd
                head=max(0.,CAP*eqo-open_val.get(s,0.))
                req=min(raw_req,head)
                if req<=1e-12:continue
                actions.append({
                  "kind":"addon","symbol":s,"liquidity_rank":int(c["liquidity_rank"]),
                  "entry_fraction":ef,"request":req,"raw_request":raw_req,
                  "cap_constrained":bool(raw_req>head+1e-12),
                  "entry_price":op,"lower":lo,"upper":hi,"target":target,
                  "risk_per_dollar":riskpd,"existing_age":int(p["hold"]),
                  "risk_before":curr_risk/eqo if eqo>0 else None
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
            if amt<=1e-12:continue
            invest=amt*(1-EC);cash-=amt
            if a["kind"]=="new":
                pos[a["symbol"]]={**a,"shares":invest/a["entry_price"],"cost_basis":amt,
                                  "hold":1,"last":a["entry_price"],"addon_event_ids":[]}
            else:
                p=pos[a["symbol"]]
                p["shares"]+=invest/a["entry_price"];p["cost_basis"]+=amt
                risk_after=max(0.,p["shares"]*(a["entry_price"]-p["lower"]*(1-XC)))/eqo if eqo>0 else None
                ev={
                  "event_id":eid,"date":d,"year":d[:4],"symbol":a["symbol"],
                  "existing_age":a["existing_age"],"age_bucket":age_bucket(a["existing_age"]),
                  "entry_fraction":a["entry_fraction"],
                  "risk_before":a["risk_before"],"risk_after":risk_after,
                  "addon_funded_capital":amt,
                  "addon_shares":invest/a["entry_price"],
                  "addon_entry_price":a["entry_price"],
                  "cap_constrained":a["cap_constrained"],
                  "cash_constrained":bool(amt+1e-12<a["request"]),
                  "exit_date":None,"exit_reason":None,
                  "addon_slice_return":None,"addon_slice_pnl":None
                }
                events.append(ev);p["addon_event_ids"].append(eid);eid+=1

        # intraday exits
        for s in list(pos):
            p=pos[s];b=bm.get(s,{}).get(d)
            if b is None:continue
            lo=float(b["low"]);hi=float(b["high"]);cl=float(b["close"]);px=None;reason=None
            if lo<=p["lower"]:px=p["lower"];reason="stop"
            elif hi>=p["target"]:px=p["target"];reason="target60"
            elif p["hold"]>=H:px=cl;reason="time_h15"
            if px is not None:
                proceeds=p["shares"]*px*(1-XC);cash+=proceeds
                for e in p.get("addon_event_ids",[]):
                    rec=events[e]
                    rec["exit_date"]=d;rec["exit_reason"]=reason
                    rec["addon_slice_return"]=px*(1-XC)/(rec["addon_entry_price"]*(1+EC))-1
                    rec["addon_slice_pnl"]=rec["addon_funded_capital"]*rec["addon_slice_return"]
                del pos[s]
            else:p["last"]=cl
    return pd.DataFrame(events)

def stats(g):
    g=g.dropna(subset=["addon_slice_return"])
    rs=g.addon_slice_return.tolist()
    pnl=g.addon_slice_pnl.tolist() if len(g) else []
    return {
      "n":int(len(g)),
      "funded_capital":float(g.addon_funded_capital.sum()) if len(g) else 0.0,
      "mean_return":float(statistics.mean(rs)) if rs else None,
      "median_return":float(statistics.median(rs)) if rs else None,
      "profit_factor":pf(rs) if rs else None,
      "win_rate":float(sum(x>0 for x in rs)/len(rs)) if rs else None,
      "sum_slice_pnl":float(sum(pnl)) if pnl else 0.0,
      "mean_risk_before":float(g.risk_before.mean()) if len(g) else None,
      "mean_risk_after":float(g.risk_after.mean()) if len(g) else None,
      "cap_constrained_share":float(g.cap_constrained.mean()) if len(g) else None,
      "cash_constrained_share":float(g.cash_constrained.mean()) if len(g) else None,
    }

def summarize(df):
    done=df.dropna(subset=["addon_slice_return"]).copy()
    if len(done):
        try:
            done["entry_fraction_quartile"]=pd.qcut(done.entry_fraction,4,labels=["Q1","Q2","Q3","Q4"],duplicates="drop")
        except Exception:
            done["entry_fraction_quartile"]="NA"
    by_year={str(y):stats(g) for y,g in done.groupby("year")} if len(done) else {}
    by_age={str(a):stats(g) for a,g in done.groupby("age_bucket")} if len(done) else {}
    by_q={str(q):stats(g) for q,g in done.groupby("entry_fraction_quartile",observed=True)} if len(done) else {}
    ex=done[done.year!="2025"] if len(done) else done
    bysym=done.groupby("symbol").addon_slice_pnl.sum().abs().sort_values(ascending=False) if len(done) else pd.Series(dtype=float)
    tot=float(bysym.sum()) if len(bysym) else 0.
    return {
      "overall":stats(done),
      "ex_2025":stats(ex),
      "by_year":by_year,
      "by_age_bucket":by_age,
      "by_entry_fraction_quartile":by_q,
      "top5_abs_addon_pnl_share":float(bysym.head(5).sum()/tot) if tot else None,
      "top10_abs_addon_pnl_share":float(bysym.head(10).sum()/tot) if tot else None,
      "unique_symbols":int(done.symbol.nunique()) if len(done) else 0
    }

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=v13.load(a.indir)
    summary={"schema":"PURE-BOX-SIMPLE-CORE-RESIGNAL-PYRAMIDING-ANATOMY-V42","results":{}}
    frames=[]
    for cap in (300,500):
        cs=v22.bottom20(v13.strict_signals(sig,cap,cal,idx,nxt,bm))
        df=run(cs,cal,bm);df["rank_cap"]=cap;frames.append(df)
        summary["results"][f"top{cap}"]=summarize(df)
    all_df=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()
    all_df.to_csv(out/"addon_events.csv",index=False)
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
