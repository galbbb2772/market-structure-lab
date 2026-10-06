#!/usr/bin/env python3
from __future__ import annotations

import json, math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

import numpy as np

import build_market_state_sequence_v1 as seq
import research_task14_stage2_final_v1 as s2

ROOT=Path(__file__).resolve().parent
BOX=ROOT/"docs/data/pruned16_v2/market_state_box_v1.json"
AUDIT=ROOT/"docs/data/pruned16_v2/market_state_sequence_event_audit_v1.json"
OUT=ROOT/"docs/data/pruned16_v2/matched_control_robustness_v1.json"
REPORT=ROOT/"research/pruned16_v2_matched_control_robustness/REPORT.md"

H=(5,10,20)
KS=(3,5,10)
EXCLS=(10,20,30)
BASE_FEATURES=["ret20_pct","rv20_pct","net_liq_4w_pct","reserves_4w_pct","breadth_20d_pct","box_position","market_score"]
NO_SCORE=[x for x in BASE_FEATURES if x!="market_score"]

def num(x):
    try:
        v=float(x); return v if math.isfinite(v) else None
    except Exception: return None

def qtile(vals,p):
    a=sorted(v for v in (num(x) for x in vals) if v is not None)
    if not a: return None
    z=(len(a)-1)*p; i=int(z); j=min(i+1,len(a)-1); f=z-i
    return a[i]+(a[j]-a[i])*f

def prepare():
    box=json.loads(BOX.read_text(encoding="utf-8"))
    audit=json.loads(AUDIT.read_text(encoding="utf-8"))
    rows=[dict(r) for r in box["daily"]]
    rows=seq.add_dual(rows)
    rows,_=seq.enrich_sequence(rows)
    rows=s2.add_forward_and_regime(rows)
    by_date={r["date"]:i for i,r in enumerate(rows)}
    event_dates=[e["date"] for e in audit["events"]]
    event_ix=[by_date[d] for d in event_dates]
    assert len(event_ix)==11,(len(event_ix),event_dates)
    return rows,event_ix,event_dates

def match(rows,event_ix,features,k,excl):
    banned=set()
    for e in event_ix:
        banned.update(range(max(0,e-excl),min(len(rows),e+excl+1)))
    candidates=[i for i,r in enumerate(rows) if i not in banned and num(r.get("final_fwd_20d")) is not None]
    mu,sd={},{}
    for f in features:
        vals=[num(rows[i].get(f)) for i in candidates]
        vals=[v for v in vals if v is not None]
        mu[f]=mean(vals) if vals else 0.0
        s=math.sqrt(sum((v-mu[f])**2 for v in vals)/max(1,len(vals)-1)) if vals else 1.0
        sd[f]=s if s>1e-12 else 1.0
    recs=[]; used=[]
    for e in event_ix:
        er=rows[e]; phase=er.get("ma200_phase_final")
        pool=[i for i in candidates if phase is None or rows[i].get("ma200_phase_final")==phase]
        relaxed=False
        if len(pool)<k:
            pool=candidates[:]; relaxed=True
        scored=[]
        for i in pool:
            diffs=[]
            for f in features:
                a,b=num(er.get(f)),num(rows[i].get(f))
                if a is not None and b is not None:
                    diffs.append(((a-b)/sd[f])**2)
            # preserve Stage2 spirit: require at least 5 features when possible,
            # otherwise all available features for no-score set.
            minf=min(5,len(features))
            if len(diffs)>=minf:
                scored.append((math.sqrt(sum(diffs)/len(diffs)),i,len(diffs)))
        scored.sort()
        chosen=scored[:k]
        used += [i for _,i,_ in chosen]
        rec={"event_date":er["date"],"year":int(er["date"][:4]),"phase":phase,"phase_relaxed":relaxed,
             "controls":[{"date":rows[i]["date"],"distance":round(d,4),"features_used":nf} for d,i,nf in chosen]}
        for h in H:
            ev=num(er.get(f"final_fwd_{h}d"))
            cvs=[num(rows[i].get(f"final_fwd_{h}d")) for _,i,_ in chosen]
            cvs=[v for v in cvs if v is not None]
            cm=mean(cvs) if cvs else None
            rec[f"event_{h}d_pct"]=None if ev is None else round(ev,4)
            rec[f"control_mean_{h}d_pct"]=None if cm is None else round(cm,4)
            rec[f"lift_{h}d_pp"]=None if ev is None or cm is None else round(ev-cm,4)
        recs.append(rec)
    agg={}
    for h in H:
        vals=[num(r.get(f"lift_{h}d_pp")) for r in recs]; vals=[v for v in vals if v is not None]
        agg[f"{h}d"]={
            "n":len(vals),
            "mean_lift_pp":None if not vals else round(mean(vals),4),
            "median_lift_pp":None if not vals else round(median(vals),4),
            "positive_pct":None if not vals else round(100*sum(v>0 for v in vals)/len(vals),2),
            "p10_pp":None if not vals else round(qtile(vals,.1),4),
            "p90_pp":None if not vals else round(qtile(vals,.9),4),
        }
    return {
        "k":k,"exclusion_sessions":excl,"features":features,
        "event_count":len(recs),"unique_control_dates":len(set(used)),
        "control_reuse_count":len(used)-len(set(used)),"aggregate":agg,"records":recs
    }

def center_secondary(center):
    recs=center["records"]
    loo={}
    for h in H:
        vals=[]
        for drop in range(len(recs)):
            x=[num(r.get(f"lift_{h}d_pp")) for i,r in enumerate(recs) if i!=drop]
            x=[v for v in x if v is not None]
            vals.append({"dropped":recs[drop]["event_date"],"mean_lift_pp":round(mean(x),4)})
        ms=[x["mean_lift_pp"] for x in vals]
        loo[f"{h}d"]={"min":min(ms),"median":round(median(ms),4),"max":max(ms),"records":vals}

    # 20-session clusters are frozen from the V2 Stage3 audit.
    clusters=[
        ["2019-06-04"],
        ["2022-01-28"],
        ["2022-05-13","2022-05-23","2022-06-07","2022-07-01","2022-07-12"],
        ["2022-09-28","2022-10-13","2022-10-25"],
        ["2023-01-04"],
    ]
    by={r["event_date"]:r for r in recs}
    cluster={}
    for h in H:
        vals=[]; records=[]
        for c in clusters:
            xs=[num(by[d].get(f"lift_{h}d_pp")) for d in c if d in by]
            xs=[v for v in xs if v is not None]
            if xs:
                v=mean(xs); vals.append(v); records.append({"dates":c,"mean_lift_pp":round(v,4)})
        cluster[f"{h}d"]={"n_clusters":len(vals),"mean_lift_pp":round(mean(vals),4),"median_lift_pp":round(median(vals),4),"records":records}

    yearly={}
    years=sorted(set(r["year"] for r in recs))
    for h in H:
        ym={}
        for y in years:
            xs=[num(r.get(f"lift_{h}d_pp")) for r in recs if r["year"]==y]
            xs=[v for v in xs if v is not None]
            if xs: ym[str(y)]=round(mean(xs),4)
        yearly[f"{h}d"]={"year_means":ym,"equal_year_mean_lift_pp":round(mean(ym.values()),4)}

    return {"leave_one_event":loo,"cluster_weighted_20session":cluster,"equal_year_weighted":yearly}

def grid_summary(cells):
    out={}
    for h in H:
        vals=[num(c["aggregate"][f"{h}d"]["mean_lift_pp"]) for c in cells]
        vals=[v for v in vals if v is not None]
        out[f"{h}d"]={
            "cells":len(vals),
            "positive_cells":sum(v>0 for v in vals),
            "positive_share_pct":round(100*sum(v>0 for v in vals)/len(vals),2),
            "min_mean_lift_pp":round(min(vals),4),
            "median_mean_lift_pp":round(median(vals),4),
            "max_mean_lift_pp":round(max(vals),4),
        }
    return out

def classify(base_grid,noscore_grid,secondary):
    b10=base_grid["10d"]; b20=base_grid["20d"]
    n10=noscore_grid["10d"]; n20=noscore_grid["20d"]
    loo10=secondary["leave_one_event"]["10d"]["min"]
    loo20=secondary["leave_one_event"]["20d"]["min"]
    if b10["positive_cells"]==9 and b20["positive_cells"]==9 and loo10>0 and loo20>0:
        return "ROBUST_POSITIVE"
    if b10["positive_cells"]>=7 and b20["positive_cells"]>=7:
        return "BROADLY_POSITIVE_BUT_FRAGILE"
    if b10["positive_cells"]<7 or b20["positive_cells"]<7 or np.sign(n10["median_mean_lift_pp"])!=np.sign(b10["median_mean_lift_pp"]) or np.sign(n20["median_mean_lift_pp"])!=np.sign(b20["median_mean_lift_pp"]):
        return "METHOD_SENSITIVE"
    if b10["median_mean_lift_pp"]<=0 and b20["median_mean_lift_pp"]<=0:
        return "NO_EDGE"
    return "MIXED"

def main():
    rows,event_ix,event_dates=prepare()
    base=[]; noscore=[]
    for excl in EXCLS:
        for k in KS:
            base.append(match(rows,event_ix,BASE_FEATURES,k,excl))
            noscore.append(match(rows,event_ix,NO_SCORE,k,excl))
    center=next(x for x in base if x["k"]==5 and x["exclusion_sessions"]==20)
    secondary=center_secondary(center)
    bg=grid_summary(base); ng=grid_summary(noscore)
    status=classify(bg,ng,secondary)
    out={
        "schema":"PRUNED16-V2-MATCHED-CONTROL-ROBUSTNESS-V1",
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "research_only":True,"production_effect":"none","forward_oos_effect":"none",
        "event_dates":event_dates,
        "preregistration":"research/pruned16_v2_matched_control_robustness/PREREGISTRATION.md",
        "base_feature_grid":{"features":BASE_FEATURES,"summary":bg,"cells":base},
        "no_market_score_grid":{"features":NO_SCORE,"summary":ng,"cells":noscore},
        "center_cell":{"k":5,"exclusion_sessions":20,"result":center},
        "secondary_robustness":secondary,
        "classification":status,
        "guardrails":{
            "thresholds_optimized":False,
            "best_cell_selected":False,
            "historical_only":True,
            "forward_oos_required_for_promotion":True
        }
    }
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    md=[
        "# PRUNED16 V2 Matched-Control Robustness",
        "",
        f"Classification: **{status}**",
        "",
        "## Base-feature grid",
        "",
        "| Horizon | Positive cells | Min mean lift | Median mean lift | Max mean lift |",
        "|---|---:|---:|---:|---:|",
    ]
    for h in H:
        z=bg[f"{h}d"]; md.append(f"| {h}D | {z['positive_cells']}/9 | {z['min_mean_lift_pp']:+.4f} pp | {z['median_mean_lift_pp']:+.4f} pp | {z['max_mean_lift_pp']:+.4f} pp |")
    md += ["","## Grid without Market Score","",
           "| Horizon | Positive cells | Min mean lift | Median mean lift | Max mean lift |",
           "|---|---:|---:|---:|---:|"]
    for h in H:
        z=ng[f"{h}d"]; md.append(f"| {h}D | {z['positive_cells']}/9 | {z['min_mean_lift_pp']:+.4f} pp | {z['median_mean_lift_pp']:+.4f} pp | {z['max_mean_lift_pp']:+.4f} pp |")
    md += ["","## Center cell K=5 / exclusion=20",""]
    for h in H:
        z=center["aggregate"][f"{h}d"]
        lo=secondary["leave_one_event"][f"{h}d"]
        cl=secondary["cluster_weighted_20session"][f"{h}d"]
        yr=secondary["equal_year_weighted"][f"{h}d"]
        md.append(f"- {h}D: mean {z['mean_lift_pp']:+.4f} pp; median {z['median_lift_pp']:+.4f} pp; positive {z['positive_pct']:.2f}%; LOO mean range [{lo['min']:+.4f}, {lo['max']:+.4f}] pp; cluster-weighted {cl['mean_lift_pp']:+.4f} pp; equal-year {yr['equal_year_mean_lift_pp']:+.4f} pp.")
    md += ["","## Guardrail","",
           "Historical robustness only. No grid cell is selected for production and no Forward-OOS definition is changed."]
    REPORT.write_text("\n".join(md)+"\n",encoding="utf-8")
    print(json.dumps({"classification":status,"base_grid":bg,"no_score_grid":ng,"center":center["aggregate"],"secondary":secondary},ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
