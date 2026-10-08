#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,statistics
from pathlib import Path
from collections import defaultdict
import pandas as pd
import research_pure_box_core_geometry_simplicity_v13 as v13
import research_pure_box_capital_architecture_v22 as v22

BUCKETS=[(1,5),(6,10),(11,15),(16,20)]

def path_rows(cands,cal,bm):
    cidx={d:i for i,d in enumerate(cal)}
    out=[]
    for c in cands:
        d=str(c["direct_entry_date"]);s=str(c["symbol"])
        if d not in cidx: continue
        lo=float(c["lower"]);hi=float(c["upper"]);op=float(c["direct_entry_price"]);target=lo+.60*(hi-lo)
        start=cidx[d]; prev=op; alive=True; exit_day=None; exit_reason=None
        for age in range(1,21):
            if start+age-1>=len(cal): break
            day=cal[start+age-1]; b=bm.get(s,{}).get(day)
            if b is None: continue
            px=float(b["close"]); reason=None
            if float(b["open"])<=lo: px=float(b["open"]);reason="stop_gap"
            elif float(b["open"])>=target: px=float(b["open"]);reason="target_gap"
            elif float(b["low"])<=lo: px=lo;reason="stop"
            elif float(b["high"])>=target: px=target;reason="target60"
            elif age>=20: reason="time_h20"
            inc=px/prev-1
            out.append({"cap":c["cap"],"symbol":s,"signal_date":c["signal_date"],"entry_date":d,
                        "year":d[:4],"age":age,"incremental_return":inc,
                        "cum_return":px/op-1,"alive_start":alive,"exit_reason":reason or "",
                        "capital_day":1})
            prev=px
            if reason:
                exit_day=age;exit_reason=reason;alive=False;break
    return pd.DataFrame(out)

def summarize(df,cap):
    z=df[df.cap==cap].copy();res={"rank_cap":cap,"buckets":{}}
    for a,b in BUCKETS:
        g=z[(z.age>=a)&(z.age<=b)]
        starts=z[z.age==a]
        eligible=set(zip(starts.symbol,starts.entry_date))
        h=g[g.apply(lambda r:(r.symbol,r.entry_date) in eligible,axis=1)] if len(g) else g
        vals=h.incremental_return.tolist()
        res["buckets"][f"d{a}_{b}"]={
          "trade_paths_entering_bucket":len(eligible),
          "alive_fraction_vs_entries":len(eligible)/max(1,z[z.age==1][["symbol","entry_date"]].drop_duplicates().shape[0]),
          "incremental_return_sum":float(h.incremental_return.sum()) if len(h) else 0.0,
          "incremental_return_mean":float(h.incremental_return.mean()) if len(h) else None,
          "positive_increment_share":float((h.incremental_return>0).mean()) if len(h) else None,
          "capital_days":int(h.capital_day.sum()) if len(h) else 0,
          "return_per_capital_day":float(h.incremental_return.sum()/h.capital_day.sum()) if len(h) and h.capital_day.sum() else None,
          "boundary_cum_mean":float(z[z.age==b].cum_return.mean()) if len(z[z.age==b]) else None,
          "boundary_cum_median":float(z[z.age==b].cum_return.median()) if len(z[z.age==b]) else None,
          "exits":h[h.exit_reason!=""].exit_reason.value_counts().to_dict()
        }
    # forced H15 cohort: trades alive through day15, inspect days16-20 contribution
    keys=set(zip(z[z.age==15].symbol,z[z.age==15].entry_date))
    tail=z[(z.age>=16)&(z.age<=20)&z.apply(lambda r:(r.symbol,r.entry_date) in keys,axis=1)]
    res["h15_survivor_tail"]={
      "cohort_n":len(keys),
      "d16_20_incremental_sum":float(tail.incremental_return.sum()) if len(tail) else 0.0,
      "d16_20_incremental_mean_per_capital_day":float(tail.incremental_return.mean()) if len(tail) else None,
      "positive_increment_share":float((tail.incremental_return>0).mean()) if len(tail) else None,
      "capital_days":int(len(tail))
    }
    yearly={}
    for y,gy in z.groupby("year"):
        yearly[y]={}
        for a,b in BUCKETS:
            h=gy[(gy.age>=a)&(gy.age<=b)]
            yearly[y][f"d{a}_{b}"]={"sum":float(h.incremental_return.sum()),"capital_days":int(len(h)),
                                     "per_capital_day":float(h.incremental_return.mean()) if len(h) else None}
    res["yearly"]=yearly
    return res

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=v13.load(a.indir)
    allc=[]
    for cap in (300,500):
        cs=v22.bottom20(v13.strict_signals(sig,cap,cal,idx,nxt,bm))
        for c in cs:c["cap"]=cap
        allc+=cs
    df=path_rows(allc,cal,bm)
    df.to_csv(out/"path_rows.csv",index=False)
    summary={"schema":"PURE-BOX-SIMPLE-CORE-HOLD-TIME-ANATOMY-V24",
             "results":{f"top{cap}":summarize(df,cap) for cap in (300,500)}}
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
