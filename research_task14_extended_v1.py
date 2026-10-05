"""Task 1/4 Extended Diagnostics V1.

Research-only extension of frozen Market State Sequence V1 / Sequence Freshness /
RMD3. It does not change production rules, thresholds, event labels, or OOS ledgers.

Diagnostics: sequence ablation, recovery velocity, failure paths, RMD component
ablation, freshness decay, second-leg hazard, and ex-ante state transitions.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

from build_market_state_sequence_v1 import add_dual, enrich_sequence

ROOT = Path(__file__).resolve().parent
BOX_SRC = ROOT / "docs/data/market_state_box_v1.json"
EVENT_SRC = ROOT / "docs/data/market_state_sequence_event_audit_v1.json"
FRESH_SRC = ROOT / "docs/data/market_state_sequence_freshness_v1.json"
RMD_SRC = ROOT / "docs/data/residual_mean_reversion_distance_v1.json"
OUT = ROOT / "docs/data/task14_extended_diagnostics_v1.json"
HORIZONS = (1, 3, 5, 10, 20)
DECLUSTER = 5


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def quantile(values, p):
    a = sorted(v for v in (num(x) for x in values) if v is not None)
    if not a:
        return None
    z = (len(a) - 1) * p
    i = int(z)
    j = min(i + 1, len(a) - 1)
    f = z - i
    return a[i] + (a[j] - a[i]) * f


def rankdata(values):
    pairs = sorted((v, i) for i, v in enumerate(values))
    ranks = [0.0] * len(values)
    p = 0
    while p < len(pairs):
        q = p + 1
        while q < len(pairs) and pairs[q][0] == pairs[p][0]:
            q += 1
        avg = ((p + 1) + q) / 2.0
        for _, idx in pairs[p:q]:
            ranks[idx] = avg
        p = q
    return ranks


def pearson(x, y):
    if len(x) < 3:
        return None
    mx, my = mean(x), mean(y)
    dx = [v - mx for v in x]
    dy = [v - my for v in y]
    den = math.sqrt(sum(v * v for v in dx) * sum(v * v for v in dy))
    if den == 0:
        return None
    return sum(a * b for a, b in zip(dx, dy)) / den


def spearman_pairs(items, x_key, y_key):
    pairs = []
    for e in items:
        x = num(e.get(x_key))
        y = num(e.get(y_key))
        if x is not None and y is not None:
            pairs.append((x, y))
    if len(pairs) < 3:
        return {"n": len(pairs), "rho": None}
    rho = pearson(rankdata([x for x, _ in pairs]), rankdata([y for _, y in pairs]))
    return {"n": len(pairs), "rho": None if rho is None else round(rho, 4)}


def add_forward_path_metrics(rows):
    closes = [num(r.get("sp500_close")) for r in rows]
    for i, r in enumerate(rows):
        c0 = closes[i]
        for h in HORIZONS:
            if c0 is None or i + h >= len(rows) or closes[i + h] is None:
                r[f"ext_fwd_{h}d"] = None
            else:
                r[f"ext_fwd_{h}d"] = 100.0 * (closes[i + h] / c0 - 1.0)
        for h in (10, 20):
            vals = [c for c in closes[i + 1 : min(len(rows), i + h + 1)] if c is not None]
            if c0 is None or not vals:
                r[f"ext_mfe_{h}d"] = None
                r[f"ext_mae_{h}d"] = None
            else:
                rets = [100.0 * (c / c0 - 1.0) for c in vals]
                r[f"ext_mfe_{h}d"] = max(rets)
                r[f"ext_mae_{h}d"] = min(rets)
    return rows


def summarize_rows(sample, baseline=None):
    out = {"n": len(sample)}
    baseline = baseline or []
    for h in HORIZONS:
        key = f"ext_fwd_{h}d"
        vals = [num(r.get(key)) for r in sample]
        vals = [v for v in vals if v is not None]
        base = [num(r.get(key)) for r in baseline]
        base = [v for v in base if v is not None]
        if not vals:
            out[f"{h}d"] = {"n": 0}
            continue
        bm = mean(base) if base else None
        out[f"{h}d"] = {
            "n": len(vals),
            "mean_pct": round(mean(vals), 4),
            "median_pct": round(median(vals), 4),
            "positive_pct": round(100.0 * sum(v > 0 for v in vals) / len(vals), 2),
            "p10_pct": round(quantile(vals, 0.10), 4),
            "p90_pct": round(quantile(vals, 0.90), 4),
            "baseline_mean_pct": None if bm is None else round(bm, 4),
            "mean_lift_vs_baseline_pp": None if bm is None else round(mean(vals) - bm, 4),
        }
    for h in (10, 20):
        mfe = [num(r.get(f"ext_mfe_{h}d")) for r in sample]
        mae = [num(r.get(f"ext_mae_{h}d")) for r in sample]
        mfe = [x for x in mfe if x is not None]
        mae = [x for x in mae if x is not None]
        out[f"mfe_{h}d_mean_pct"] = None if not mfe else round(mean(mfe), 4)
        out[f"mae_{h}d_mean_pct"] = None if not mae else round(mean(mae), 4)
    return out


def onset_indices(rows, predicate, decluster=DECLUSTER):
    candidates = []
    prev = False
    for i, r in enumerate(rows):
        cur = bool(predicate(r))
        if cur and not prev:
            candidates.append(i)
        prev = cur
    keep = []
    last = -10_000
    for i in candidates:
        if i - last >= decluster:
            keep.append(i)
            last = i
    return keep


def lag_band(x):
    x = num(x)
    if x is None:
        return "missing"
    if x <= 5:
        return "0_5"
    if x <= 10:
        return "6_10"
    if x <= 20:
        return "11_20"
    return "21_plus"


def breadth_rebound_band(x):
    x = num(x)
    if x is None:
        return "missing"
    if x <= 10:
        return "le10pp"
    if x <= 25:
        return "10_25pp"
    return "gt25pp"


def dual_severity_band(x):
    x = num(x)
    if x is None:
        return "missing"
    if x <= 2:
        return "le2pp"
    if x <= 6:
        return "2_6pp"
    return "gt6pp"


def main():
    box = json.loads(BOX_SRC.read_text(encoding="utf-8"))
    rows = [dict(r) for r in (box.get("daily") or [])]
    if len(rows) < 2000:
        raise RuntimeError("market_state_box_v1 daily table missing/short")
    rows = add_dual(rows)
    rows, episodes = enrich_sequence(rows)
    rows = add_forward_path_metrics(rows)
    idx_by_date = {r["date"]: i for i, r in enumerate(rows)}
    usable = [r for r in rows if num(r.get("ext_fwd_20d")) is not None]

    # 1) Cumulative sequence ablation.
    stages = {
        "S0_DUAL_ONSET": lambda r: bool(r.get("dual_drain")),
        "S1_DUAL_BREADTH_LOW": lambda r: bool(r.get("D_TO_BREADTH_LOW")),
        "S2_LOW_PLUS_BOX": lambda r: bool(r.get("D_TO_BREADTH_LOW")) and bool(r.get("box_bottom_since_dual")),
        "S3_LOW_BOX_BREADTH_REBOUND": lambda r: bool(r.get("D_TO_BREADTH_LOW")) and bool(r.get("box_bottom_since_dual")) and bool(r.get("breadth_rebound_since_dual")),
        "S4_REBOUND_SCORE_NO_BOX_REQUIREMENT": lambda r: bool(r.get("D_TO_REBOUND_SCORE")),
        "S5_FULL_COMPLETE": lambda r: bool(r.get("D_TO_BOTH_REBOUND_SCORE")),
    }
    ablation = {}
    for name, pred in stages.items():
        ix = [i for i in onset_indices(rows, pred) if num(rows[i].get("ext_fwd_20d")) is not None]
        ablation[name] = {
            "dates": [rows[i]["date"] for i in ix],
            "stats": summarize_rows([rows[i] for i in ix], usable),
        }

    # 2) Recovery velocity on the frozen completion events.
    event_src = json.loads(EVENT_SRC.read_text(encoding="utf-8"))
    events = [dict(e) for e in event_src.get("events", [])]
    for e in events:
        i = idx_by_date.get(e.get("date"))
        if i is not None:
            e["ext_fwd_20d"] = rows[i].get("ext_fwd_20d")
            e["ext_mfe_20d"] = rows[i].get("ext_mfe_20d")
            e["ext_mae_20d"] = rows[i].get("ext_mae_20d")
    vel_groups = {}
    for band in ("0_5", "6_10", "11_20", "21_plus"):
        sample = [rows[idx_by_date[e["date"]]] for e in events if e.get("date") in idx_by_date and lag_band(e.get("confirmation_lag_sessions")) == band]
        vel_groups[band] = summarize_rows(sample, usable)
    completion_eps = [e for e in episodes if e.get("first_score_recovery_after_rebound") and e.get("first_box_bottom") and e.get("first_breadth_low")]
    intervals = {
        "dual_to_breadth_low": [e["breadth_low_lag_from_start"] for e in completion_eps if e.get("breadth_low_lag_from_start") is not None],
        "dual_to_box_bottom": [e["box_bottom_lag_from_start"] for e in completion_eps if e.get("box_bottom_lag_from_start") is not None],
        "breadth_low_to_rebound": [e["rebound_lag_from_start"] - e["breadth_low_lag_from_start"] for e in completion_eps if e.get("rebound_lag_from_start") is not None and e.get("breadth_low_lag_from_start") is not None],
        "rebound_to_score_recovery": [e["score_recovery_lag_from_start"] - e["rebound_lag_from_start"] for e in completion_eps if e.get("score_recovery_lag_from_start") is not None and e.get("rebound_lag_from_start") is not None],
        "dual_to_score_recovery": [e["score_recovery_lag_from_start"] for e in completion_eps if e.get("score_recovery_lag_from_start") is not None],
    }
    interval_summary = {
        k: {
            "n": len(v),
            "median_sessions": None if not v else round(median(v), 2),
            "p25": None if not v else round(quantile(v, 0.25), 2),
            "p75": None if not v else round(quantile(v, 0.75), 2),
        }
        for k, v in intervals.items()
    }
    velocity_corr = {
        f"lag_vs_fwd_{h}d": spearman_pairs(events, "confirmation_lag_sessions", "ext_fwd_20d" if h == 20 else f"fwd_{h}d")
        for h in (5, 10, 20)
    }

    # 3) Retrospective failure-path taxonomy across all DUAL episodes.
    failure_records = []
    for ep in episodes:
        has_low = ep.get("first_breadth_low") is not None
        has_box = ep.get("first_box_bottom") is not None
        has_rebound = ep.get("first_breadth_rebound") is not None
        has_score = ep.get("first_score_recovery_after_rebound") is not None
        if not has_low:
            cls = "NO_BREADTH_LOW"
        elif not has_box:
            cls = "RECOVERY_NO_BOX" if has_score else "BREADTH_LOW_NO_BOX"
        elif not has_rebound:
            cls = "LOW_BOX_NO_REBOUND"
        elif not has_score:
            cls = "REBOUND_NO_SCORE"
        else:
            cls = "COMPLETE_PATH"
        i = idx_by_date.get(ep.get("start"))
        rec = dict(ep)
        rec["failure_class"] = cls
        if i is not None:
            for h in HORIZONS:
                rec[f"ext_fwd_{h}d"] = rows[i].get(f"ext_fwd_{h}d")
            for h in (10, 20):
                rec[f"ext_mfe_{h}d"] = rows[i].get(f"ext_mfe_{h}d")
                rec[f"ext_mae_{h}d"] = rows[i].get(f"ext_mae_{h}d")
        failure_records.append(rec)
    failure_summary = {}
    failure_classes = ("NO_BREADTH_LOW", "BREADTH_LOW_NO_BOX", "RECOVERY_NO_BOX", "LOW_BOX_NO_REBOUND", "REBOUND_NO_SCORE", "COMPLETE_PATH")
    for cls in failure_classes:
        recs = [x for x in failure_records if x["failure_class"] == cls]
        pseudo = []
        for x in recs:
            q = {f"ext_fwd_{h}d": x.get(f"ext_fwd_{h}d") for h in HORIZONS}
            for h in (10, 20):
                q[f"ext_mfe_{h}d"] = x.get(f"ext_mfe_{h}d")
                q[f"ext_mae_{h}d"] = x.get(f"ext_mae_{h}d")
            pseudo.append(q)
        failure_summary[cls] = summarize_rows(pseudo, usable)

    # 4) RMD component/pair ablation, equal weights only.
    rmd = json.loads(RMD_SRC.read_text(encoding="utf-8"))
    rmd_events = [dict(e) for e in rmd.get("events_ranked_by_rmd3", [])]
    combos = {
        "PRICE": ("price_residual",),
        "BREADTH": ("breadth_residual",),
        "SCORE": ("score_residual",),
        "PRICE_BREADTH": ("price_residual", "breadth_residual"),
        "PRICE_SCORE": ("price_residual", "score_residual"),
        "BREADTH_SCORE": ("breadth_residual", "score_residual"),
        "RMD3": ("price_residual", "breadth_residual", "score_residual"),
    }
    for e in rmd_events:
        i = idx_by_date.get(e.get("date"))
        if i is not None:
            e["fwd_20d"] = rows[i].get("ext_fwd_20d")
        for name, keys in combos.items():
            vals = [num(e.get(k)) for k in keys]
            e[f"combo_{name}"] = None if any(v is None for v in vals) else sum(vals) / len(vals)
    rmd_ablation = {}
    for name, keys in combos.items():
        key = f"combo_{name}"
        item = {"components": list(keys), "spearman": {}}
        for h in (5, 10, 20):
            item["spearman"][f"fwd_{h}d"] = spearman_pairs(rmd_events, key, "fwd_20d" if h == 20 else f"fwd_{h}d")
        valid = sorted([e for e in rmd_events if num(e.get(key)) is not None], key=lambda e: e[key])
        cut = len(valid) // 2
        item["rank_halves"] = {}
        for half, sample in {"lower": valid[:cut], "upper": valid[cut:]}.items():
            d = {"n": len(sample)}
            for h in (5, 10, 20):
                vals = [num(e.get("fwd_20d" if h == 20 else f"fwd_{h}d")) for e in sample]
                vals = [v for v in vals if v is not None]
                d[f"{h}d_mean_pct"] = None if not vals else round(mean(vals), 4)
                d[f"{h}d_positive_pct"] = None if not vals else round(100.0 * sum(v > 0 for v in vals) / len(vals), 2)
            item["rank_halves"][half] = d
        rmd_ablation[name] = item

    # 5) Freshness decay by fixed delayed observation dates.
    decay = {}
    for delay in (0, 1, 2, 3, 5, 10):
        sample, dates = [], []
        for e in events:
            i = idx_by_date.get(e.get("date"))
            if i is None or i + delay >= len(rows):
                continue
            sample.append(rows[i + delay])
            dates.append(rows[i + delay]["date"])
        decay[f"DPLUS_{delay}"] = {"dates": dates, "stats": summarize_rows(sample, usable)}
    baseline_means = {
        h: mean([r[f"ext_fwd_{h}d"] for r in usable if num(r.get(f"ext_fwd_{h}d")) is not None])
        for h in HORIZONS
    }
    half_life = {}
    for h in (5, 10, 20):
        d0 = decay["DPLUS_0"]["stats"][f"{h}d"].get("mean_pct")
        base = baseline_means[h]
        lift = None if d0 is None else d0 - base
        hit = None
        if lift is not None and lift > 0:
            for delay in (1, 2, 3, 5, 10):
                m = decay[f"DPLUS_{delay}"]["stats"][f"{h}d"].get("mean_pct")
                if m is not None and (m - base) <= 0.5 * lift:
                    hit = delay
                    break
        half_life[f"{h}d"] = {
            "day0_lift_pp": None if lift is None else round(lift, 4),
            "first_fixed_delay_at_or_below_half_lift": hit,
        }

    # 6) Second-leg hazard: retest/break the prior DUAL-path trough after completion.
    rmd_by_date = {e["date"]: e for e in rmd_events}
    hazard_events = []
    for e in events:
        date = e.get("date")
        i = idx_by_date.get(date)
        s = idx_by_date.get(e.get("dual_episode_start"))
        if i is None or s is None or s > i:
            continue
        past = [num(rows[j].get("sp500_close")) for j in range(s, i + 1)]
        past = [x for x in past if x is not None]
        if not past:
            continue
        trough = min(past)
        rr = rmd_by_date.get(date, {})
        start = rows[s]
        net = num(start.get("net_liq_4w_pct"))
        res = num(start.get("reserves_4w_pct"))
        severity = None if net is None or res is None else max(0.0, -2.0 - net) + max(0.0, -2.0 - res)
        br = num(e.get("breadth_20d_pct"))
        brmin = num(e.get("min_breadth_pct_since_dual"))
        brdist = None if br is None or brmin is None else br - brmin
        rec = {
            "date": date,
            "prior_trough_close": round(trough, 4),
            "confirmation_lag_sessions": e.get("confirmation_lag_sessions"),
            "speed_band": lag_band(e.get("confirmation_lag_sessions")),
            "rmd3": rr.get("rmd3"),
            "breadth_rebound_distance_pp": None if brdist is None else round(brdist, 4),
            "breadth_rebound_band": breadth_rebound_band(brdist),
            "dual_severity_pp_beyond_threshold": None if severity is None else round(severity, 4),
            "dual_severity_band": dual_severity_band(severity),
        }
        for h in (5, 10, 20):
            fut = [num(rows[j].get("sp500_close")) for j in range(i + 1, min(len(rows), i + h + 1))]
            fut = [x for x in fut if x is not None]
            mn = None if not fut else min(fut)
            rec[f"future_min_{h}d"] = None if mn is None else round(mn, 4)
            rec[f"retest_within_1pct_{h}d"] = None if mn is None else bool(mn <= trough * 1.01)
            rec[f"break_prior_trough_{h}d"] = None if mn is None else bool(mn < trough)
        hazard_events.append(rec)
    rmd_vals = sorted([num(e.get("rmd3")) for e in hazard_events if num(e.get("rmd3")) is not None])
    rmd_med = median(rmd_vals) if rmd_vals else None
    for e in hazard_events:
        x = num(e.get("rmd3"))
        e["rmd3_half"] = "missing" if x is None or rmd_med is None else ("low" if x < rmd_med else "high")

    def hazard_summary(group):
        out = {"n": len(group)}
        for h in (5, 10, 20):
            for key in ("retest_within_1pct", "break_prior_trough"):
                vals = [e.get(f"{key}_{h}d") for e in group if e.get(f"{key}_{h}d") is not None]
                out[f"{key}_{h}d_pct"] = None if not vals else round(100.0 * sum(bool(v) for v in vals) / len(vals), 2)
        return out

    hazard_groups = {
        "rmd3_half": {k: hazard_summary([e for e in hazard_events if e["rmd3_half"] == k]) for k in ("low", "high")},
        "speed_band": {k: hazard_summary([e for e in hazard_events if e["speed_band"] == k]) for k in ("0_5", "6_10", "11_20", "21_plus")},
        "breadth_rebound_band": {k: hazard_summary([e for e in hazard_events if e["breadth_rebound_band"] == k]) for k in ("le10pp", "10_25pp", "gt25pp")},
        "dual_severity_band": {k: hazard_summary([e for e in hazard_events if e["dual_severity_band"] == k]) for k in ("le2pp", "2_6pp", "gt6pp")},
    }

    # 7) Exclusive, current-information-only daily states; no future outcome leakage.
    def state(r):
        if bool(r.get("D_TO_BOTH_REBOUND_SCORE")):
            return "COMPLETE_RECOVERY"
        if bool(r.get("D_TO_REBOUND_SCORE")):
            return "SCORE_RECOVERY_NO_BOX"
        if bool(r.get("D_TO_BREADTH_LOW")) and bool(r.get("box_bottom_since_dual")) and bool(r.get("breadth_rebound_since_dual")):
            return "LOW_BOX_REBOUND"
        if bool(r.get("D_TO_BREADTH_REBOUND")):
            return "BREADTH_REBOUND"
        if bool(r.get("D_TO_BREADTH_LOW")) and bool(r.get("box_bottom_since_dual")):
            return "LOW_AND_BOX"
        if bool(r.get("D_TO_BOX_BOTTOM")):
            return "BOX_BOTTOM"
        if bool(r.get("D_TO_BREADTH_LOW")):
            return "BREADTH_LOW"
        if bool(r.get("recent_dual_10d")):
            return "DUAL_RECENT"
        return "NORMAL"

    states = [state(r) for r in rows]
    state_names = sorted(set(states))
    transition = {}
    for lag in (1, 3, 5):
        counts = {s: {t: 0 for t in state_names} for s in state_names}
        totals = {s: 0 for s in state_names}
        for i in range(len(states) - lag):
            a, b = states[i], states[i + lag]
            counts[a][b] += 1
            totals[a] += 1
        probs = {s: {t: (None if totals[s] == 0 else round(100.0 * counts[s][t] / totals[s], 2)) for t in state_names} for s in state_names}
        to_complete = {s: (None if totals[s] == 0 else round(100.0 * counts[s].get("COMPLETE_RECOVERY", 0) / totals[s], 2)) for s in state_names}
        transition[f"lag_{lag}d"] = {"counts": counts, "prob_pct": probs, "to_complete_pct": to_complete}
    occupancy = {s: {"n": states.count(s), "pct": round(100.0 * states.count(s) / len(states), 2)} for s in state_names}

    out = {
        "schema": "TASK14-EXTENDED-DIAGNOSTICS-V1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "diagnostic_only": True,
        "production_effect": "none",
        "thresholds_changed": False,
        "source_event_definition": "D_TO_BOTH_REBOUND_SCORE",
        "coverage": {"start": rows[0]["date"], "end": rows[-1]["date"], "observations": len(rows), "usable_20d": len(usable)},
        "sequence_ablation": ablation,
        "recovery_velocity": {"frozen_event_count": len(events), "fixed_lag_bands": vel_groups, "milestone_intervals": interval_summary, "spearman": velocity_corr},
        "failure_paths": {"episode_count": len(episodes), "class_counts": {k: sum(1 for x in failure_records if x["failure_class"] == k) for k in failure_summary}, "summary_from_episode_start": failure_summary, "records": failure_records},
        "rmd_component_ablation": rmd_ablation,
        "freshness_decay": {"delays_sessions": [0, 1, 2, 3, 5, 10], "curve": decay, "baseline_mean_pct": {str(k): round(v, 4) for k, v in baseline_means.items()}, "half_life_diagnostic": half_life},
        "second_leg_hazard": {"definition": {"retest": "future min close <= 1.01 * prior trough close since DUAL episode start", "break": "future min close < prior trough close"}, "rmd3_median": None if rmd_med is None else round(rmd_med, 6), "events": hazard_events, "groups": hazard_groups},
        "state_transition_matrix": {"definition": "exclusive current-information states only; no future-dependent FAILURE/SECOND_LEG state", "occupancy": occupancy, "transitions": transition},
        "decision": {"may_change_production": False, "may_change_existing_forward_oos_shadow": False, "status": "mechanism_diagnostic_only", "next_requirement": "Any promoted gate/weight requires preregistration and independent forward OOS evidence."},
        "warnings": [
            "All seven extensions are post-discovery diagnostics over already observed historical data.",
            "Failure classes are retrospective path labels and must not be used as ex-ante signals without a separately preregistered observable rule.",
            "RMD pair/triple combinations are equal-weight ablations only; no weight fitting is performed.",
            "Second-leg 1% retest and trough-break definitions are descriptive fixed diagnostics, not production rules.",
            "FRED current-history retrieval can contain revisions and is not ALFRED vintage data.",
        ],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Wrote", OUT)
    print(json.dumps({"coverage": out["coverage"], "ablation_n": {k: v["stats"]["n"] for k, v in ablation.items()}, "failure_counts": out["failure_paths"]["class_counts"], "half_life": half_life, "occupancy": occupancy}, ensure_ascii=False))


if __name__ == "__main__":
    main()
