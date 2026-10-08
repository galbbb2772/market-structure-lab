#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,statistics,math
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

def run_early_events(cands,calendar,bm):
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
                if int(p["hold"])>3:continue
                curr_risk=max(0.,p["shares"]*(op-lo*(1-XC)))
                add_risk=max(0.,TARGET_RISK*eqo-curr_risk)
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
            amt=min(a["request"],rem) if rem>0 else 0.;rem-=amt
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
                  "existing_age":a["existing_age"],"entry_fraction":a["entry_fraction"],
                  "risk_before":a["risk_before"],"risk_after":risk_after,
                  "addon_funded_capital":amt,"addon_entry_price":a["entry_price"],
                  "cap_constrained":a["cap_constrained"],
                  "cash_constrained":bool(amt+1e-12<a["request"]),
                  "exit_date":None,"exit_reason":None,
                  "addon_slice_return":None,"addon_slice_pnl":None
                }
                events.append(ev);p["addon_event_ids"].append(eid);eid+=1

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

def compound_years(yr,omit=None):
    w=1.0
    for y in sorted(yr):
        if y==omit:continue
        w*=1+float(yr[y])
    return w-1

def event_stats(df):
    d=df.dropna(subset=["addon_slice_return"]).copy()
    rs=d.addon_slice_return.tolist()
    bysym=d.groupby("symbol").addon_slice_pnl.sum() if len(d) else pd.Series(dtype=float)
    absb=bysym.abs().sort_values(ascending=False)
    totalabs=float(absb.sum()) if len(absb) else 0.
    top_symbols=list(absb.index)
    def excl(k):
        if not len(d):return None
        rem=d[~d.symbol.isin(top_symbols[:k])]
        return float(rem.addon_slice_pnl.sum())
    return {
      "n":int(len(d)),
      "funded_capital":float(d.addon_funded_capital.sum()) if len(d) else 0.,
      "mean_return":float(d.addon_slice_return.mean()) if len(d) else None,
      "median_return":float(d.addon_slice_return.median()) if len(d) else None,
      "profit_factor":pf(rs) if rs else None,
      "win_rate":float((d.addon_slice_return>0).mean()) if len(d) else None,
      "sum_slice_pnl":float(d.addon_slice_pnl.sum()) if len(d) else 0.,
      "unique_symbols":int(d.symbol.nunique()) if len(d) else 0,
      "top1_abs_share":float(absb.head(1).sum()/totalabs) if totalabs else None,
      "top3_abs_share":float(absb.head(3).sum()/totalabs) if totalabs else None,
      "top5_abs_share":float(absb.head(5).sum()/totalabs) if totalabs else None,
      "top10_abs_share":float(absb.head(10).sum()/totalabs) if totalabs else None,
      "top_symbol":str(top_symbols[0]) if top_symbols else None,
      "top_symbol_signed_pnl":float(bysym.loc[top_symbols[0]]) if top_symbols else None,
      "leave_top1_symbol_out_sum_pnl":excl(1),
      "leave_top3_symbols_out_sum_pnl":excl(3)
    }

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

    # Exact annual portfolio blocks from V43.
    src=json.load(open("research/pure_box_liquid_leaders_v1/early_resignal_pyramiding_v43/summary.json"))
    policies=("SKIP_OVERLAP","FULL_R250","EARLY_R250")
    block={}
    for cap in (300,500):
        block[f"top{cap}"]={}
        for p in policies:
            row=src["results"][f"top{cap}__5bps__{p}"]
            yr=row["yearly_return"]
            block[f"top{cap}"][p]={
              "all_block_compound":compound_years(yr),
              "ex_2025_block_compound":compound_years(yr,"2025"),
              "leave_one_year_out":{y:compound_years(yr,y) for y in yr}
            }

    sig,cal,idx,nxt,bm=v13.load(a.indir)
    events={};frames=[]
    for cap in (300,500):
        cs=v22.bottom20(v13.strict_signals(sig,cap,cal,idx,nxt,bm))
        df=run_early_events(cs,cal,bm);df["rank_cap"]=cap;frames.append(df)
        ex=df[df.year!="2025"] if len(df) else df
        events[f"top{cap}"]={"overall":event_stats(df),"ex_2025":event_stats(ex)}

    all_df=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()
    all_df.to_csv(out/"early_r250_addon_events.csv",index=False)
    summary={"schema":"PURE-BOX-SIMPLE-CORE-EARLY-R250-FRAGILITY-V44","block_compounding":block,"addon_events":events}
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
