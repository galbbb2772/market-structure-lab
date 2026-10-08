#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,statistics
from pathlib import Path
import pandas as pd
import research_pure_box_core_geometry_simplicity_v13 as v13
import research_pure_box_capital_architecture_v22 as v22
import research_pure_box_age3_resignal_addon_v48 as v48
import research_pure_box_age3_addon_fragility_v49 as v49

CLASSES={
"LEVERAGED_INVERSE_ETP":{"NVDL","QID","SDOW","SDS","SPXS","SPXU","SQQQ","SSO","SVXY","TMF","TNA","TZA","UDOW"},
"CRYPTO_ETP":{"ETHA","FBTC","GBTC","IBIT"},
"COMMODITY_VOL_ETP":{"GDX","GDXJ","SLV","USO","VXX"},
"THEMATIC_SECTOR_ETF":{"ARKK","KRE","KWEB","XME"},
}
def cls(sym):
    for k,s in CLASSES.items():
        if sym in s:return k
    return "SINGLE_STOCK"

def pf(rs):
    w=sum(x for x in rs if x>0);l=-sum(x for x in rs if x<0)
    return w/l if l>0 else None

def independent(cands,calendar,bm):
    cidx={d:i for i,d in enumerate(calendar)}
    rows=[]
    for c in cands:
        s=str(c["symbol"]);d=str(c["direct_entry_date"])
        if d not in cidx:continue
        b=bm.get(s,{}).get(d)
        if b is None:continue
        op=float(b["open"]);lo=float(c["lower"]);hi=float(c["upper"]);target=lo+.60*(hi-lo)
        if not(lo<op<target):continue
        ef=(op-lo)/(hi-lo)
        if ef>.20:continue
        j=cidx[d];px=op
        for age in range(1,16):
            k=j+age-1
            if k>=len(calendar):break
            day=calendar[k];bb=bm.get(s,{}).get(day)
            if bb is None:continue
            o=float(bb["open"])
            if o<=lo:px=o;break
            if o>=target:px=o;break
            if float(bb["low"])<=lo:px=lo;break
            if float(bb["high"])>=target:px=target;break
            if age>=15:px=float(bb["close"]);break
        r=px*(1-v48.XC)/(op*(1+v48.EC))-1
        rows.append({"symbol":s,"class":cls(s),"ret":r,"liquidity_rank":int(c["liquidity_rank"])})
    return pd.DataFrame(rows)

def stats(g):
    rs=g.ret.tolist()
    return {"n":len(rs),"mean":float(g.ret.mean()) if len(g) else None,
            "median":float(g.ret.median()) if len(g) else None,
            "profit_factor":pf(rs) if rs else None,
            "win_rate":float((g.ret>0).mean()) if len(g) else None}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=v13.load(a.indir)
    v48.EC=v48.XC=.0005;v49.EC=v49.XC=.0005
    summary={"schema":"PURE-BOX-SIMPLE-CORE-INSTRUMENT-CLASS-ATTRIBUTION-V52","results":{}}
    rows=[]
    for cap in (300,500):
        cs=v22.bottom20(v13.strict_signals(sig,cap,cal,idx,nxt,bm))
        cdf=pd.DataFrame(cs);cdf["class"]=cdf.symbol.astype(str).map(cls)
        candstats={}
        for k,g in cdf.groupby("class"):
            candstats[k]={"candidate_events":int(len(g)),"unique_symbols":int(g.symbol.nunique()),
                          "median_liquidity_rank":float(g.liquidity_rank.median())}
        idf=independent(cs,cal,bm)
        tradestats={k:stats(g) for k,g in idf.groupby("class")}
        ev=v49.run_events(cs,cal,bm)
        if len(ev):
            ev["class"]=ev.symbol.astype(str).map(cls)
            total_abs=float(ev.addon_slice_pnl.abs().sum())
            addstats={}
            for k,g in ev.groupby("class"):
                s=v49.stats(g)
                s["abs_pnl_share"]=float(g.addon_slice_pnl.abs().sum()/total_abs) if total_abs else None
                addstats[k]=s
        else:addstats={}
        scopes={
          "ALL":set(),
          "EXCLUDE_LEVERAGED_INVERSE":CLASSES["LEVERAGED_INVERSE_ETP"],
          "EXCLUDE_CRYPTO":CLASSES["CRYPTO_ETP"],
          "EXCLUDE_COMMODITY_VOL":CLASSES["COMMODITY_VOL_ETP"],
          "EXCLUDE_THEMATIC_SECTOR":CLASSES["THEMATIC_SECTOR_ETF"],
          "STOCK_ONLY":set().union(*CLASSES.values())
        }
        portfolios={}
        for label,ex in scopes.items():
            sub=[c for c in cs if str(c["symbol"]) not in ex]
            portfolios[label]={}
            for p in ("SKIP_OVERLAP","AGE3_ONLY_R250"):
                r=v48.run(sub,cal,bm,p)
                portfolios[label][p]=r
                rows.append({"rank_cap":cap,"scope":label,"policy":p,
                             "total_return":r["total_return"],"cagr":r["cagr"],
                             "max_drawdown":r["max_drawdown"],"daily_sharpe":r["daily_sharpe"],
                             "rolling_12m_min_return":r["rolling_12m_min_return"]})
        summary["results"][f"top{cap}"]={"candidate_class_stats":candstats,
                                           "independent_trade_stats":tradestats,
                                           "age3_addon_class_stats":addstats,
                                           "portfolio_ablations":portfolios}
    pd.DataFrame(rows).to_csv(out/"portfolio_ablations.csv",index=False)
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(pd.DataFrame(rows).to_string(index=False))
    print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
