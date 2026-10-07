#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,math,statistics
from collections import defaultdict
from datetime import date
from pathlib import Path
import pandas as pd

ENTRY_COST=.0005
EXIT_COST=.0005
VAL_START="2023-01-01"
VAL_END="2026-03-31"
THRESHOLDS={
  300:{"small":(0.13149887551263392,3),"large":(0.2831081474441409,7)},
  500:{"small":(0.13255303761158518,3),"large":(0.2832764505119453,7)},
}

def mdd(vals):
    if not vals:return None
    p=vals[0];d=0.0
    for x in vals:
        p=max(p,x)
        if p>0:d=min(d,x/p-1)
    return d

def sharpe(vals):
    if len(vals)<3:return None
    r=[vals[i]/vals[i-1]-1 for i in range(1,len(vals)) if vals[i-1]>0]
    if len(r)<2:return None
    sd=statistics.stdev(r)
    return None if sd==0 else statistics.mean(r)/sd*math.sqrt(252)

def pf(rs):
    w=sum(x for x in rs if x>0);l=-sum(x for x in rs if x<0)
    return w/l if l>0 else (float("inf") if w>0 else None)

def load(indir):
    p=Path(indir)
    bars=pd.concat([pd.read_csv(x) for x in sorted(p.glob("**/bars_*.csv.gz"))],ignore_index=True)
    bars["date"]=bars.date.astype(str);bars["ticker"]=bars.ticker.astype(str)
    bars=bars.sort_values(["ticker","date"]).drop_duplicates(["ticker","date"],keep="last")
    sig=pd.concat([pd.read_csv(x) for x in sorted(p.glob("**/signals_*.csv"))],ignore_index=True)
    sig["signal_date"]=sig.signal_date.astype(str);sig["symbol"]=sig.symbol.astype(str);sig["detected_at"]=sig.detected_at.astype(str)
    spy=bars[bars.ticker=="SPY"].sort_values("date")
    cal=spy.date.tolist();idx={d:i for i,d in enumerate(cal)}
    nxt={cal[i]:cal[i+1] for i in range(len(cal)-1)}
    bm={s:{r["date"]:r for r in g.to_dict("records")} for s,g in bars.groupby("ticker",sort=False)}
    return sig,cal,idx,nxt,bm

def strict_signals(sig,cap,cal,idx,nxt,bm):
    s=sig[sig.liquidity_rank<=cap].copy()
    s["ord"]=s.scale.map({"small":0,"large":1})
    s=s.sort_values(["signal_date","symbol","ord","detected_at"],ascending=[True,True,False,False])
    s=s.drop_duplicates(["signal_date","symbol"],keep="first")
    out=[]
    for q in s.to_dict("records"):
        scale=str(q["scale"])
        if scale not in ("small","large"):continue
        d0=str(q["signal_date"])
        if not (VAL_START<=d0<=VAL_END):continue
        d1=nxt.get(d0)
        b0=bm.get(str(q["symbol"]),{}).get(d0)
        b1=bm.get(str(q["symbol"]),{}).get(d1) if d1 else None
        if b0 is None or b1 is None:continue
        lo=float(q["lower"]);hi=float(q["upper"]);op1=float(b1["open"])
        if not(lo<op1<hi):continue
        age=max(0,idx[d0]-idx.get(str(q["detected_at"]),idx[d0]))
        width=(hi-lo)/op1
        wthr,athr=THRESHOLDS[cap][scale]
        if width<wthr or age>athr:continue
        out.append({**q,"scale":scale,"lower":lo,"upper":hi,"box_age_sessions":age,
                    "box_width_pct":width,"direct_entry_date":d1,"direct_entry_price":op1,
                    "signal_low":float(b0["low"])})
    return out

def with_confirmation(cands,nxt,bm):
    out=[]
    for c in cands:
        d0=str(c["signal_date"]);d1=nxt.get(d0);d2=nxt.get(d1) if d1 else None
        if not d1 or not d2:continue
        sm=bm.get(str(c["symbol"]),{})
        b0=sm.get(d0);b1=sm.get(d1);b2=sm.get(d2)
        if b0 is None or b1 is None or b2 is None:continue
        if float(b1["low"])<float(b0["low"]):continue
        if float(b1["close"])<=float(b1["open"]):continue
        op2=float(b2["open"]);lo=float(c["lower"]);hi=float(c["upper"])
        if not(lo<op2<hi):continue
        out.append({**c,"confirm_entry_date":d2,"confirm_entry_price":op2})
    return out

def run(cands,calendar,bm,entry_mode,target_frac,max_hold,alloc_mode):
    cidx={d:i for i,d in enumerate(calendar)}
    byday=defaultdict(list)
    edate="direct_entry_date" if entry_mode=="direct" else "confirm_entry_date"
    eprice="direct_entry_price" if entry_mode=="direct" else "confirm_entry_price"
    for c in cands:
        d=str(c[edate])
        if VAL_START<=d<=VAL_END and d in cidx:byday[d].append(c)

    days=[d for d in calendar if VAL_START<=d<=VAL_END]
    cash=1.0;pos={};eq=[];expo=[];tr=[]
    for d in days:
        # gap exits
        for sym in list(pos):
            b=bm.get(sym,{}).get(d)
            if b is None:continue
            p=pos[sym];op=float(b["open"]);px=None;reason=None
            if op<=p["lower"]:px=op;reason="stop_gap"
            elif op>=p["target"]:px=op;reason="target_gap"
            if px is not None:
                proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                tr.append(proceeds/p["cost_basis"]-1);del pos[sym]

        cand=[c for c in byday.get(d,[]) if str(c["symbol"]) not in pos]
        cand.sort(key=lambda x:(str(x["symbol"]),str(x["signal_date"])))
        ded=[];seen=set()
        for c in cand:
            sym=str(c["symbol"])
            if sym in seen:continue
            seen.add(sym);ded.append(c)
        cand=ded

        eqo=cash
        for sym,p in pos.items():
            b=bm.get(sym,{}).get(d);eqo+=p["shares"]*(float(b["open"]) if b is not None else p["last"])

        valid=[]
        for c in cand:
            sym=str(c["symbol"]);b=bm.get(sym,{}).get(d)
            if b is None:continue
            op=float(b["open"]);lo=float(c["lower"]);hi=float(c["upper"])
            target=hi if target_frac>=.999999 else lo+target_frac*(hi-lo)
            if not(lo<op<target):continue
            valid.append((c,op,lo,hi,target))

        if valid:
            req=[]
            for c,op,lo,hi,target in valid:
                if alloc_mode=="old":
                    req.append((0.5 if c["scale"]=="small" else 1.0)*eqo)
                else:
                    req.append(0.20*eqo)
            budget=min(cash,sum(req));sc=budget/sum(req) if req else 0.0
            for (c,op,lo,hi,target),rq in zip(valid,req):
                amt=rq*sc
                if amt<=1e-12 or amt>cash+1e-10:continue
                invest=amt*(1-ENTRY_COST);cash-=amt
                sym=str(c["symbol"])
                pos[sym]={"shares":invest/op,"cost_basis":amt,"entry_i":cidx[d],
                          "lower":lo,"upper":hi,"target":target,"last":op}

        # same day and carried intraday
        for sym in list(pos):
            p=pos[sym];b=bm.get(sym,{}).get(d);hold=cidx[d]-p["entry_i"]+1
            if b is None:
                if max_hold is not None and hold>=max_hold:
                    px=p["last"];proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                    tr.append(proceeds/p["cost_basis"]-1);del pos[sym]
                continue
            lo=float(b["low"]);hi=float(b["high"]);cl=float(b["close"]);px=None
            if lo<=p["lower"]:px=p["lower"]
            elif hi>=p["target"]:px=p["target"]
            elif max_hold is not None and hold>=max_hold:px=cl
            if px is not None:
                proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                tr.append(proceeds/p["cost_basis"]-1);del pos[sym]
            else:p["last"]=cl

        val=cash;inv=0.0
        for sym,p in pos.items():
            b=bm.get(sym,{}).get(d);px=float(b["close"]) if b is not None else p["last"];p["last"]=px
            v=p["shares"]*px;val+=v;inv+=v
        eq.append((d,val));expo.append(inv/val if val>0 else 0.0)

    vals=[x[1] for x in eq];rs=[float(x) for x in tr]
    yrs=max((date.fromisoformat(days[-1])-date.fromisoformat(days[0])).days/365.2425,1/365)
    return {
      "total_return":vals[-1]/vals[0]-1,
      "cagr":(vals[-1]/vals[0])**(1/yrs)-1,
      "max_drawdown":mdd(vals),"daily_sharpe":sharpe(vals),
      "avg_exposure":statistics.mean(expo) if expo else 0.0,
      "completed_trades":len(tr),"open_positions_at_end":len(pos),
      "profit_factor":pf(rs),"mean_trade":statistics.mean(rs) if rs else None,
      "win_rate":sum(x>0 for x in rs)/len(rs) if rs else None
    }

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=load(a.indir)
    rows=[];summary={"schema":"PURE-BOX-CORE-GEOMETRY-SIMPLICITY-V13","window":[VAL_START,VAL_END],"results":{}}
    lane_defs=[
      ("OLD_EXACT","direct",1.0,None,"old"),
      ("DIRECT_20_FULL_NOTIME","direct",1.0,None,"fixed"),
      ("DIRECT_20_FULL_H20","direct",1.0,20,"fixed"),
      ("CONFIRM_20_FULL_H20","confirm",1.0,20,"fixed"),
      ("DIRECT_20_T60_H20","direct",0.60,20,"fixed"),
      ("CONFIRM_20_T60_H20","confirm",0.60,20,"fixed"),
    ]
    for cap in (300,500):
        ds=strict_signals(sig,cap,cal,idx,nxt,bm)
        cs=with_confirmation(ds,nxt,bm)
        for name,entry,target,h,amode in lane_defs:
            q=ds if entry=="direct" else cs
            r=run(q,cal,bm,entry,target,h,amode)
            key=f"top{cap}__{name}"
            summary["results"][key]={**r,"candidate_n":len(q),"entry_mode":entry,"target_fraction":target,
                                     "max_hold":h,"alloc_mode":amode}
            rows.append({"rank_cap":cap,"lane":name,**summary["results"][key]})
    pd.DataFrame(rows).to_csv(out/"results.csv",index=False)
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
