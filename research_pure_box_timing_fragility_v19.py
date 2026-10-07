#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,statistics
from collections import defaultdict
from pathlib import Path
import pandas as pd
import research_pure_box_core_geometry_simplicity_v13 as v13

VAL_START=v13.VAL_START; VAL_END=v13.VAL_END

def cohort(sig,cap,cal,idx,nxt,bm):
    base=v13.strict_signals(sig,cap,cal,idx,nxt,bm)
    out=[]
    for c in base:
        lo=float(c["lower"]); hi=float(c["upper"]); op0=float(c["direct_entry_price"])
        if hi<=lo: continue
        ef0=(op0-lo)/(hi-lo)
        if ef0>.20: continue
        d0=str(c["direct_entry_date"]); d1=nxt.get(d0)
        sm=bm.get(str(c["symbol"]),{})
        b1=sm.get(d1) if d1 else None
        delayed_valid=False; op1=None; ef1=None
        target=lo+.60*(hi-lo)
        if b1 is not None:
            op1=float(b1["open"]); ef1=(op1-lo)/(hi-lo)
            delayed_valid=(lo<op1<target)
        out.append({**c,"entry_fraction_direct":ef0,"delay_date":d1,"delay_open":op1,
                    "entry_fraction_delay":ef1,"delayed_valid":delayed_valid})
    return out

def trade_return(c,bm,cal_idx,entry_date,entry_price):
    lo=float(c["lower"]); hi=float(c["upper"]); target=lo+.60*(hi-lo)
    sm=bm.get(str(c["symbol"]),{})
    if entry_date not in cal_idx:return None
    ei=cal_idx[entry_date]
    last=entry_price
    dates=sorted(sm)
    # use calendar index and scan symbol rows by date through market calendar
    inv={v:k for k,v in cal_idx.items()}
    exit_px=None; exit_reason=None
    for j in range(ei, min(ei+20, max(inv)+1)):
        d=inv.get(j)
        if d is None:continue
        b=sm.get(d)
        if b is None:continue
        op=float(b["open"]); low=float(b["low"]); high=float(b["high"]); close=float(b["close"])
        if j==ei:
            # entry at open, then intraday stop/target
            pass
        else:
            if op<=lo: exit_px=op; exit_reason="stop_gap"; break
            if op>=target: exit_px=op; exit_reason="target_gap"; break
        if low<=lo: exit_px=lo; exit_reason="stop"; break
        if high>=target: exit_px=target; exit_reason="target"; break
        last=close
        if j-ei+1>=20:
            exit_px=close; exit_reason="time"; break
    if exit_px is None:
        exit_px=last; exit_reason="end"
    ret=(exit_px*(1-v13.EXIT_COST))/(entry_price*(1+v13.ENTRY_COST))-1
    return {"ret":ret,"exit_reason":exit_reason}

def band(x):
    if x is None:return "INVALID"
    if x<=.10:return "LE10"
    if x<=.20:return "10_20"
    if x<=.30:return "20_30"
    return "GT30"

def summarize(rows):
    def s(vals):
        vals=[x for x in vals if x is not None]
        return {"n":len(vals),"mean":statistics.mean(vals) if vals else None,
                "median":statistics.median(vals) if vals else None,
                "min":min(vals) if vals else None,"max":max(vals) if vals else None}
    return s(rows)

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=v13.load(a.indir)
    rows=[]; summary={"schema":"PURE-BOX-TIMING-FRAGILITY-ANATOMY-V19","window":[VAL_START,VAL_END],"results":{}}
    for cap in (300,500):
        cs=cohort(sig,cap,cal,idx,nxt,bm)
        rr=[]
        for c in cs:
            lo=float(c["lower"]);hi=float(c["upper"]);target=lo+.60*(hi-lo)
            op0=float(c["direct_entry_price"])
            stop0=(op0-lo)/op0
            rew0=(target-op0)/op0
            r0=rew0/stop0 if stop0>0 else None
            op1=c["delay_open"]; stop1=rew1=r1=None
            if op1 is not None:
                stop1=(op1-lo)/op1
                rew1=(target-op1)/op1
                r1=rew1/stop1 if stop1>0 else None
            td=trade_return(c,bm,idx,str(c["direct_entry_date"]),op0)
            tl=trade_return(c,bm,idx,str(c["delay_date"]),op1) if c["delayed_valid"] else None
            row={
              "rank_cap":cap,"symbol":str(c["symbol"]),"scale":str(c["scale"]),"signal_date":str(c["signal_date"]),
              "direct_date":str(c["direct_entry_date"]),"delay_date":c["delay_date"],
              "entry_fraction_direct":c["entry_fraction_direct"],"entry_fraction_delay":c["entry_fraction_delay"],
              "entry_fraction_delta":None if c["entry_fraction_delay"] is None else c["entry_fraction_delay"]-c["entry_fraction_direct"],
              "direct_stop_distance":stop0,"delay_stop_distance":stop1,
              "direct_rr":r0,"delay_rr":r1,"rr_delta":None if r1 is None or r0 is None else r1-r0,
              "open_move":None if op1 is None else op1/op0-1,
              "delayed_valid":bool(c["delayed_valid"]),
              "direct_ret":td["ret"] if td else None,"delay_ret":tl["ret"] if tl else None,
              "ret_delta":None if tl is None or td is None else tl["ret"]-td["ret"],
              "direct_exit":td["exit_reason"] if td else None,"delay_exit":tl["exit_reason"] if tl else None,
              "delay_band":band(c["entry_fraction_delay"]),
              "year":str(c["direct_entry_date"])[:4],"month":str(c["direct_entry_date"])[:7]
            }
            rr.append(row);rows.append(row)
        df=pd.DataFrame(rr)
        valid=df[df.delayed_valid==True].copy()
        bstats={}
        for b,g in valid.groupby("delay_band"):
            bstats[b]={
              "n":int(len(g)),"mean_delay_ret":float(g.delay_ret.mean()),"mean_direct_ret":float(g.direct_ret.mean()),
              "mean_ret_delta":float(g.ret_delta.mean()),"mean_delay_rr":float(g.delay_rr.mean()),
              "mean_entry_fraction_delay":float(g.entry_fraction_delay.mean())
            }
        worst_months=(valid.groupby("month").agg(n=("delay_ret","size"),sum_delay_ret=("delay_ret","sum"),mean_delay_ret=("delay_ret","mean"),sum_direct_ret=("direct_ret","sum"))
                      .sort_values("sum_delay_ret").head(5).reset_index().to_dict("records"))
        direct_win_delay_loss=int(((valid.direct_ret>0)&(valid.delay_ret<=0)).sum())
        invalid_count=int((~df.delayed_valid).sum())
        summary["results"][f"top{cap}"]={
          "candidate_n":int(len(df)),"delay_valid_n":int(len(valid)),"delay_invalid_n":invalid_count,
          "delay_valid_share":float(len(valid)/len(df)) if len(df) else None,
          "entry_fraction_direct":summarize(df.entry_fraction_direct.tolist()),
          "entry_fraction_delay":summarize(valid.entry_fraction_delay.tolist()),
          "entry_fraction_delta":summarize(valid.entry_fraction_delta.tolist()),
          "direct_stop_distance":summarize(valid.direct_stop_distance.tolist()),
          "delay_stop_distance":summarize(valid.delay_stop_distance.tolist()),
          "direct_rr":summarize(valid.direct_rr.tolist()),"delay_rr":summarize(valid.delay_rr.tolist()),
          "rr_delta":summarize(valid.rr_delta.tolist()),
          "open_move":summarize(valid.open_move.tolist()),
          "direct_ret":summarize(valid.direct_ret.tolist()),"delay_ret":summarize(valid.delay_ret.tolist()),
          "ret_delta":summarize(valid.ret_delta.tolist()),
          "direct_win_delay_loss_n":direct_win_delay_loss,
          "delay_band_stats":bstats,"worst_delay_months":worst_months
        }
    pd.DataFrame(rows).to_csv(out/"trade_anatomy.csv",index=False)
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
