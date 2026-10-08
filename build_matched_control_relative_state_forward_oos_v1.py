#!/usr/bin/env python3
from __future__ import annotations

import json, math
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import mean, median

import build_market_state_sequence_v1 as seq
import research_task14_stage2_final_v1 as s2

ROOT=Path(__file__).resolve().parent
STATE=ROOT/"docs/data/market_state_box_v1.json"
OUT=ROOT/"docs/data/matched_control_relative_state_forward_oos_v1.json"

SCHEMA="MATCHED-CONTROL-RELATIVE-STATE-FORWARD-OOS-V1"
FREEZE="2026-10-06"
FREEZE_REFERENCE_COMMIT="cf5a0d9c92c28176bf33f98e6f68c574675a19f6"
FULL_FLAG="D_TO_BOTH_REBOUND_SCORE"
FEATURES=["ret20_pct","rv20_pct","net_liq_4w_pct","reserves_4w_pct","breadth_20d_pct","box_position","market_score"]
K=5
EXCLUSION=20
PRIMARY_N=20
MIN_MONTHS=12
MIN_CLUSTERS=8

def num(x):
    try:
        v=float(x); return v if math.isfinite(v) else None
    except Exception: return None

def add_year(d,years=1):
    try:return d.replace(year=d.year+years)
    except ValueError:return d.replace(month=2,day=28,year=d.year+years)

def load_existing():
    if not OUT.exists():
        return {
            "schema":SCHEMA,
            "freeze_reference_commit":FREEZE_REFERENCE_COMMIT,
            "frozen_through_market_date":FREEZE,
            "research_only":True,
            "observation_only":True,
            "production_effect":"none",
            "priority_tier":"T1_CORE_THESIS",
            "matching_spec":{"k":K,"exclusion_sessions":EXCLUSION,"features":FEATURES,"phase_rule":"exact MA200 phase when >=K controls; otherwise relax"},
            "events":[],
            "source_recompute_discrepancies":[],
        }
    d=json.loads(OUT.read_text(encoding="utf-8"))
    assert d.get("schema")==SCHEMA
    assert d.get("frozen_through_market_date")==FREEZE
    assert d.get("freeze_reference_commit")==FREEZE_REFERENCE_COMMIT
    return d

def prepare():
    src=json.loads(STATE.read_text(encoding="utf-8"))
    rows=[dict(r) for r in (src.get("daily") or [])]
    if len(rows)<2000: raise RuntimeError("Market State history missing/too short")
    rows=seq.add_dual(rows)
    rows,_=seq.enrich_sequence(rows)
    rows=s2.add_forward_and_regime(rows)
    return rows

def onset_indices(rows):
    xs=seq.event_onsets(rows,FULL_FLAG)
    out=[]
    bydate={r["date"]:i for i,r in enumerate(rows)}
    for r in xs:
        i=r.get("_i")
        if not isinstance(i,int): i=bydate.get(r.get("date"))
        if isinstance(i,int): out.append(i)
    return sorted(set(out))

def control_pool(rows,event_i,onsets):
    banned=set()
    for e in onsets:
        if e>event_i: continue
        banned.update(range(max(0,e-EXCLUSION),min(len(rows),e+EXCLUSION+1)))
    # 20D outcome must already be observable at the event date.
    return [
        i for i,r in enumerate(rows)
        if i<=event_i-20 and i not in banned and num(r.get("final_fwd_20d")) is not None
    ]

def choose_controls(rows,event_i,onsets):
    er=rows[event_i]
    pool=control_pool(rows,event_i,onsets)
    if len(pool)<K: raise RuntimeError(f"insufficient point-in-time controls for {er['date']}: {len(pool)}")
    mu={};sd={}
    for f in FEATURES:
        vals=[num(rows[i].get(f)) for i in pool]
        vals=[v for v in vals if v is not None]
        mu[f]=mean(vals) if vals else 0.0
        if len(vals)>1:
            var=sum((v-mu[f])**2 for v in vals)/(len(vals)-1)
            st=math.sqrt(var)
        else: st=1.0
        sd[f]=st if st>1e-12 else 1.0
    phase=er.get("ma200_phase_final")
    phased=[i for i in pool if phase is None or rows[i].get("ma200_phase_final")==phase]
    use=phased if len(phased)>=K else pool
    relaxed=len(phased)<K
    scored=[]
    for i in use:
        diffs=[]
        for f in FEATURES:
            a,b=num(er.get(f)),num(rows[i].get(f))
            if a is not None and b is not None:
                diffs.append(((a-b)/sd[f])**2)
        if len(diffs)>=5:
            scored.append((math.sqrt(sum(diffs)/len(diffs)),i,len(diffs)))
    scored.sort()
    chosen=scored[:K]
    if len(chosen)<K: raise RuntimeError(f"insufficient scored controls for {er['date']}: {len(chosen)}")
    controls=[]
    for dist,i,nf in chosen:
        r=rows[i]
        controls.append({
            "date":r["date"],
            "distance":round(dist,8),
            "features_used":nf,
            "ma200_phase":r.get("ma200_phase_final"),
            "fwd_10d_pct":num(r.get("final_fwd_10d")),
            "fwd_20d_pct":num(r.get("final_fwd_20d")),
        })
    c10=[c["fwd_10d_pct"] for c in controls if c["fwd_10d_pct"] is not None]
    c20=[c["fwd_20d_pct"] for c in controls if c["fwd_20d_pct"] is not None]
    return {
        "phase":phase,
        "phase_relaxed":relaxed,
        "control_pool_n":len(pool),
        "controls":controls,
        "control_mean_10d_pct":None if not c10 else round(mean(c10),6),
        "control_mean_20d_pct":None if not c20 else round(mean(c20),6),
    }

def event_snapshot(rows,i,onsets):
    r=rows[i]
    m=choose_controls(rows,i,onsets)
    return {
        "event_date":r["date"],
        "first_seen_at":datetime.now(timezone.utc).isoformat(),
        "first_seen_market_date":rows[-1]["date"],
        "event_features":{f:num(r.get(f)) for f in FEATURES},
        **m,
        "mature_10d":False,
        "event_fwd_10d_pct":None,
        "lift_10d_pp":None,
        "mature_20d":False,
        "event_fwd_20d_pct":None,
        "lift_20d_pp":None,
    }

def update_outcomes(e,r):
    f10=num(r.get("final_fwd_10d"))
    f20=num(r.get("final_fwd_20d"))
    if f10 is not None:
        e["mature_10d"]=True
        if e.get("event_fwd_10d_pct") is None:
            e["event_fwd_10d_pct"]=round(f10,6)
            cm=e.get("control_mean_10d_pct")
            e["lift_10d_pp"]=None if cm is None else round(f10-cm,6)
    if f20 is not None:
        e["mature_20d"]=True
        if e.get("event_fwd_20d_pct") is None:
            e["event_fwd_20d_pct"]=round(f20,6)
            cm=e.get("control_mean_20d_pct")
            e["lift_20d_pp"]=None if cm is None else round(f20-cm,6)

def cluster_count(ds,market_index,gap=20):
    xs=sorted(market_index[d] for d in ds if d in market_index)
    if not xs:return 0
    n=1;last=xs[0]
    for x in xs[1:]:
        if x-last>gap:n+=1
        last=x
    return n

def summary(events,rows,discrepancies):
    mature10=[e for e in events if e.get("mature_10d") and e.get("lift_10d_pp") is not None]
    mature20=[e for e in events if e.get("mature_20d") and e.get("lift_20d_pp") is not None]
    market_index={r["date"]:i for i,r in enumerate(rows)}
    clusters=cluster_count([e["event_date"] for e in mature20],market_index)
    calendar=False
    if events:
        first=date.fromisoformat(min(e["event_date"] for e in events))
        last=date.fromisoformat(rows[-1]["date"])
        calendar=last>=add_year(first)
    ready=len(mature20)>=PRIMARY_N and calendar and clusters>=MIN_CLUSTERS and not discrepancies
    def agg(es,key):
        v=[float(e[key]) for e in es if e.get(key) is not None]
        return {
            "n":len(v),
            "mean_lift_pp":None if not v else round(mean(v),6),
            "median_lift_pp":None if not v else round(median(v),6),
            "positive_lift_pct":None if not v else round(100*sum(x>0 for x in v)/len(v),2),
        }
    return {
        "forward_event_count":len(events),
        "mature_10d_event_count":len(mature10),
        "mature_20d_event_count":len(mature20),
        "independent_cluster_count_20sessions":clusters,
        "calendar_12m_ready":calendar,
        "event_count_ready":len(mature20)>=PRIMARY_N,
        "cluster_gate_ready":clusters>=MIN_CLUSTERS,
        "discrepancy_gate_ready":not discrepancies,
        "ready_for_preregistered_review":ready,
        "ten_day":agg(mature10,"lift_10d_pp"),
        "twenty_day":agg(mature20,"lift_20d_pp"),
    }

def main():
    rows=prepare(); onsets=onset_indices(rows)
    future=[i for i in onsets if rows[i]["date"]>FREEZE]
    out=load_existing()
    existing={e["event_date"]:e for e in out.get("events",[])}
    discrepancies=list(out.get("source_recompute_discrepancies",[]))
    for i in future:
        d=rows[i]["date"]
        if d not in existing:
            existing[d]=event_snapshot(rows,i,onsets)
        else:
            # Event identity is frozen. Only outcomes may mature.
            frozen=existing[d]
            current={f:num(rows[i].get(f)) for f in FEATURES}
            diffs={}
            for f,v in current.items():
                old=(frozen.get("event_features") or {}).get(f)
                if old is None or v is None:
                    if old!=v: diffs[f]={"frozen":old,"current":v}
                elif abs(float(old)-float(v))>1e-8:
                    diffs[f]={"frozen":old,"current":v}
            if diffs and not any(x.get("event_date")==d and x.get("fields")==diffs for x in discrepancies):
                discrepancies.append({"event_date":d,"fields":diffs})
        update_outcomes(existing[d],rows[i])
    events=sorted(existing.values(),key=lambda e:e["event_date"])
    out.update({
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "latest_market_date":rows[-1]["date"],
        "events":events,
        "source_recompute_discrepancies":discrepancies,
        "summary":summary(events,rows,discrepancies),
        "promotion_gate":{
            "minimum_mature_20d_events":PRIMARY_N,
            "minimum_calendar_months":MIN_MONTHS,
            "minimum_independent_clusters":MIN_CLUSTERS,
            "automatic_promotion":False,
            "note":"Passing permits only a separate preregistered review."
        },
        "warnings":[
            "Historical development events through 2026-10-06 are excluded.",
            "Control sets are locked at first observation and never reselected.",
            "No result changes production automatically."
        ]
    })
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(out["summary"],ensure_ascii=False,indent=2))

if __name__=="__main__":main()
