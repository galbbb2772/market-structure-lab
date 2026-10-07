#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math, statistics
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd

ENTRY_COST=.0005
EXIT_COST=.0005
ALLOC=.10
MAX_HOLD=20
TARGETS={"60":.60,"80":.80}
FRESH={300:23,500:24}

def pf(rs):
    w=sum(x for x in rs if x>0); l=-sum(x for x in rs if x<0)
    return w/l if l>0 else None
def mdd(vals):
    p=vals[0];d=0.
    for x in vals:
        p=max(p,x);d=min(d,x/p-1)
    return d
def sharpe(vals):
    r=[vals[i]/vals[i-1]-1 for i in range(1,len(vals)) if vals[i-1]>0]
    if len(r)<2:return None
    s=statistics.stdev(r)
    return None if s==0 else statistics.mean(r)/s*math.sqrt(252)

def load(indir,year):
    p=Path(indir)
    sigp=next(p.glob(f"**/signals_{year}.csv"))
    sig=pd.read_csv(sigp)
    sig["signal_date"]=sig.signal_date.astype(str)
    sig["detected_at"]=sig.detected_at.astype(str)
    sig["symbol"]=sig.symbol.astype(str)
    sig=sig[(sig.liquidity_rank<=500)&(sig.scale=="large")].copy()
    sig=sig.sort_values(["signal_date","symbol","detected_at"],
                        ascending=[True,True,False]).drop_duplicates(
                            ["signal_date","symbol"],keep="first")
    syms=set(sig.symbol);syms.add("SPY")
    kept=[];dates=set()
    for bp in sorted(p.glob("**/bars_*.csv.gz")):
        for ch in pd.read_csv(bp,chunksize=300000):
            ch["date"]=ch.date.astype(str);ch["ticker"]=ch.ticker.astype(str)
            dates.update(ch.date.unique().tolist())
            z=ch[ch.ticker.isin(syms)].copy()
            if len(z):kept.append(z)
    bars=pd.concat(kept,ignore_index=True)
    bars=bars.sort_values(["ticker","date"]).drop_duplicates(["ticker","date"],keep="last")
    cal=sorted(dates);idx={d:i for i,d in enumerate(cal)}
    nxt={cal[i]:cal[i+1] for i in range(len(cal)-1)}
    bm={s:{r["date"]:r for r in g.to_dict("records")} for s,g in bars.groupby("ticker")}
    spy=bars[bars.ticker=="SPY"].sort_values("date").reset_index(drop=True)
    return sig,cal,idx,nxt,bm,spy

def regime_map(spy):
    s=spy.copy()
    s["close"]=pd.to_numeric(s.close,errors="coerce")
    s["logret"]=np.log(s.close/s.close.shift(1))
    s["rv20"]=s.logret.rolling(20,min_periods=15).std(ddof=0)*np.sqrt(252)
    s["ret20"]=s.close/s.close.shift(20)-1
    s["ma200"]=s.close.rolling(200,min_periods=200).mean()
    s["dd60"]=s.close/s.close.rolling(60,min_periods=60).max()-1
    s["trend"]=np.where(s.ma200.notna(),np.where(s.close>=s.ma200,"ABOVE_MA200","BELOW_MA200"),None)

    volpct=[]
    for i,r in s.iterrows():
        if pd.isna(r.rv20):
            volpct.append(np.nan);continue
        a=max(0,i-251)
        hist=s.loc[a:i,"rv20"].dropna()
        if len(hist)<60:
            volpct.append(np.nan)
        else:
            volpct.append(float((hist<=r.rv20).mean()))
    s["vol_pct"]=volpct
    def vol_label(v):
        if pd.isna(v):return None
        if v<=.30:return "LOW_LE_30PCT"
        if v>=.70:return "HIGH_GE_70PCT"
        return "MID_30_TO_70PCT"
    def dd_label(v):
        if pd.isna(v):return None
        if v>-.05:return "SHALLOW_GT_-5PCT"
        if v>-.10:return "MEDIUM_-5_TO_-10PCT"
        return "DEEP_LE_-10PCT"
    def abs_label(rv,ret):
        if pd.isna(rv) or pd.isna(ret):return None
        if rv<.10 and ret>0:return "CALM_UPTREND"
        if rv<.10 and ret<=0:return "CALM_WEAK"
        if rv>=.10 and ret<=0:return "STRESS_REVERSAL"
        return "VOLATILE_UPTREND"
    s["vol_regime"]=s.vol_pct.map(vol_label)
    s["dd_regime"]=s.dd60.map(dd_label)
    s["abs_regime"]=[abs_label(rv,ret) for rv,ret in zip(s.rv20,s.ret20)]
    out={}
    for r in s.to_dict("records"):
        trend=r["trend"] if isinstance(r["trend"],str) else None
        vol=r["vol_regime"] if isinstance(r["vol_regime"],str) else None
        dd=r["dd_regime"] if isinstance(r["dd_regime"],str) else None
        absr=r["abs_regime"] if isinstance(r["abs_regime"],str) else None
        out[str(r["date"])]={
          "spy_ret20":None if pd.isna(r["ret20"]) else float(r["ret20"]),
          "spy_rv20":None if pd.isna(r["rv20"]) else float(r["rv20"]),
          "spy_dd60":None if pd.isna(r["dd60"]) else float(r["dd60"]),
          "trend":trend,"vol_regime":vol,"dd_regime":dd,"abs_regime":absr,
          "trend_x_vol":f"{trend}|{vol}" if trend and vol else None,
          "trend_x_dd":f"{trend}|{dd}" if trend and dd else None,
        }
    return out

def confirmed(sig,cal,idx,nxt,bm,regimes):
    out=[]
    for q in sig.to_dict("records"):
        d0=q["signal_date"];d1=nxt.get(d0);d2=nxt.get(d1) if d1 else None
        if not d1 or not d2:continue
        sm=bm.get(q["symbol"],{})
        b0=sm.get(d0);b1=sm.get(d1);b2=sm.get(d2)
        if b0 is None or b1 is None or b2 is None:continue
        lo=float(q["lower"]);hi=float(q["upper"]);op1=float(b1["open"]);op2=float(b2["open"])
        if not(lo<op1<hi and lo<op2<hi):continue
        if float(b1["low"])<float(b0["low"]):continue
        if float(b1["close"])<=float(b1["open"]):continue
        age=max(0,idx[d0]-idx.get(q["detected_at"],idx[d0]))
        reg=regimes.get(d1,{})
        out.append({
          **q,"lower":lo,"upper":hi,"box_age_sessions":age,
          "confirmation_date":d1,"entry_date":d2,"entry_price":op2,
          **reg
        })
    return pd.DataFrame(out)

def event_outcome(c,bm,calendar_idx,target_frac):
    sm=bm.get(c["symbol"],{})
    lo=float(c["lower"]);hi=float(c["upper"]);target=lo+target_frac*(hi-lo)
    entry=str(c["entry_date"]);ei=calendar_idx.get(entry)
    if ei is None:return None
    op=float(c["entry_price"])
    if not(lo<op<target):return None
    maxp=op;minp=op
    last=op
    for k in range(MAX_HOLD):
        di=ei+k
        if di>=len(CALENDAR):break
        d=CALENDAR[di];b=sm.get(d)
        if b is None:
            if k==MAX_HOLD-1:
                px=last*(1-EXIT_COST)
                return {"exit_reason":"max_hold_stale","holding_sessions":k+1,
                        "net_return":(px/op)/(1+ENTRY_COST)-1,
                        "mfe_return":maxp/op-1,"mae_return":minp/op-1}
            continue
        o=float(b["open"]);low=float(b["low"]);high=float(b["high"]);cl=float(b["close"])
        maxp=max(maxp,high);minp=min(minp,low);last=cl
        if o<=lo:
            px=o;reason="stop_gap"
        elif o>=target:
            px=o;reason="target_gap"
        elif low<=lo:
            px=lo;reason="stop"
        elif high>=target:
            px=target;reason="target"
        elif k==MAX_HOLD-1:
            px=cl;reason="max_hold"
        else:
            continue
        gross=(px*(1-EXIT_COST))/(op*(1+ENTRY_COST))-1
        return {"exit_reason":reason,"holding_sessions":k+1,"net_return":gross,
                "mfe_return":maxp/op-1,"mae_return":minp/op-1}
    return None

def run_portfolio(cands,bm,calendar,year,target_frac):
    days=[d for d in calendar if d.startswith(str(year))]
    yidx={d:i for i,d in enumerate(days)}
    by=defaultdict(list)
    for c in cands.to_dict("records"):
        d=str(c["entry_date"])
        if d in yidx and yidx[d]+MAX_HOLD-1<len(days):
            by[d].append(c)
    cash=1.;pos={};vals=[];expo=[];tr=[]
    for d in days:
        # gap exits
        for sym in list(pos):
            b=bm.get(sym,{}).get(d)
            if b is None:continue
            p=pos[sym];o=float(b["open"]);px=None;reason=None
            if o<=p["lower"]:px=o;reason="stop_gap"
            elif o>=p["target"]:px=o;reason="target_gap"
            if px is not None:
                proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                tr.append(proceeds/p["cost_basis"]-1);del pos[sym]
        cand=[c for c in by.get(d,[]) if c["symbol"] not in pos]
        cand.sort(key=lambda x:(x["symbol"],x["signal_date"]))
        ded=[];seen=set()
        for c in cand:
            if c["symbol"] in seen:continue
            seen.add(c["symbol"]);ded.append(c)
        cand=ded
        eqo=cash
        for sym,p in pos.items():
            b=bm.get(sym,{}).get(d);eqo+=p["shares"]*(float(b["open"]) if b is not None else p["last"])
        if cand:
            req=[ALLOC*eqo]*len(cand);budget=min(cash,sum(req));sc=budget/sum(req) if req else 0
            for c,r in zip(cand,req):
                a=r*sc
                b=bm.get(c["symbol"],{}).get(d)
                if b is None or a<=1e-12:continue
                o=float(b["open"]);lo=float(c["lower"]);hi=float(c["upper"]);target=lo+target_frac*(hi-lo)
                if not(lo<o<target):continue
                invest=a*(1-ENTRY_COST);cash-=a
                pos[c["symbol"]]={**c,"target":target,"shares":invest/o,"cost_basis":a,
                                  "entry_i":yidx[d],"entry_price":o,"last":o}
        for sym in list(pos):
            p=pos[sym];hold=yidx[d]-p["entry_i"]+1
            b=bm.get(sym,{}).get(d)
            if b is None:
                if hold>=MAX_HOLD:
                    px=p["last"];proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                    tr.append(proceeds/p["cost_basis"]-1);del pos[sym]
                continue
            low=float(b["low"]);high=float(b["high"]);cl=float(b["close"]);px=None
            if low<=p["lower"]:px=p["lower"]
            elif high>=p["target"]:px=p["target"]
            elif hold>=MAX_HOLD:px=cl
            if px is not None:
                proceeds=p["shares"]*px*(1-EXIT_COST);cash+=proceeds
                tr.append(proceeds/p["cost_basis"]-1);del pos[sym]
            else:p["last"]=cl
        val=cash;inv=0.
        for sym,p in pos.items():
            b=bm.get(sym,{}).get(d);px=float(b["close"]) if b is not None else p["last"];p["last"]=px
            q=p["shares"]*px;val+=q;inv+=q
        vals.append(val);expo.append(inv/val if val>0 else 0.)
    return {
      "total_return":vals[-1]-1 if vals else 0.,
      "max_drawdown":mdd(vals) if vals else None,
      "sharpe":sharpe(vals),
      "avg_exposure":statistics.mean(expo) if expo else 0.,
      "completed_trades":len(tr),
      "profit_factor":pf(tr),
      "mean_trade":statistics.mean(tr) if tr else None,
    }

def main():
    global CALENDAR
    ap=argparse.ArgumentParser()
    ap.add_argument("--year",type=int,required=True)
    ap.add_argument("--indir",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,CALENDAR,idx,nxt,bm,spy=load(a.indir,a.year)
    regs=regime_map(spy)
    c=confirmed(sig,CALENDAR,idx,nxt,bm,regs)
    ci={d:i for i,d in enumerate(CALENDAR)}

    event_rows=[];portfolio_rows=[]
    state_cols=["trend","vol_regime","dd_regime","abs_regime","trend_x_vol","trend_x_dd"]
    for cap in (300,500):
        base=c[(c.liquidity_rank<=cap)&(c.box_age_sessions<=FRESH[cap])].copy()
        for label,frac in TARGETS.items():
            # event-level outcomes
            ev=[]
            for row in base.to_dict("records"):
                r=event_outcome(row,bm,ci,frac)
                if r is not None:ev.append({**row,"target_fraction":frac,**r})
            e=pd.DataFrame(ev)
            if len(e):
                for sc in state_cols:
                    for state,g in e.dropna(subset=[sc]).groupby(sc):
                        rs=g.net_return.astype(float).tolist()
                        reasons=g.exit_reason.astype(str)
                        event_rows.append({
                          "year":a.year,"rank_cap":cap,"target_fraction":frac,
                          "state_dimension":sc,"state":str(state),"n":len(g),
                          "mean_trade":float(g.net_return.mean()),
                          "median_trade":float(g.net_return.median()),
                          "profit_factor":pf(rs),
                          "win_rate":float((g.net_return>0).mean()),
                          "target_share":float(reasons.isin(["target","target_gap"]).mean()),
                          "stop_share":float(reasons.isin(["stop","stop_gap"]).mean()),
                          "max_hold_share":float(reasons.str.startswith("max_hold").mean()),
                          "mean_holding_sessions":float(g.holding_sessions.mean()),
                          "mean_mfe_return":float(g.mfe_return.mean()),
                          "mean_mae_return":float(g.mae_return.mean()),
                        })
            # portfolio diagnostics baseline, include-state, exclude-state
            baseline=run_portfolio(base,bm,CALENDAR,a.year,frac)
            portfolio_rows.append({
              "year":a.year,"rank_cap":cap,"target_fraction":frac,
              "state_dimension":"ALL","state":"ALL","portfolio_lane":"baseline",**baseline})
            for sc in state_cols:
                vals=sorted([str(v) for v in base[sc].dropna().unique()])
                for state in vals:
                    inc=base[base[sc].astype(str)==state]
                    exc=base[base[sc].astype(str)!=state]
                    portfolio_rows.append({
                      "year":a.year,"rank_cap":cap,"target_fraction":frac,
                      "state_dimension":sc,"state":state,"portfolio_lane":"include",**run_portfolio(inc,bm,CALENDAR,a.year,frac)})
                    portfolio_rows.append({
                      "year":a.year,"rank_cap":cap,"target_fraction":frac,
                      "state_dimension":sc,"state":state,"portfolio_lane":"exclude",**run_portfolio(exc,bm,CALENDAR,a.year,frac)})

    pd.DataFrame(event_rows).to_csv(out/f"large_permission_events_{a.year}.csv",index=False)
    pd.DataFrame(portfolio_rows).to_csv(out/f"large_permission_portfolios_{a.year}.csv",index=False)
    receipt={
      "schema":"LARGE-MARKET-PERMISSION-YEAR-V1","year":a.year,
      "confirmed_large_rows":int(len(c)),
      "classified":{
        col:int(c[col].notna().sum()) for col in ["trend","vol_regime","dd_regime","abs_regime"]
      }
    }
    (out/f"summary_{a.year}.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
    print(json.dumps(receipt,indent=2))

if __name__=="__main__":
    main()
