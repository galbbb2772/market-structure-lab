"""Task 1/4 Stage-2 Research V1.

Post-discovery diagnostic suite for Market State Sequence / RMD research.
Runs ten research blocks without changing MAIN or any existing frozen OOS ledger:
1) regime conditioning, 2) leave-one-year-out incl. 2022 removal,
3) placebo random-date tests, 4) order-necessity/path tests,
5) continuous sequence maturity score, 6) RMD x DUAL-severity surface,
7) competing-risk path test, 8) entry/exit timing matrix,
9) cross-market confirmation, 10) historical analogs.

All findings are diagnostic-only and require separate preregistration + Forward OOS
before any rule can be promoted.
"""
from __future__ import annotations

import csv
import io
import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

import requests
import build_market_state_sequence_v1 as seq

ROOT = Path(__file__).resolve().parent
BOX = ROOT / "docs/data/market_state_box_v1.json"
AUDIT = ROOT / "docs/data/market_state_sequence_event_audit_v1.json"
RMD = ROOT / "docs/data/residual_mean_reversion_distance_v1.json"
OUT = ROOT / "docs/data/task14_stage2_research_v1.json"
H = (1, 3, 5, 10, 20)
SEED = 140214


def num(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def clamp(x, lo=0.0, hi=1.0):
    if x is None:
        return None
    return max(lo, min(hi, x))


def qtile(vals, p):
    a = sorted(v for v in (num(x) for x in vals) if v is not None)
    if not a:
        return None
    z = (len(a)-1)*p
    i = int(z); j = min(i+1, len(a)-1); f = z-i
    return a[i] + (a[j]-a[i])*f


def rankdata(vals):
    pairs = sorted((v, i) for i, v in enumerate(vals))
    out = [0.0]*len(vals); p=0
    while p < len(pairs):
        q=p+1
        while q<len(pairs) and pairs[q][0]==pairs[p][0]: q+=1
        r=((p+1)+q)/2.0
        for _,i in pairs[p:q]: out[i]=r
        p=q
    return out


def pearson(x,y):
    if len(x)<3: return None
    mx,my=mean(x),mean(y)
    dx=[v-mx for v in x]; dy=[v-my for v in y]
    den=math.sqrt(sum(v*v for v in dx)*sum(v*v for v in dy))
    if not den: return None
    return sum(a*b for a,b in zip(dx,dy))/den


def spearman_pairs(items, xkey, ykey):
    pairs=[]
    for e in items:
        x=num(e.get(xkey)); y=num(e.get(ykey))
        if x is not None and y is not None: pairs.append((x,y))
    if len(pairs)<3: return {"n":len(pairs),"rho":None}
    rho=pearson(rankdata([x for x,_ in pairs]), rankdata([y for _,y in pairs]))
    return {"n":len(pairs),"rho":None if rho is None else round(rho,4)}


def add_forward(rows):
    closes=[num(r.get("sp500_close")) for r in rows]
    for i,r in enumerate(rows):
        c0=closes[i]
        for h in H:
            if c0 is None or i+h>=len(rows) or closes[i+h] is None:
                r[f"s2_fwd_{h}d"]=None
            else:
                r[f"s2_fwd_{h}d"]=100.0*(closes[i+h]/c0-1.0)
        for h in (10,20):
            fut=[c for c in closes[i+1:min(len(rows),i+h+1)] if c is not None]
            if c0 is None or not fut:
                r[f"s2_mfe_{h}d"]=None; r[f"s2_mae_{h}d"]=None
            else:
                rr=[100.0*(c/c0-1.0) for c in fut]
                r[f"s2_mfe_{h}d"]=max(rr); r[f"s2_mae_{h}d"]=min(rr)
    return rows


def summary(sample):
    out={"n":len(sample)}
    for h in H:
        v=[num(r.get(f"s2_fwd_{h}d")) for r in sample]
        v=[x for x in v if x is not None]
        out[f"{h}d"]={"n":len(v)} if not v else {
            "n":len(v),"mean_pct":round(mean(v),4),"median_pct":round(median(v),4),
            "positive_pct":round(100*sum(x>0 for x in v)/len(v),2),
            "p10_pct":round(qtile(v,.10),4),"p90_pct":round(qtile(v,.90),4)
        }
    for h in (10,20):
        mfe=[num(r.get(f"s2_mfe_{h}d")) for r in sample]; mfe=[x for x in mfe if x is not None]
        mae=[num(r.get(f"s2_mae_{h}d")) for r in sample]; mae=[x for x in mae if x is not None]
        out[f"mfe_{h}d_mean_pct"]=None if not mfe else round(mean(mfe),4)
        out[f"mae_{h}d_mean_pct"]=None if not mae else round(mean(mae),4)
    return out


def moving_average(vals,n):
    out=[None]*len(vals); q=[]; s=0.0
    for i,v in enumerate(vals):
        q.append(v)
        if v is not None: s+=v
        if len(q)>n:
            old=q.pop(0)
            if old is not None: s-=old
        if len(q)==n and all(x is not None for x in q): out[i]=s/n
    return out


def enrich_regime(rows):
    closes=[num(r.get("sp500_close")) for r in rows]
    ma200=moving_average(closes,200)
    rets=[None]
    for i in range(1,len(closes)):
        a,b=closes[i-1],closes[i]
        rets.append(None if a in (None,0) or b is None else b/a-1.0)
    for i,r in enumerate(rows):
        m=ma200[i]; c=closes[i]
        slope=None
        if i>=20 and m is not None and ma200[i-20] not in (None,0):
            slope=100*(m/ma200[i-20]-1.0)
        phase=None
        if c is not None and m is not None and slope is not None:
            if c>=m and slope>0: phase="bull_rising"
            elif c>=m and slope<=0: phase="bull_weakening"
            elif c<m and slope<0: phase="bear_falling"
            else: phase="bear_recovery"
        r["s2_phase"]=phase
        if i>=20:
            w=[x for x in rets[i-19:i+1] if x is not None]
            if len(w)==20:
                mu=mean(w); var=sum((x-mu)**2 for x in w)/(len(w)-1)
                rv=math.sqrt(var)*math.sqrt(252)*100
                r["s2_rv20_pct"]=rv
                r["s2_vol_regime"]="high_ge20" if rv>=20 else "low_lt20"
    return rows


def event_rows(rows):
    return seq.event_onsets(rows,"D_TO_BOTH_REBOUND_SCORE")


def regime_test(events):
    out={}
    for key in ("s2_phase","s2_vol_regime"):
        vals=sorted(set(r.get(key) for r in events if r.get(key)))
        out[key]={v:summary([r for r in events if r.get(key)==v]) for v in vals}
    return out


def loyo_test(events, rmd_by_date):
    years=sorted(set(int(r["date"][:4]) for r in events))
    tests={}
    for y in years:
        keep=[r for r in events if int(r["date"][:4])!=y]
        pseudo=[]
        for r in keep:
            q={"rmd3":rmd_by_date.get(r["date"],{}).get("rmd3"),"fwd10":r.get("s2_fwd_10d")}
            pseudo.append(q)
        tests[f"exclude_{y}"]={"sequence":summary(keep),"rmd3_vs_10d":spearman_pairs(pseudo,"rmd3","fwd10")}
    keep=[r for r in events if not r["date"].startswith("2022-")]
    pseudo=[{"rmd3":rmd_by_date.get(r["date"],{}).get("rmd3"),"fwd10":r.get("s2_fwd_10d")} for r in keep]
    tests["exclude_2022_focus"]={"sequence":summary(keep),"rmd3_vs_10d":spearman_pairs(pseudo,"rmd3","fwd10")}
    return tests


def placebo_test(events, rows, rounds=10000):
    rng=random.Random(SEED)
    n=len(events)
    valid=[r for r in rows if num(r.get("s2_fwd_20d")) is not None]
    out={"rounds":rounds,"sample_n":n,"seed":SEED,"horizons":{}}
    for h in (5,10,20):
        actual=mean([r[f"s2_fwd_{h}d"] for r in events if num(r.get(f"s2_fwd_{h}d")) is not None])
        sims=[]
        for _ in range(rounds):
            s=rng.sample(valid,n)
            sims.append(mean(r[f"s2_fwd_{h}d"] for r in s))
        ge=sum(x>=actual for x in sims)
        out["horizons"][str(h)]={
            "actual_mean_pct":round(actual,4),
            "placebo_mean_pct":round(mean(sims),4),
            "placebo_p95_pct":round(qtile(sims,.95),4),
            "empirical_one_sided_p":round((ge+1)/(rounds+1),5),
            "actual_percentile_vs_placebo":round(100*sum(x<=actual for x in sims)/rounds,2),
        }
    return out


def order_test(episodes, rows, by_date):
    recs=[]
    for e in episodes:
        dates=[e.get("first_breadth_low"),e.get("first_box_bottom"),e.get("first_breadth_rebound"),e.get("first_score_recovery_after_rebound")]
        if any(x is None for x in dates): continue
        low,box,reb,score=dates
        strict=low<=box<=reb<=score
        box_before_low=box<low
        box_after_rebound=box>reb
        r=by_date.get(score)
        if r is None: continue
        recs.append({"episode_id":e.get("episode_id"),"score_date":score,"low":low,"box":box,"rebound":reb,
                     "strict_low_box_rebound_score":strict,"box_before_low":box_before_low,"box_after_rebound":box_after_rebound,
                     **{f"s2_fwd_{h}d":r.get(f"s2_fwd_{h}d") for h in H},
                     "s2_mfe_10d":r.get("s2_mfe_10d"),"s2_mae_10d":r.get("s2_mae_10d"),
                     "s2_mfe_20d":r.get("s2_mfe_20d"),"s2_mae_20d":r.get("s2_mae_20d")})
    return {
        "all_complete_milestone_episodes":summary(recs),
        "strict_order":summary([r for r in recs if r["strict_low_box_rebound_score"]]),
        "non_strict_order":summary([r for r in recs if not r["strict_low_box_rebound_score"]]),
        "box_before_low":summary([r for r in recs if r["box_before_low"]]),
        "box_after_rebound":summary([r for r in recs if r["box_after_rebound"]]),
        "records":recs,
    }


def maturity_score(r):
    ds=num(r.get("days_since_dual"))
    dual=0.0 if ds is None or ds>10 else clamp((10-ds)/10.0)
    breadth=num(r.get("breadth_20d_pct")); stress=None if breadth is None else clamp((30.0-breadth)/20.0)
    bp=num(r.get("box_position")); box=None if bp is None else clamp((0.5-bp)/0.5)
    trough=num(r.get("breadth_trough_since_dual"))
    rec=None if breadth is None or trough is None else clamp((breadth-trough)/25.0)
    d3=num(r.get("market_score_d3")); score=None if d3 is None else clamp(d3/5.0)
    comps=[x for x in (dual,stress,box,rec,score) if x is not None]
    return None if not comps else 100*mean(comps)


def continuous_score_test(rows):
    active=[]
    for r in rows:
        s=maturity_score(r); r["s2_maturity_score"]=s
        if num(s) is not None and (r.get("recent_dual_10d") or (num(r.get("days_since_dual")) is not None and r.get("days_since_dual")<=20)):
            active.append(r)
    rho={str(h):spearman_pairs(active,"s2_maturity_score",f"s2_fwd_{h}d") for h in (5,10,20)}
    buckets={}
    for lo in (0,20,40,60,80):
        hi=lo+20
        sample=[r for r in active if num(r.get("s2_maturity_score")) is not None and lo<=r["s2_maturity_score"]<(hi if hi<100 else 100.0001)]
        buckets[f"{lo}_{hi}"]=summary(sample)
    return {"definition":"equal-weight current-information components: recency of DUAL, breadth stress, box depth, breadth rebound distance, positive score D3 recovery; each clipped 0..1","active_n":len(active),"spearman":rho,"buckets":buckets}


def rmd_severity_surface(events, rmd_by_date, audit_by_date):
    recs=[]
    for r in events:
        d=r["date"]; a=audit_by_date.get(d,{}); start=a.get("dual_episode_start")
        sev=None
        if start:
            # severity is computed from episode-start row in caller-enriched map later
            sev=a.get("_severity")
        recs.append({"date":d,"rmd3":rmd_by_date.get(d,{}).get("rmd3"),"severity":sev,
                     **{f"s2_fwd_{h}d":r.get(f"s2_fwd_{h}d") for h in H},
                     "s2_mfe_10d":r.get("s2_mfe_10d"),"s2_mae_10d":r.get("s2_mae_10d"),
                     "s2_mfe_20d":r.get("s2_mfe_20d"),"s2_mae_20d":r.get("s2_mae_20d")})
    vals=[num(x["rmd3"]) for x in recs if num(x["rmd3"]) is not None]
    med=None if not vals else median(vals)
    cells={}
    for rmd_band in ("low","high"):
        for sev_band in ("le6","gt6"):
            s=[]
            for x in recs:
                rv=num(x["rmd3"]); sv=num(x["severity"])
                if rv is None or sv is None or med is None: continue
                rb="low" if rv<med else "high"; sb="gt6" if sv>6 else "le6"
                if rb==rmd_band and sb==sev_band: s.append(x)
            cells[f"rmd_{rmd_band}__severity_{sev_band}"]=summary(s)
    return {"rmd3_historical_median":None if med is None else round(med,6),"severity_split_pp":6.0,"cells":cells,"records":recs}


def first_hit(close_path, signal_close, trough, up_pct):
    up=signal_close*(1+up_pct/100.0)
    for k,c in enumerate(close_path, start=1):
        hit_up=c>=up; hit_down=c<trough
        if hit_up and hit_down: return {"outcome":"same_day_both","session":k}
        if hit_up: return {"outcome":"upside_first","session":k}
        if hit_down: return {"outcome":"trough_break_first","session":k}
    return {"outcome":"censored_20d","session":None}


def competing_risk(events, rows, by_date, audit_by_date):
    idx={r["date"]:i for i,r in enumerate(rows)}; closes=[num(r.get("sp500_close")) for r in rows]
    out={}
    for target in (3,5):
        recs=[]
        for r in events:
            d=r["date"]; i=idx[d]; a=audit_by_date.get(d,{}); s=idx.get(a.get("dual_episode_start"))
            if s is None: continue
            past=[x for x in closes[s:i+1] if x is not None]
            if not past or closes[i] is None: continue
            fut=[x for x in closes[i+1:min(len(rows),i+21)] if x is not None]
            z=first_hit(fut,closes[i],min(past),target); z["date"]=d; recs.append(z)
        counts={k:sum(1 for x in recs if x["outcome"]==k) for k in ("upside_first","trough_break_first","same_day_both","censored_20d")}
        out[f"target_{target}pct"]={"n":len(recs),"counts":counts,"pct":{k:None if not recs else round(100*v/len(recs),2) for k,v in counts.items()},"records":recs}
    return out


def entry_exit_matrix(events, rows):
    idx={r["date"]:i for i,r in enumerate(rows)}; c=[num(r.get("sp500_close")) for r in rows]
    out={}
    for delay in (0,1,2,3,5):
        dct={}
        for h in (5,10,20):
            vals=[]
            for e in events:
                i=idx[e["date"]]+delay
                j=i+h
                if i<len(c) and j<len(c) and c[i] not in (None,0) and c[j] is not None:
                    vals.append(100*(c[j]/c[i]-1.0))
            dct[f"hold_{h}d"]={"n":len(vals),"mean_pct":None if not vals else round(mean(vals),4),"median_pct":None if not vals else round(median(vals),4),"positive_pct":None if not vals else round(100*sum(x>0 for x in vals)/len(vals),2)}
        out[f"delay_{delay}d"]=dct
    return out


def fetch_stooq(symbol):
    url=f"https://stooq.com/q/d/l/?s={symbol}&d1=20160101&d2=20261231&i=d"
    r=requests.get(url,timeout=20,headers={"User-Agent":"Mozilla/5.0"}); r.raise_for_status()
    rd=csv.DictReader(io.StringIO(r.text)); out=[]
    for row in rd:
        d=row.get("Date"); c=num(row.get("Close"))
        if d and c is not None: out.append((d,c))
    if len(out)<100: raise RuntimeError(f"short Stooq series {symbol}: {len(out)}")
    return out


def fetch_fred_vix():
    url="https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS"
    r=requests.get(url,timeout=20,headers={"User-Agent":"Mozilla/5.0"}); r.raise_for_status()
    rd=csv.DictReader(io.StringIO(r.text)); out=[]
    for row in rd:
        d=row.get("DATE") or row.get("observation_date"); v=num(row.get("VIXCLS"))
        if d and v is not None and d>="2016-01-01": out.append((d,v))
    if len(out)<100: raise RuntimeError(f"short VIX series: {len(out)}")
    return out


def ret_n_on_or_before(series,date,n=5):
    arr=[x for x in series if x[0]<=date]
    if len(arr)<=n: return None
    a=arr[-1][1]; b=arr[-1-n][1]
    return None if b==0 else 100*(a/b-1.0)


def cross_market_test(events):
    series={}; errors={}
    for k,sym in {"QQQ":"qqq.us","IWM":"iwm.us","HYG":"hyg.us","LQD":"lqd.us"}.items():
        try: series[k]=fetch_stooq(sym)
        except Exception as e: errors[k]=str(e)
    try: series["VIX"]=fetch_fred_vix()
    except Exception as e: errors["VIX"]=str(e)
    recs=[]
    for e in events:
        d=e["date"]; feats={}; score=0; avail=0
        for k in ("QQQ","IWM","HYG","LQD"):
            if k in series:
                v=ret_n_on_or_before(series[k],d,5); feats[f"{k}_ret5_pct"]=None if v is None else round(v,4)
                if v is not None: avail+=1; score+=int(v>0)
        if "VIX" in series:
            v=ret_n_on_or_before(series["VIX"],d,5); feats["VIX_ret5_pct"]=None if v is None else round(v,4)
            if v is not None: avail+=1; score+=int(v<0)
        recs.append({"date":d,"confirmation_count":score,"available_components":avail,**feats,
                     **{f"s2_fwd_{h}d":e.get(f"s2_fwd_{h}d") for h in H},
                     "s2_mfe_10d":e.get("s2_mfe_10d"),"s2_mae_10d":e.get("s2_mae_10d"),"s2_mfe_20d":e.get("s2_mfe_20d"),"s2_mae_20d":e.get("s2_mae_20d")})
    full=[r for r in recs if r["available_components"]>=4]
    groups={"0_2":summary([r for r in full if r["confirmation_count"]<=2]),"3_plus":summary([r for r in full if r["confirmation_count"]>=3])}
    return {"source":"Stooq ETFs + FRED VIXCLS; no API key","errors":errors,"records":recs,"groups":groups}


def analog_vector(r):
    vals=[
        clamp((num(r.get("net_liq_4w_pct")) or 0.0)+15,0,30)/30.0,
        clamp((num(r.get("reserves_4w_pct")) or 0.0)+15,0,30)/30.0,
        clamp((num(r.get("breadth_20d_pct")) or 0.0)/100.0),
        clamp(num(r.get("box_position")) if num(r.get("box_position")) is not None else 0.5),
        clamp((num(r.get("market_score_pct")) or num(r.get("market_score")) or 50.0)/100.0),
    ]
    return vals


def dist(a,b): return math.sqrt(sum((x-y)**2 for x,y in zip(a,b)))


def analog_test(events, rows):
    idx={r["date"]:i for i,r in enumerate(rows)}
    for r in rows: r["_analog_vec"]=analog_vector(r)
    latest=rows[-1]; li=len(rows)-1
    candidates=[r for i,r in enumerate(rows) if i<=li-20 and num(r.get("s2_fwd_20d")) is not None]
    near=sorted(candidates,key=lambda r:dist(latest["_analog_vec"],r["_analog_vec"]))[:20]
    latest_payload={"target_date":latest["date"],"neighbors":[{"date":r["date"],"distance":round(dist(latest["_analog_vec"],r["_analog_vec"]),6),"fwd_5d":r.get("s2_fwd_5d"),"fwd_10d":r.get("s2_fwd_10d"),"fwd_20d":r.get("s2_fwd_20d")} for r in near],"neighbor_summary":summary(near)}
    preds=[]
    for e in events:
        i=idx[e["date"]]; prior=[r for j,r in enumerate(rows) if j<=i-20 and num(r.get("s2_fwd_10d")) is not None]
        if len(prior)<5: continue
        nn=sorted(prior,key=lambda r:dist(e["_analog_vec"],r["_analog_vec"]))[:5]
        pred=mean(r["s2_fwd_10d"] for r in nn); act=e.get("s2_fwd_10d")
        if num(act) is not None: preds.append({"date":e["date"],"pred_10d":pred,"actual_10d":act})
    rho=spearman_pairs(preds,"pred_10d","actual_10d")
    sign=None if not preds else round(100*sum((x["pred_10d"]>0)==(x["actual_10d"]>0) for x in preds)/len(preds),2)
    return {"feature_definition":"fixed-scale Euclidean distance on net-liquidity 4w, reserves 4w, breadth percentile, box position, market score percentile/score; validation neighbors restricted to >=20 sessions earlier","latest":latest_payload,"historical_forward_validation":{"n":len(preds),"spearman":rho,"sign_accuracy_pct":sign,"records":preds}}


def main():
    src=json.loads(BOX.read_text(encoding="utf-8"))
    rows=[dict(r) for r in (src.get("daily") or [])]
    rows=seq.add_dual(rows); rows,episodes=seq.enrich_sequence(rows); rows=add_forward(rows); rows=enrich_regime(rows)
    by_date={r["date"]:r for r in rows}
    events=event_rows(rows)
    audit=json.loads(AUDIT.read_text(encoding="utf-8")); audits=[dict(x) for x in audit.get("events",[])]
    audit_by_date={x["date"]:x for x in audits}
    for a in audits:
        s=by_date.get(a.get("dual_episode_start"),{})
        net=num(s.get("net_liq_4w_pct")); res=num(s.get("reserves_4w_pct"))
        a["_severity"]=None if net is None or res is None else max(0.0,-2.0-net)+max(0.0,-2.0-res)
    rmd=json.loads(RMD.read_text(encoding="utf-8")); rmd_by_date={x["date"]:x for x in rmd.get("events_ranked_by_rmd3",[])}

    payload={
        "schema":"TASK14-STAGE2-RESEARCH-V1",
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "research_only":True,"diagnostic_only":True,"production_effect":"none","thresholds_changed":False,
        "coverage":{"start":rows[0]["date"],"end":rows[-1]["date"],"observations":len(rows),"complete_sequence_events":len(events)},
        "regime_conditioning":regime_test(events),
        "leave_one_year_out":loyo_test(events,rmd_by_date),
        "placebo_random_dates":placebo_test(events,rows),
        "order_necessity":order_test(episodes,rows,by_date),
        "continuous_sequence_maturity":continuous_score_test(rows),
        "rmd_x_dual_severity":rmd_severity_surface(events,rmd_by_date,audit_by_date),
        "competing_risk":competing_risk(events,rows,by_date,audit_by_date),
        "entry_exit_matrix":entry_exit_matrix(events,rows),
        "cross_market_confirmation":cross_market_test(events),
        "historical_analogs":analog_test(events,rows),
        "decision":{"may_change_production":False,"may_change_existing_forward_oos":False,"status":"post_discovery_mechanism_and_robustness_diagnostics_only","promotion_requirement":"Any surviving candidate must be separately preregistered, frozen, and validated with independent Forward OOS."},
        "warnings":[
            "All analyses are post-discovery diagnostics and must not be treated as fresh OOS evidence.",
            "The 12 complete historical sequence events are heavily concentrated in 2022.",
            "Placebo random-date tests are descriptive and do not fully correct serial dependence or multiple testing.",
            "Continuous maturity score uses fixed equal-weight components and is not weight-optimized.",
            "Cross-market data are fetched from Stooq/FRED during the run; unavailable feeds are explicitly reported.",
            "Historical analog scaling is fixed and deliberately simple; it is not optimized for predictive fit.",
        ],
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Wrote",OUT)
    print(json.dumps({
        "coverage":payload["coverage"],
        "exclude_2022":payload["leave_one_year_out"]["exclude_2022_focus"],
        "placebo":payload["placebo_random_dates"]["horizons"],
        "competing_risk":{k:v["pct"] for k,v in payload["competing_risk"].items()},
        "cross_market_errors":payload["cross_market_confirmation"]["errors"],
        "analog_validation":payload["historical_analogs"]["historical_forward_validation"],
    },ensure_ascii=False))


if __name__=="__main__":
    main()
