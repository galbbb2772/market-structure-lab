#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd

import research_pure_box_large_market_permission_year_v1 as large
import research_pure_box_large_selloff_anatomy_year_v2 as anatomy

TARGETS=(.60,.80)
FRESH={300:23,500:24}

def classify(gap,intra):
    if pd.isna(gap) or pd.isna(intra): return None,None
    binary="GAP_DOWN" if gap<0 else "NO_GAP_DOWN"
    if gap<0 and intra<=0: four="GAP_DOWN_CONTINUED"
    elif gap<0 and intra>0: four="GAP_DOWN_REJECTED"
    elif gap>=0 and intra<0: four="NO_GAP_DOWN_SELLING"
    else: four="NO_GAP_DOWN_RISING"
    return binary,four

def pf(rs):
    w=sum(x for x in rs if x>0);l=-sum(x for x in rs if x<0)
    return w/l if l>0 else None

def event_stats(e,group_col):
    rows=[]
    if e.empty:return rows
    for state,g in e.dropna(subset=[group_col]).groupby(group_col):
        rs=g.net_return.astype(float).tolist(); reasons=g.exit_reason.astype(str)
        rows.append({
          "state_dimension":group_col,"state":state,"n":len(g),
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
          "gross_positive_return_sum":float(g.loc[g.net_return>0,"net_return"].sum()),
          "gross_negative_return_abs_sum":float(-g.loc[g.net_return<0,"net_return"].sum()),
        })
    return rows

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--year",type=int,required=True)
    ap.add_argument("--indir",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

    sig,cal,idx,nxt,bm,spy=large.load(a.indir,a.year)
    large.CALENDAR=cal
    c=large.confirmed(sig,cal,idx,nxt,bm,{})
    amap=anatomy.anatomy_map(bm)
    rows=[]
    for r in c.to_dict("records"):
        f=amap.get(str(r["symbol"]),{}).get(str(r["signal_date"]),{})
        gap=f.get("gap_component")
        intra=f.get("intraday_component")
        binary,four=classify(gap,intra)
        rows.append({**r,"gap_component":gap,"intraday_component":intra,
                     "gap_binary":binary,"gap_four_state":four})
    c=pd.DataFrame(rows)
    ci={d:i for i,d in enumerate(cal)}

    erows=[];prows=[]
    for cap in (300,500):
        z=c[(c.liquidity_rank<=cap)&(c.box_age_sessions<=FRESH[cap])].copy()
        for target in TARGETS:
            ev=[]
            for row in z.to_dict("records"):
                rr=large.event_outcome(row,bm,ci,target)
                if rr is not None:ev.append({**row,"target_fraction":target,**rr})
            e=pd.DataFrame(ev)
            for dim in ("gap_binary","gap_four_state"):
                for r in event_stats(e,dim):
                    erows.append({"year":a.year,"rank_cap":cap,"target_fraction":target,**r})

            # portfolio baseline and every predeclared state
            base=large.run_portfolio(z,bm,cal,a.year,target)
            prows.append({"year":a.year,"rank_cap":cap,"target_fraction":target,
                          "state_dimension":"ALL","state":"ALL",**base})
            for dim,states in [
              ("gap_binary",["GAP_DOWN","NO_GAP_DOWN"]),
              ("gap_four_state",["GAP_DOWN_CONTINUED","GAP_DOWN_REJECTED",
                                 "NO_GAP_DOWN_SELLING","NO_GAP_DOWN_RISING"])
            ]:
                for state in states:
                    g=z[z[dim]==state].copy()
                    res=large.run_portfolio(g,bm,cal,a.year,target)
                    prows.append({"year":a.year,"rank_cap":cap,"target_fraction":target,
                                  "state_dimension":dim,"state":state,**res})

    pd.DataFrame(erows).to_csv(out/f"gap_repricing_events_{a.year}.csv",index=False)
    pd.DataFrame(prows).to_csv(out/f"gap_repricing_portfolios_{a.year}.csv",index=False)
    receipt={"schema":"LARGE-GAP-REPRICING-YEAR-V3","year":a.year,
             "confirmed_large":int(len(c)),
             "binary_counts":c.gap_binary.value_counts(dropna=True).to_dict(),
             "four_state_counts":c.gap_four_state.value_counts(dropna=True).to_dict()}
    (out/f"summary_{a.year}.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
    print(json.dumps(receipt,indent=2))

if __name__=="__main__":
    main()
