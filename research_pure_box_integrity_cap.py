#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, statistics
from pathlib import Path
import pandas as pd
import research_pure_box_integrity_v1 as core

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--indir",required=True)
    ap.add_argument("--outdir",required=True)
    ap.add_argument("--cap",type=int,required=True,choices=[300,500])
    a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

    bars,sig,cal,idx,nxt,bm,bmd=core.load(a.indir)
    cap=a.cap
    breadth=core.build_breadth(bars,cap)
    bmap={r["date"]:r for r in breadth.to_dict("records")}
    cs=core.build_candidates(sig,cap,nxt,bm,bmd,idx,bmap)
    cdf=pd.DataFrame([{k:v for k,v in c.items() if k!="_breadth"} for c in cs])

    rows=[];featrows=[]
    result={}
    for y in core.YEARS:
        train=cdf[cdf.signal_date.str[:4].astype(int)<y]
        test=[c for c in cs if int(c["signal_date"][:4])==y]
        if train.empty or not test:continue
        th=core.thresholds(train)
        for sleeve in ("fresh","wide_fresh"):
            base=[c for c in test if core.sleeve_ok(c,th,sleeve)]
            if base:
                fdf=pd.DataFrame([{**{k:v for k,v in c.items() if k!="_breadth"},
                                  **{f"br_{k}":v for k,v in (c["_breadth"] or {}).items()}} for c in base])
                featrows.append({
                    "rank_cap":cap,"year":y,"sleeve":sleeve,"n":len(fdf),
                    "mean_touch_episodes":float(fdf.post_detection_lower_touch_episodes.mean()),
                    "mean_touch_days_last10":float(fdf.touch_days_last10.mean()),
                    "mean_bottom_streak":float(fdf.lower_zone_close_streak.mean()),
                    "mean_d5_ma50":float(fdf.br_d5_ma50.mean()),
                    "mean_d5_ret20breadth":float(fdf.br_d5_ret20breadth.mean()),
                    "mean_d5_newlow":float(fdf.br_d5_newlow.mean())
                })
            for gate in core.GATES:
                filt=[c for c in base if core.gate_ok(c,gate)]
                res=core.run(filt,cal,bmd,f"{y}-01-01",f"{y}-12-31")
                rows.append({"rank_cap":cap,"year":y,"sleeve":sleeve,"gate":gate,
                             "eligible_candidates":len(filt),**res})

    rdf=pd.DataFrame(rows)
    rdf.to_csv(out/f"annual_integrity_top{cap}.csv",index=False)
    pd.DataFrame(featrows).to_csv(out/f"feature_year_receipt_top{cap}.csv",index=False)

    result={}
    for sleeve in ("fresh","wide_fresh"):
        result[sleeve]={}
        for gate in core.GATES:
            g=rdf[(rdf.sleeve==sleeve)&(rdf.gate==gate)].sort_values("year")
            comp=1.;vals=[]
            for r in g.to_dict("records"):
                comp*=1+float(r["total_return"]);vals.append(float(r["total_return"]))
            result[sleeve][gate]={
                "compounded_walk_forward_return":comp-1,
                "positive_years":sum(v>0 for v in vals),"years":len(vals),
                "avg_year_return":statistics.mean(vals),"avg_sharpe":float(g.sharpe.mean()),
                "avg_exposure":float(g.avg_exposure.mean()),"total_trades":int(g.trades.sum()),
                "yearly":{str(int(r.year)):float(r.total_return) for r in g.itertuples()}
            }
    summary={"schema":"PURE-BOX-INTEGRITY-V1-CAP","rank_cap":cap,"lanes":result}
    (out/f"summary_top{cap}.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))

if __name__=="__main__":main()
