#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd
import research_pure_box_large_market_permission_year_v1 as large

TARGETS=(.60,.80)
GAP_METHODS={
 "EXPANDING":"gap_expanding_lane",
 "FIXED_-1PCT":"gap_fixed_lane",
}
EXHAUSTION={
 "rebound_from_low_box":"rebound_strength",
 "low_progress_box":"lowprog_strength",
}

def pf(rs):
    w=sum(float(x) for x in rs if float(x)>0)
    l=-sum(float(x) for x in rs if float(x)<0)
    return w/l if l>0 else None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--year",type=int,required=True)
    ap.add_argument("--indir",required=True)
    ap.add_argument("--labels",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

    _,cal,_,_,bm,_=large.load(a.indir,a.year)
    large.CALENDAR=cal
    lab=pd.read_csv(a.labels,compression="infer")
    lab["year"]=lab.year.astype(int)
    ci={d:i for i,d in enumerate(cal)}

    event_rows=[];portfolio_rows=[]
    for cap in (300,500):
        z=lab[(lab.year==a.year)&(lab.rank_cap==cap)].copy()
        if z.empty: continue
        for target in TARGETS:
            ev=[]
            for row in z.to_dict("records"):
                rr=large.event_outcome(row,bm,ci,target)
                if rr is not None:
                    ev.append({**row,"target_fraction":target,**rr})
            e=pd.DataFrame(ev)

            for method,gcol in GAP_METHODS.items():
                for feat,scol in EXHAUSTION.items():
                    for gaplane in ("EXTREME_GAP","NON_EXTREME"):
                        for strength in ("STRONG","WEAK"):
                            lane=f"{gaplane}__{strength}"
                            gc=z[(z[gcol]==gaplane)&(z[scol]==strength)].copy()
                            pc=large.run_portfolio(gc,bm,cal,a.year,target)
                            portfolio_rows.append({
                              "year":a.year,"rank_cap":cap,"target_fraction":target,
                              "gap_method":method,"exhaustion_feature":feat,"lane":lane,
                              "candidate_count":int(len(gc)),**pc
                            })

                            if len(e):
                                ge=e[(e[gcol]==gaplane)&(e[scol]==strength)].copy()
                                if len(ge):
                                    rs=ge.net_return.astype(float).tolist()
                                    reasons=ge.exit_reason.astype(str)
                                    event_rows.append({
                                      "year":a.year,"rank_cap":cap,"target_fraction":target,
                                      "gap_method":method,"exhaustion_feature":feat,"lane":lane,
                                      "n":int(len(ge)),
                                      "mean_trade":float(ge.net_return.mean()),
                                      "median_trade":float(ge.net_return.median()),
                                      "profit_factor":pf(rs),
                                      "win_rate":float((ge.net_return>0).mean()),
                                      "target_share":float(reasons.isin(["target","target_gap"]).mean()),
                                      "stop_share":float(reasons.isin(["stop","stop_gap"]).mean()),
                                      "max_hold_share":float(reasons.str.startswith("max_hold").mean()),
                                      "mean_holding_sessions":float(ge.holding_sessions.mean()),
                                      "mean_mfe_return":float(ge.mfe_return.mean()),
                                      "mean_mae_return":float(ge.mae_return.mean()),
                                      "gross_positive_return_sum":float(ge.loc[ge.net_return>0,"net_return"].sum()),
                                      "gross_negative_return_abs_sum":float(-ge.loc[ge.net_return<0,"net_return"].sum()),
                                    })

    pd.DataFrame(event_rows).to_csv(out/f"gap_exhaustion_events_{a.year}.csv",index=False)
    pd.DataFrame(portfolio_rows).to_csv(out/f"gap_exhaustion_portfolios_{a.year}.csv",index=False)
    summary={"schema":"LARGE-GAP-EXHAUSTION-YEAR-V5","year":a.year,
             "event_rows":len(event_rows),"portfolio_rows":len(portfolio_rows)}
    (out/f"summary_{a.year}.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))

if __name__=="__main__":
    main()
