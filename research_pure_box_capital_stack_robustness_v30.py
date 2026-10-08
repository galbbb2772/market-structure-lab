#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,statistics,math
from collections import defaultdict
from datetime import date
from pathlib import Path
import pandas as pd
import research_pure_box_core_geometry_simplicity_v13 as v13
import research_pure_box_capital_architecture_v22 as v22
import research_pure_box_capital_stack_interaction_v29 as v29

def rolling_stats(eq,window):
    rs=[]
    for i in range(window-1,len(eq)):
        a=eq.iloc[i-window+1].equity;b=eq.iloc[i].equity
        if a>0:rs.append(b/a-1)
    return {
      "min":min(rs) if rs else None,
      "median":statistics.median(rs) if rs else None,
      "positive_share":sum(x>0 for x in rs)/len(rs) if rs else None
    }

def simulate_trade_rows(cands,cal,bm,cost_bps=5,delay=False):
    ec=cost_bps/10000;xc=cost_bps/10000
    idx={d:i for i,d in enumerate(cal)}
    rows=[]
    for c in cands:
        s=str(c["symbol"]);d=str(c["direct_entry_date"])
        if d not in idx:continue
        j=idx[d]+(1 if delay else 0)
        if j>=len(cal):continue
        ed=cal[j];b=bm.get(s,{}).get(ed)
        if b is None:continue
        lo=float(c["lower"]);hi=float(c["upper"]);op=float(b["open"]);target=lo+.60*(hi-lo)
        if not(lo<op<target):continue
        ef=(op-lo)/(hi-lo)
        if ef>.20:continue
        px=op;reason="";exd=ed
        for age in range(1,16):
            k=j+age-1
            if k>=len(cal):break
            day=cal[k];bb=bm.get(s,{}).get(day)
            if bb is None:continue
            o=float(bb["open"])
            if o<=lo:px=o;reason="stop_gap"
            elif o>=target:px=o;reason="target_gap"
            elif float(bb["low"])<=lo:px=lo;reason="stop"
            elif float(bb["high"])>=target:px=target;reason="target60"
            elif age>=15:px=float(bb["close"]);reason="time_h15"
            else:continue
            exd=day;break
        net=px*(1-xc)/(op*(1+ec))-1
        rows.append({"symbol":s,"entry_date":ed,"signal_date":str(c["signal_date"]),"year":ed[:4],
                     "liquidity_rank":int(c["liquidity_rank"]),"entry_fraction":ef,
                     "box_width_pct":(hi-lo)/op,"scale":str(c["scale"]),
                     "net_return":net,"exit_date":exd,"exit_reason":reason})
    return pd.DataFrame(rows)

def trade_stats(df):
    rs=df.net_return.tolist()
    if not rs:return {"n":0}
    w=sum(x for x in rs if x>0);l=-sum(x for x in rs if x<0)
    return {"n":len(rs),"mean_trade":statistics.mean(rs),"median_trade":statistics.median(rs),
            "profit_factor":w/l if l>0 else None,"win_rate":sum(x>0 for x in rs)/len(rs),
            "sum_trade_return":sum(rs)}

def concentration(df):
    by=df.groupby("symbol").net_return.sum().abs().sort_values(ascending=False)
    total=float(by.sum()) if len(by) else 0.
    return {"top5_abs_pnl_share":float(by.head(5).sum()/total) if total else None,
            "top10_abs_pnl_share":float(by.head(10).sum()/total) if total else None}

def portfolio_from_trade_subset(df):
    # simple diagnostic only, not capital-aware: compounded sequentially by entry date at unit notional
    if df.empty:return None
    vals=[1.0]
    for x in df.sort_values(["entry_date","symbol"]).net_return:
        vals.append(vals[-1]*(1+x))
    return vals[-1]-1

def run_cost_lane(cands,cal,bm,cap,lane,cost_bps,delay):
    # reuse V29 at baseline only; for stressed cost/delay use trade-level diagnostic because v29 costs are fixed.
    t=simulate_trade_rows(cands,cal,bm,cost_bps,delay)
    return {
      "trade_stats":trade_stats(t),
      "concentration":concentration(t),
      "diagnostic_compounded_trade_return":portfolio_from_trade_subset(t)
    }

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=v13.load(a.indir)
    summary={"schema":"PURE-BOX-SIMPLE-CORE-CAPITAL-STACK-ROBUSTNESS-V30","results":{}}
    rows=[]
    configs={
      300:[
        ("BASE_R125_PRO_RATA","R125","PRO_RATA"),
        ("EA_PRO_RATA","EA","PRO_RATA"),
        ("R125_LOW_ENTRY","R125","LOW_ENTRY_FIRST"),
        ("EA_LOW_ENTRY","EA","LOW_ENTRY_FIRST"),
      ],
      500:[
        ("BASE_R125_PRO_RATA","R125","PRO_RATA"),
        ("EA_PRO_RATA","EA","PRO_RATA"),
        ("R125_LIQUIDITY","R125","LIQUIDITY_FIRST"),
        ("EA_LIQUIDITY","EA","LIQUIDITY_FIRST"),
      ]
    }
    for cap,lcfg in configs.items():
        cs=v22.bottom20(v13.strict_signals(sig,cap,cal,idx,nxt,bm))
        cres={}
        for name,rm,apol in lcfg:
            base=v29.run(cs,cal,bm,rm,apol)
            # year robustness from portfolio result already available
            tbase=simulate_trade_rows(cs,cal,bm,5,False)
            years=sorted(tbase.year.unique())
            loyo={y:trade_stats(tbase[tbase.year!=y]) for y in years}
            # Concentration is trade-level diagnostic over frozen signal set.
            entry={"baseline":base,
                   "trade_concentration":concentration(tbase),
                   "leave_one_year_out_trade":loyo,
                   "cost_delay_stress":{}}
            for bps in (5,10,20):
                entry["cost_delay_stress"][f"{bps}bps_direct"]=run_cost_lane(cs,cal,bm,cap,name,bps,False)
                entry["cost_delay_stress"][f"{bps}bps_delay_revalidated"]=run_cost_lane(cs,cal,bm,cap,name,bps,True)
            cres[name]=entry
            rows.append({"rank_cap":cap,"lane":name,**base,
                         **concentration(tbase)})
        summary["results"][f"top{cap}"]=cres
    pd.DataFrame(rows).to_csv(out/"baseline_results.csv",index=False)
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(pd.DataFrame(rows)[["rank_cap","lane","total_return","cagr","max_drawdown","daily_sharpe",
                              "rolling_12m_min_return","top5_abs_pnl_share","top10_abs_pnl_share"]].to_string(index=False))
if __name__=="__main__":main()
