#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd

import research_pure_box_large_market_permission_year_v1 as base

TARGETS={"60":.60,"80":.80}
FRESH={300:23,500:24}

def classify(trend,ret20):
    if trend is None or ret20 is None or pd.isna(ret20):
        return None
    if trend=="ABOVE_MA200" and float(ret20)<=0:
        return "UPTREND_PULLBACK"
    if trend=="ABOVE_MA200" and float(ret20)>0:
        return "UPTREND_RISING"
    if trend=="BELOW_MA200" and float(ret20)<=0:
        return "DOWNTREND_SELLING"
    if trend=="BELOW_MA200" and float(ret20)>0:
        return "DOWNTREND_BOUNCE"
    return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--year",type=int,required=True)
    ap.add_argument("--indir",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

    sig,cal,idx,nxt,bm,spy=base.load(a.indir,a.year)
    base.CALENDAR=cal
    regs=base.regime_map(spy)
    c=base.confirmed(sig,cal,idx,nxt,bm,regs)
    c["pullback_regime"]=[
      classify(t,r) for t,r in zip(c["trend"],c["spy_ret20"])
    ]
    ci={d:i for i,d in enumerate(cal)}

    event_rows=[]; portfolio_rows=[]
    for cap in (300,500):
        z=c[(c.liquidity_rank<=cap)&(c.box_age_sessions<=FRESH[cap])].copy()
        z=z[z.pullback_regime.notna()].copy()
        for label,frac in TARGETS.items():
            # event outcomes
            ev=[]
            for row in z.to_dict("records"):
                rr=base.event_outcome(row,bm,ci,frac)
                if rr is not None:
                    ev.append({**row,"target_fraction":frac,**rr})
            e=pd.DataFrame(ev)
            if len(e):
                for state,g in e.groupby("pullback_regime"):
                    rs=g.net_return.astype(float).tolist()
                    reasons=g.exit_reason.astype(str)
                    event_rows.append({
                      "year":a.year,"rank_cap":cap,"target_fraction":frac,
                      "state":state,"n":int(len(g)),
                      "mean_trade":float(g.net_return.mean()),
                      "median_trade":float(g.net_return.median()),
                      "profit_factor":base.pf(rs),
                      "gross_positive_return_sum":float(g.loc[g.net_return>0,"net_return"].sum()),
                      "gross_negative_return_abs_sum":float(-g.loc[g.net_return<0,"net_return"].sum()),
                      "win_rate":float((g.net_return>0).mean()),
                      "target_share":float(reasons.isin(["target","target_gap"]).mean()),
                      "stop_share":float(reasons.isin(["stop","stop_gap"]).mean()),
                      "max_hold_share":float(reasons.str.startswith("max_hold").mean()),
                      "mean_holding_sessions":float(g.holding_sessions.mean()),
                      "mean_mfe_return":float(g.mfe_return.mean()),
                      "mean_mae_return":float(g.mae_return.mean()),
                    })

            # portfolio diagnostics
            allr=base.run_portfolio(z,bm,cal,a.year,frac)
            portfolio_rows.append({
              "year":a.year,"rank_cap":cap,"target_fraction":frac,
              "state":"ALL","portfolio_lane":"baseline",**allr
            })
            for state in ("UPTREND_PULLBACK","UPTREND_RISING","DOWNTREND_SELLING","DOWNTREND_BOUNCE"):
                inc=z[z.pullback_regime==state]
                exc=z[z.pullback_regime!=state]
                portfolio_rows.append({
                  "year":a.year,"rank_cap":cap,"target_fraction":frac,
                  "state":state,"portfolio_lane":"include",**base.run_portfolio(inc,bm,cal,a.year,frac)
                })
                portfolio_rows.append({
                  "year":a.year,"rank_cap":cap,"target_fraction":frac,
                  "state":state,"portfolio_lane":"exclude",**base.run_portfolio(exc,bm,cal,a.year,frac)
                })

    pd.DataFrame(event_rows).to_csv(out/f"pullback_regime_events_{a.year}.csv",index=False)
    pd.DataFrame(portfolio_rows).to_csv(out/f"pullback_regime_portfolios_{a.year}.csv",index=False)
    receipt={
      "schema":"LARGE-PULLBACK-REGIME-YEAR-V2",
      "year":a.year,
      "confirmed_large":int(len(c)),
      "classified":int(c.pullback_regime.notna().sum()),
      "state_counts":c.pullback_regime.value_counts(dropna=True).to_dict()
    }
    (out/f"summary_{a.year}.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
    print(json.dumps(receipt,indent=2))

if __name__=="__main__":
    main()
