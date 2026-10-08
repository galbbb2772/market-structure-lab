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

def progress_bucket(x):
    if x<0:return "P0_NEG"
    if x<.25:return "P1_0_25"
    if x<.50:return "P2_25_50"
    return "P3_50_PLUS"

def stats(g):
    d=g.dropna(subset=["addon_slice_return"]).copy()
    rs=d.addon_slice_return.tolist()
    return {
      "n":int(len(d)),
      "funded_capital":float(d.addon_funded_capital.sum()) if len(d) else 0.0,
      "mean_return":float(d.addon_slice_return.mean()) if len(d) else None,
      "median_return":float(d.addon_slice_return.median()) if len(d) else None,
      "profit_factor":pf(rs) if rs else None,
      "win_rate":float((d.addon_slice_return>0).mean()) if len(d) else None,
      "sum_slice_pnl":float(d.addon_slice_pnl.sum()) if len(d) else 0.0,
      "unique_symbols":int(d.symbol.nunique()) if len(d) else 0
    }

def run(cands,calendar,bm):
    cidx={d:i for i,d in enumerate(calendar)}
    by=defaultdict(list)
    for c in cands:
        d=str(c["direct_entry_date"])
        if v13.VAL_START<=d<=v13.VAL_END and d in cidx:by[d].append(c)
    days=[d for d in calendar if v13.VAL_START<=d<=v13.VAL_END]
    cash=1.;pos={};events=[];eid=0
    for d in days:
        di=cidx[d]
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
                    rec=events[e];rec["exit_date"]=d;rec["exit_reason"]=reason
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
                age=int(p["hold"])
                if age>3:continue
                curr_risk=max(0.,p["shares"]*(op-p["lower"]*(1-XC)))
                add_risk=max(0.,TARGET_RISK*eqo-curr_risk)
                if add_risk<=1e-12:continue
                raw_req=add_risk/riskpd
                head=max(0.,CAP*eqo-open_val.get(s,0.))
                req=min(raw_req,head)
                if req<=1e-12:continue

                entry=float(p["entry_price"])
                denom=max(float(p["target"])-entry,1e-12)
                prog=(op-entry)/denom
                prev_day=calendar[di-1] if di>0 else None
                pb=bm.get(s,{}).get(prev_day) if prev_day else None
                prior_close=float(pb["close"]) if pb is not None else None
                prior_open=float(pb["open"]) if pb is not None else None
                stop_dist=(op-float(p["lower"]))/op if op>0 else None
                actions.append({
                  "kind":"addon","symbol":s,"liquidity_rank":int(c["liquidity_rank"]),
                  "entry_fraction":ef,"request":req,"entry_price":op,"lower":lo,"target":target,
                  "existing_age":age,"original_entry":entry,"target_progress":prog,
                  "pnl_state":"POSITIVE" if op>entry else "NEGATIVE_OR_FLAT",
                  "progress_bucket":progress_bucket(prog),
                  "prior_close_state":("ABOVE_ENTRY" if prior_close is not None and prior_close>entry else "AT_OR_BELOW_ENTRY"),
                  "prior_day_direction":("GREEN" if prior_close is not None and prior_open is not None and prior_close>prior_open else "RED_OR_FLAT"),
                  "stop_headroom":stop_dist
                })
            else:
                req=min(RB*eqo/riskpd,CAP*eqo)
                actions.append({
                  "kind":"new","symbol":s,"liquidity_rank":int(c["liquidity_rank"]),
                  "entry_fraction":ef,"request":req,"entry_price":op,"lower":lo,"target":target
                })

        actions.sort(key=lambda x:(x["liquidity_rank"],x["entry_fraction"],x["symbol"],0 if x["kind"]=="new" else 1))
        rem=cash
        for a in actions:
            amt=min(a["request"],rem) if rem>0 else 0.;rem-=amt
            if amt<=1e-12:continue
            invest=amt*(1-EC);cash-=amt
            if a["kind"]=="new":
                pos[a["symbol"]]={**a,"shares":invest/a["entry_price"],"cost_basis":amt,"hold":1,
                                  "last":a["entry_price"],"addon_event_ids":[]}
            else:
                p=pos[a["symbol"]]
                p["shares"]+=invest/a["entry_price"];p["cost_basis"]+=amt
                ev={
                  "event_id":eid,"date":d,"year":d[:4],"symbol":a["symbol"],
                  "existing_age":a["existing_age"],
                  "pnl_state":a["pnl_state"],
                  "target_progress":a["target_progress"],
                  "progress_bucket":a["progress_bucket"],
                  "prior_close_state":a["prior_close_state"],
                  "prior_day_direction":a["prior_day_direction"],
                  "stop_headroom":a["stop_headroom"],
                  "addon_funded_capital":amt,"addon_entry_price":a["entry_price"],
                  "exit_date":None,"exit_reason":None,"addon_slice_return":None,"addon_slice_pnl":None
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
                    rec=events[e];rec["exit_date"]=d;rec["exit_reason"]=reason
                    rec["addon_slice_return"]=px*(1-XC)/(rec["addon_entry_price"]*(1+EC))-1
                    rec["addon_slice_pnl"]=rec["addon_funded_capital"]*rec["addon_slice_return"]
                del pos[s]
            else:p["last"]=cl
    return pd.DataFrame(events)

def summarize(df):
    d=df.dropna(subset=["addon_slice_return"]).copy()
    if len(d):
        med=float(d.stop_headroom.median())
        d["stop_headroom_state"]=d.stop_headroom.map(lambda x:"BELOW_MEDIAN" if x<med else "ABOVE_MEDIAN")
    else:
        med=None;d["stop_headroom_state"]=[]
    out={"overall":stats(d),"stop_headroom_median":med}
    for col in ["pnl_state","progress_bucket","prior_close_state","prior_day_direction","stop_headroom_state","existing_age"]:
        out[col]={str(k):stats(g) for k,g in d.groupby(col)} if len(d) else {}
    out["age_x_pnl"]={f"age{a}__{p}":stats(g) for (a,p),g in d.groupby(["existing_age","pnl_state"])} if len(d) else {}
    out["age_x_progress"]={f"age{a}__{p}":stats(g) for (a,p),g in d.groupby(["existing_age","progress_bucket"])} if len(d) else {}
    out["direction_x_pnl"]={f"{dr}__{p}":stats(g) for (dr,p),g in d.groupby(["prior_day_direction","pnl_state"])} if len(d) else {}
    out["year_split"]={
      "2025":stats(d[d.year=="2025"]) if len(d) else {},
      "ex_2025":stats(d[d.year!="2025"]) if len(d) else {}
    }
    return out,d

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=v13.load(a.indir)
    summary={"schema":"PURE-BOX-SIMPLE-CORE-EARLY-PATH-STATE-ADDON-AUDIT-V46","results":{}}
    frames=[]
    for cap in (300,500):
        cs=v22.bottom20(v13.strict_signals(sig,cap,cal,idx,nxt,bm))
        df=run(cs,cal,bm);s,annot=summarize(df);annot["rank_cap"]=cap;frames.append(annot)
        summary["results"][f"top{cap}"]=s
    pd.concat(frames,ignore_index=True).to_csv(out/"addon_events.csv",index=False)
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
