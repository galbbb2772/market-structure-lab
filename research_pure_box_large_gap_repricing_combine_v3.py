#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd

ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
src=Path(a.indir);out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
ef=sorted(src.glob("**/gap_repricing_events_*.csv"));pf=sorted(src.glob("**/gap_repricing_portfolios_*.csv"))
if len(ef)<8 or len(pf)<8: raise RuntimeError(f"expected 8+8 shards, got {len(ef)} {len(pf)}")
e=pd.concat([pd.read_csv(f) for f in ef],ignore_index=True);p=pd.concat([pd.read_csv(f) for f in pf],ignore_index=True)
e["period"]=e.year.map(lambda y:"discovery" if int(y)<=2022 else "validation")
p["period"]=p.year.map(lambda y:"discovery" if int(y)<=2022 else "validation")
e.to_csv(out/"annual_event_stats.csv",index=False);p.to_csv(out/"annual_portfolio_stats.csv",index=False)

def wavg(g,col,w="n"):
    z=g[[col,w]].dropna()
    if z.empty:return None
    ww=z[w].astype(float)
    if ww.sum()<=0:return None
    return float((z[col].astype(float)*ww).sum()/ww.sum())

erows=[]
for (cap,target,dim,state,period),g in e.groupby(["rank_cap","target_fraction","state_dimension","state","period"]):
    gp=float(g.gross_positive_return_sum.sum());gl=float(g.gross_negative_return_abs_sum.sum())
    erows.append({
      "rank_cap":int(cap),"target_fraction":float(target),"state_dimension":dim,"state":state,"period":period,
      "n":int(g.n.sum()),"mean_trade":wavg(g,"mean_trade"),"median_trade":wavg(g,"median_trade"),
      "profit_factor":gp/gl if gl>0 else None,"win_rate":wavg(g,"win_rate"),
      "target_share":wavg(g,"target_share"),"stop_share":wavg(g,"stop_share"),
      "max_hold_share":wavg(g,"max_hold_share"),"mean_holding_sessions":wavg(g,"mean_holding_sessions"),
      "mean_mfe_return":wavg(g,"mean_mfe_return"),"mean_mae_return":wavg(g,"mean_mae_return"),
      "yearly_mean_trade":json.dumps({str(int(r.year)):float(r.mean_trade) for r in g.itertuples()},sort_keys=True),
      "yearly_pf":json.dumps({str(int(r.year)):None if pd.isna(r.profit_factor) else float(r.profit_factor) for r in g.itertuples()},sort_keys=True),
      "yearly_n":json.dumps({str(int(r.year)):int(r.n) for r in g.itertuples()},sort_keys=True)
    })
edf=pd.DataFrame(erows);edf.to_csv(out/"event_summary.csv",index=False)

prows=[]
for (cap,target,dim,state,period),g in p.groupby(["rank_cap","target_fraction","state_dimension","state","period"]):
    comp=1.0
    for r in g.sort_values("year").itertuples():comp*=1+float(r.total_return)
    prows.append({
      "rank_cap":int(cap),"target_fraction":float(target),"state_dimension":dim,"state":state,"period":period,
      "segments":len(g),"compounded_segment_return":comp-1,"positive_segments":int((g.total_return>0).sum()),
      "avg_sharpe":float(g.sharpe.mean()) if g.sharpe.notna().any() else None,
      "worst_segment_mdd":float(g.max_drawdown.min()) if g.max_drawdown.notna().any() else None,
      "avg_exposure":float(g.avg_exposure.mean()),"total_trades":int(g.completed_trades.sum()),
      "yearly_return":json.dumps({str(int(r.year)):float(r.total_return) for r in g.itertuples()},sort_keys=True)
    })
pdf=pd.DataFrame(prows);pdf.to_csv(out/"portfolio_summary.csv",index=False)

def ev(cap,target,period,dim,state):
    z=edf[(edf.rank_cap==cap)&(edf.target_fraction==target)&(edf.period==period)&(edf.state_dimension==dim)&(edf.state==state)]
    return None if z.empty else z.iloc[0]
def po(cap,target,period,dim,state):
    z=pdf[(pdf.rank_cap==cap)&(pdf.target_fraction==target)&(pdf.period==period)&(pdf.state_dimension==dim)&(pdf.state==state)]
    return None if z.empty else z.iloc[0]
def yearmap(s):
    try:return json.loads(s)
    except:return {}

comparisons=[
 ("BINARY","gap_binary","NO_GAP_DOWN","GAP_DOWN"),
 ("REJECTED_VS_CONTINUED","gap_four_state","GAP_DOWN_REJECTED","GAP_DOWN_CONTINUED"),
 ("INTRADAY_SELLING_VS_GAP_CONTINUED","gap_four_state","NO_GAP_DOWN_SELLING","GAP_DOWN_CONTINUED"),
]
checks=[];support={}
for name,dim,good,bad in comparisons:
    arr=[]
    for cap in (300,500):
      for target in (.6,.8):
        for period in ("discovery","validation"):
          eg=ev(cap,target,period,dim,good);eb=ev(cap,target,period,dim,bad)
          pg=po(cap,target,period,dim,good);pb=po(cap,target,period,dim,bad)
          if any(x is None for x in (eg,eb,pg,pb)):continue
          event=bool(float(eg.mean_trade)>float(eb.mean_trade) and float(eg.profit_factor)>float(eb.profit_factor))
          port=bool(float(pg.compounded_segment_return)>float(pb.compounded_segment_return))
          yg=yearmap(eg.yearly_mean_trade);yb=yearmap(eb.yearly_mean_trade);yrs=sorted(set(yg)&set(yb))
          better=sum(float(yg[y])>float(yb[y]) for y in yrs)
          not_one=bool(len(yrs)>=2 and better>=2)
          passed=event and port and not_one
          rec={"comparison":name,"rank_cap":cap,"target_fraction":target,"period":period,
               "good_state":good,"bad_state":bad,"good_n":int(eg.n),"bad_n":int(eb.n),
               "good_mean_trade":float(eg.mean_trade),"bad_mean_trade":float(eb.mean_trade),
               "good_pf":None if pd.isna(eg.profit_factor) else float(eg.profit_factor),
               "bad_pf":None if pd.isna(eb.profit_factor) else float(eb.profit_factor),
               "good_portfolio_comp":float(pg.compounded_segment_return),
               "bad_portfolio_comp":float(pb.compounded_segment_return),
               "better_years":better,"overlap_years":yrs,
               "event_order":event,"portfolio_order":port,"not_one_year":not_one,"passed":passed}
          checks.append(rec);arr.append(rec)
    support[name]={"passed_checks":sum(x["passed"] for x in arr),"total_checks":len(arr),
                   "all_checks_passed":bool(arr and all(x["passed"] for x in arr))}

summary={"schema":"LARGE-GAP-REPRICING-V3","support":support,"checks":checks}
(out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
pd.DataFrame(checks).to_csv(out/"support_checks.csv",index=False)
print(json.dumps({"schema":summary["schema"],"support":support},indent=2))
