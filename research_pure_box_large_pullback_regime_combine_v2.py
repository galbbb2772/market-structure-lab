#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd

ap=argparse.ArgumentParser()
ap.add_argument("--indir",required=True)
ap.add_argument("--outdir",required=True)
a=ap.parse_args()
src=Path(a.indir);out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

ef=sorted(src.glob("**/pullback_regime_events_*.csv"))
pf=sorted(src.glob("**/pullback_regime_portfolios_*.csv"))
if len(ef)<8 or len(pf)<8: raise RuntimeError(f"expected 8+8 shards, got {len(ef)} {len(pf)}")
e=pd.concat([pd.read_csv(f) for f in ef],ignore_index=True)
p=pd.concat([pd.read_csv(f) for f in pf],ignore_index=True)
e["period"]=e.year.map(lambda y:"discovery" if int(y)<=2022 else "validation")
p["period"]=p.year.map(lambda y:"discovery" if int(y)<=2022 else "validation")
e.to_csv(out/"annual_event_stats.csv",index=False)
p.to_csv(out/"annual_portfolio_stats.csv",index=False)

def wavg(g,col,w="n"):
    z=g[[col,w]].dropna()
    if z.empty:return None
    ww=z[w].astype(float)
    if ww.sum()<=0:return None
    return float((z[col].astype(float)*ww).sum()/ww.sum())

rows=[]
for (cap,target,state,period),g in e.groupby(["rank_cap","target_fraction","state","period"]):
    gp=float(g.gross_positive_return_sum.sum());gl=float(g.gross_negative_return_abs_sum.sum())
    rows.append({
      "rank_cap":int(cap),"target_fraction":float(target),"state":state,"period":period,
      "n":int(g.n.sum()),
      "mean_trade":wavg(g,"mean_trade"),
      "weighted_year_median_trade":wavg(g,"median_trade"),
      "profit_factor":gp/gl if gl>0 else None,
      "win_rate":wavg(g,"win_rate"),
      "target_share":wavg(g,"target_share"),
      "stop_share":wavg(g,"stop_share"),
      "max_hold_share":wavg(g,"max_hold_share"),
      "mean_holding_sessions":wavg(g,"mean_holding_sessions"),
      "mean_mfe_return":wavg(g,"mean_mfe_return"),
      "mean_mae_return":wavg(g,"mean_mae_return"),
      "yearly_mean_trade":{str(int(r.year)):float(r.mean_trade) for r in g.itertuples()},
      "yearly_pf":{str(int(r.year)):None if pd.isna(r.profit_factor) else float(r.profit_factor) for r in g.itertuples()},
      "yearly_n":{str(int(r.year)):int(r.n) for r in g.itertuples()},
    })
event=pd.DataFrame(rows)
event.to_csv(out/"event_summary.csv",index=False)

prows=[]
for (cap,target,state,lane,period),g in p.groupby(["rank_cap","target_fraction","state","portfolio_lane","period"]):
    comp=1.0
    for r in g.sort_values("year").itertuples():comp*=1+float(r.total_return)
    prows.append({
      "rank_cap":int(cap),"target_fraction":float(target),"state":state,"portfolio_lane":lane,"period":period,
      "segments":int(len(g)),"compounded_segment_return":comp-1,
      "positive_segments":int((g.total_return>0).sum()),
      "avg_sharpe":float(g.sharpe.mean()) if g.sharpe.notna().any() else None,
      "worst_segment_mdd":float(g.max_drawdown.min()) if g.max_drawdown.notna().any() else None,
      "avg_exposure":float(g.avg_exposure.mean()) if len(g) else None,
      "total_trades":int(g.completed_trades.sum()) if len(g) else 0,
      "yearly_return":{str(int(r.year)):float(r.total_return) for r in g.itertuples()},
    })
port=pd.DataFrame(prows)
port.to_csv(out/"portfolio_summary.csv",index=False)

summary={"schema":"LARGE-PULLBACK-REGIME-V2","states":{}}
for cap in (300,500):
    summary["states"][f"top{cap}"]={}
    for target in (.60,.80):
        tk=f"t{int(target*100)}"
        summary["states"][f"top{cap}"][tk]={}
        for state in ("UPTREND_PULLBACK","UPTREND_RISING","DOWNTREND_SELLING","DOWNTREND_BOUNCE"):
            q=event[(event.rank_cap==cap)&(event.target_fraction==target)&(event.state==state)]
            item={}
            for period in ("discovery","validation"):
                z=q[q.period==period]
                if len(z):
                    rr=z.iloc[0]
                    item[period]={
                      "n":int(rr.n),
                      "mean_trade":float(rr.mean_trade),
                      "profit_factor":None if pd.isna(rr.profit_factor) else float(rr.profit_factor),
                      "win_rate":float(rr.win_rate),
                      "stop_share":float(rr.stop_share),
                      "target_share":float(rr.target_share),
                      "mean_holding_sessions":float(rr.mean_holding_sessions),
                      "yearly_mean_trade":rr.yearly_mean_trade,
                      "yearly_pf":rr.yearly_pf,
                    }
            summary["states"][f"top{cap}"][tk][state]=item

(out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
print(json.dumps(summary,indent=2))
