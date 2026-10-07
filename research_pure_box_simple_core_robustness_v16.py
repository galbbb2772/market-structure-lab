#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd
import research_pure_box_core_geometry_simplicity_v13 as core

TARGET=.60
MAX_HOLD=20
SEED=20261007
BOOT=5000

def pf(x):
    x=np.asarray(x,float)
    w=x[x>0].sum();l=-x[x<0].sum()
    return float(w/l) if l>0 else (float("inf") if w>0 else None)

def candidates(sig,cap,cal,idx,nxt,bm):
    base=core.strict_signals(sig,cap,cal,idx,nxt,bm)
    out=[]
    for c in base:
        width=float(c["upper"])-float(c["lower"])
        if width<=0:continue
        ef=(float(c["direct_entry_price"])-float(c["lower"]))/width
        if ef<=.20:
            out.append({**c,"entry_fraction":ef})
    return out

def outcome(c,cal,idx,bm):
    entry=str(c["direct_entry_date"]);ei=idx.get(entry)
    if ei is None:return None
    sm=bm.get(str(c["symbol"]),{})
    lo=float(c["lower"]);hi=float(c["upper"])
    target=lo+TARGET*(hi-lo)
    op=float(c["direct_entry_price"])
    if not(lo<op<target):return None
    last=op
    for k in range(MAX_HOLD):
        j=ei+k
        if j>=len(cal):break
        d=cal[j];b=sm.get(d)
        if b is None:
            if k==MAX_HOLD-1:
                px=last
                gross=(1-core.ENTRY_COST)*(px/op)*(1-core.EXIT_COST)-1
                return {**c,"exit_date":d,"exit_reason":"max_hold_stale","net_return":gross}
            continue
        o=float(b["open"]);low=float(b["low"]);high=float(b["high"]);cl=float(b["close"]);last=cl
        if o<=lo:px=o;reason="stop_gap"
        elif o>=target:px=o;reason="target_gap"
        elif low<=lo:px=lo;reason="stop"
        elif high>=target:px=target;reason="target"
        elif k==MAX_HOLD-1:px=cl;reason="max_hold"
        else:continue
        gross=(1-core.ENTRY_COST)*(px/op)*(1-core.EXIT_COST)-1
        return {**c,"exit_date":d,"exit_reason":reason,"net_return":gross}
    return None

def metrics(df):
    r=df.net_return.astype(float)
    if len(r)==0:return {}
    ql,qh=r.quantile([.025,.975])
    wr=r.clip(ql,qh)
    sym=df.groupby("symbol").net_return.mean()
    years=sorted(df.year.unique())
    loo={}
    for y in years:
        z=df[df.year!=y].net_return
        loo[str(int(y))]=float(z.mean()) if len(z) else None
    bysym={s:g.net_return.to_numpy(float) for s,g in df.groupby("symbol")}
    syms=list(bysym)
    rng=np.random.default_rng(SEED)
    boots=[]
    for _ in range(BOOT):
        pick=rng.choice(syms,size=len(syms),replace=True)
        vals=np.concatenate([bysym[s] for s in pick])
        boots.append(float(vals.mean()))
    gross_by_sym=df.groupby("symbol").net_return.sum().abs().sort_values(ascending=False)
    top5=float(gross_by_sym.head(5).sum()/gross_by_sym.sum()) if gross_by_sym.sum()>0 else None
    return {
      "n":int(len(df)),"mean_trade":float(r.mean()),"profit_factor":pf(r),
      "win_rate":float((r>0).mean()),"winsor_mean":float(wr.mean()),
      "symbol_balanced_mean":float(sym.mean()),"symbols":int(sym.size),
      "leave_one_year_out":loo,
      "min_leave_one_year_out":float(min(v for v in loo.values() if v is not None)),
      "bootstrap_p_mean_gt_0":float(np.mean(np.asarray(boots)>0)),
      "bootstrap_q05":float(np.quantile(boots,.05)),
      "bootstrap_q50":float(np.quantile(boots,.50)),
      "bootstrap_q95":float(np.quantile(boots,.95)),
      "top5_symbol_abs_pnl_share":top5,
    }

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=core.load(a.indir)
    summary={"schema":"PURE-BOX-SIMPLE-CORE-ROBUSTNESS-V16","results":{}}
    annual=[]
    for cap in (300,500):
        cs=candidates(sig,cap,cal,idx,nxt,bm)
        ev=[]
        for c in cs:
            r=outcome(c,cal,idx,bm)
            if r is not None:
                r["year"]=int(str(r["direct_entry_date"])[:4]);ev.append(r)
        df=pd.DataFrame(ev)
        m=metrics(df)
        # portfolio reference
        pr=core.run(cs,cal,bm,"direct",.60,20,"fixed")
        m["portfolio_reference"]={k:v for k,v in pr.items()}
        summary["results"][f"top{cap}"]=m
        for y,g in df.groupby("year"):
            annual.append({"rank_cap":cap,"year":int(y),"n":int(len(g)),
                           "mean_trade":float(g.net_return.mean()),"profit_factor":pf(g.net_return),
                           "win_rate":float((g.net_return>0).mean())})
        df.to_csv(out/f"events_top{cap}.csv.gz",index=False,compression="gzip")
    pd.DataFrame(annual).to_csv(out/"annual.csv",index=False)
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
