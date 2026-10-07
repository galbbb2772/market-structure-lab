#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd

FRESH={300:23,500:24}
CELLS=("RESILIENT_STRONG","RESILIENT_WEAK","UNDERPERFORM_STRONG","UNDERPERFORM_WEAK")

def pf(s):
    x=pd.to_numeric(s,errors="coerce").dropna()
    gp=float(x[x>0].sum());gl=float(-x[x<0].sum())
    return gp/gl if gl>0 else None

def summarize(g):
    if g.empty:return None
    reasons=g.exit_reason.astype(str)
    return {
      "n":int(len(g)),
      "mean_trade":float(g.net_return.mean()),
      "median_trade":float(g.net_return.median()),
      "profit_factor":pf(g.net_return),
      "win_rate":float((g.net_return>0).mean()),
      "target_share":float(reasons.isin(["target","target_gap"]).mean()),
      "stop_share":float(reasons.isin(["stop","stop_gap"]).mean()),
      "max_hold_share":float(reasons.str.startswith("max_hold").mean()),
      "mean_holding_sessions":float(g.holding_sessions.mean()),
      "mean_mfe_return":float(g.mfe_return.mean()),
      "mean_mae_return":float(g.mae_return.mean()),
      "yearly_mean_trade":{str(int(y)):float(z.net_return.mean()) for y,z in g.groupby("year")},
      "yearly_pf":{str(int(y)):pf(z.net_return) for y,z in g.groupby("year")},
      "yearly_n":{str(int(y)):int(len(z)) for y,z in g.groupby("year")},
    }

def contrast(a,b):
    # a - b, where positive mean/target and negative stop is hypothesized.
    if a is None or b is None:return None
    return {
      "n_a":a["n"],"n_b":b["n"],
      "mean_trade_diff":a["mean_trade"]-b["mean_trade"],
      "target_share_diff":a["target_share"]-b["target_share"],
      "stop_share_diff":a["stop_share"]-b["stop_share"],
      "pf_a":a["profit_factor"],"pf_b":b["profit_factor"],
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--indir",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    src=Path(a.indir);out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

    ff=sorted(src.glob("**/resilience_exhaustion_features_*.csv.gz"))
    oo=sorted(src.glob("**/resilience_exhaustion_outcomes_*.csv.gz"))
    if len(ff)<8 or len(oo)<8:
        raise RuntimeError(f"expected 8 feature + 8 outcome shards, got {len(ff)} {len(oo)}")
    f=pd.concat([pd.read_csv(x) for x in ff],ignore_index=True).drop_duplicates("event_id",keep="last")
    o=pd.concat([pd.read_csv(x) for x in oo],ignore_index=True)
    f["period"]=f.year.map(lambda y:"discovery" if int(y)<=2022 else "validation")
    f.to_csv(out/"features.csv.gz",index=False,compression="gzip")
    o.to_csv(out/"outcomes.csv.gz",index=False,compression="gzip")

    cell_rows=[];contrast_rows=[];thresholds={}
    summary={"schema":"LARGE-RESILIENCE-EXHAUSTION-V2","thresholds":{},"cells":{},"contrasts":{}}

    for cap in (300,500):
        capkey=f"top{cap}"
        fb=f[(f.liquidity_rank<=cap)&(f.box_age_sessions<=FRESH[cap])].copy()
        disc=fb[fb.period=="discovery"]
        med=float(disc.rebound_from_low_box.median())
        thresholds[capkey]={"rebound_discovery_median":med,"fresh_age_max":FRESH[cap]}
        fb["resilience_state"]=fb.relative_resilience_5d.map(lambda x:"RESILIENT" if float(x)>=0 else "UNDERPERFORM")
        fb["rebound_state"]=fb.rebound_from_low_box.map(lambda x:"STRONG" if float(x)>=med else "WEAK")
        fb["cell"]=fb.resilience_state+"_"+fb.rebound_state
        z=o.merge(fb[["event_id","year","period","cell","relative_resilience_5d","rebound_from_low_box"]],on="event_id",how="inner")

        summary["cells"][capkey]={}
        summary["contrasts"][capkey]={}
        for target in (.60,.80):
            tk=f"t{int(target*100)}"
            summary["cells"][capkey][tk]={}
            summary["contrasts"][capkey][tk]={}
            t=z[z.target_fraction==target].copy()
            for period in ("discovery","validation"):
                pp=t[t.period==period]
                stats={}
                for cell in CELLS:
                    g=pp[pp.cell==cell]
                    s=summarize(g)
                    if s is not None:
                        stats[cell]=s
                        cell_rows.append({
                          "rank_cap":cap,"target_fraction":target,"period":period,"cell":cell,
                          **{k:v for k,v in s.items() if not k.startswith("yearly_")}
                        })
                summary["cells"][capkey][tk][period]=stats

                ctr={
                  "resilience_within_strong":contrast(stats.get("RESILIENT_STRONG"),stats.get("UNDERPERFORM_STRONG")),
                  "resilience_within_weak":contrast(stats.get("RESILIENT_WEAK"),stats.get("UNDERPERFORM_WEAK")),
                  "rebound_within_resilient":contrast(stats.get("RESILIENT_STRONG"),stats.get("RESILIENT_WEAK")),
                  "rebound_within_underperform":contrast(stats.get("UNDERPERFORM_STRONG"),stats.get("UNDERPERFORM_WEAK")),
                  "joint_best_vs_worst":contrast(stats.get("RESILIENT_STRONG"),stats.get("UNDERPERFORM_WEAK")),
                }
                summary["contrasts"][capkey][tk][period]=ctr
                for name,v in ctr.items():
                    if v is not None:
                        contrast_rows.append({
                          "rank_cap":cap,"target_fraction":target,"period":period,"contrast":name,**v
                        })

    summary["thresholds"]=thresholds
    pd.DataFrame(cell_rows).to_csv(out/"cell_summary.csv",index=False)
    pd.DataFrame(contrast_rows).to_csv(out/"contrast_summary.csv",index=False)

    # Compact support flags, descriptive only.
    support={}
    for cap in (300,500):
      ck=f"top{cap}";support[ck]={}
      for target in (.60,.80):
        tk=f"t{int(target*100)}";support[ck][tk]={}
        for name in (
          "resilience_within_strong","resilience_within_weak",
          "rebound_within_resilient","rebound_within_underperform","joint_best_vs_worst"
        ):
          signs=[]
          for period in ("discovery","validation"):
            v=summary["contrasts"][ck][tk][period].get(name)
            signs.append(None if v is None else {
              "mean_positive":v["mean_trade_diff"]>0,
              "target_positive":v["target_share_diff"]>0,
              "stop_negative":v["stop_share_diff"]<0,
              "n_a":v["n_a"],"n_b":v["n_b"],
            })
          support[ck][tk][name]={"discovery":signs[0],"validation":signs[1]}
    summary["support"]=support

    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps({"schema":summary["schema"],"thresholds":thresholds,"support":support},indent=2))

if __name__=="__main__":
    main()
