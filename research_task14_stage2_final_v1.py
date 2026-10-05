#!/usr/bin/env python3
"""Final historical Stage-2 diagnostics for Task 1/4.

Exactly five frozen studies:
1) matched controls, 2) threshold stability surface, 3) lead/lag event study,
4) orthogonal information, 5) indicator redundancy map.

Research-only. No production or Forward-OOS mutation.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

import numpy as np
import pandas as pd

import build_market_state_sequence_v1 as seq

ROOT = Path(__file__).resolve().parent
BOX = ROOT / "docs/data/market_state_box_v1.json"
AUDIT = ROOT / "docs/data/market_state_sequence_event_audit_v1.json"
RMD = ROOT / "docs/data/residual_mean_reversion_distance_v1.json"
OUT = ROOT / "docs/data/task14_stage2_final_v1.json"
H = (5, 10, 20)


def num(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def rankdata(vals):
    pairs = sorted((v, i) for i, v in enumerate(vals))
    out = [0.0] * len(vals)
    p = 0
    while p < len(pairs):
        q = p + 1
        while q < len(pairs) and pairs[q][0] == pairs[p][0]:
            q += 1
        r = ((p + 1) + q) / 2.0
        for _, i in pairs[p:q]:
            out[i] = r
        p = q
    return out


def pearson(x, y):
    if len(x) < 3:
        return None
    mx, my = mean(x), mean(y)
    dx = [v - mx for v in x]
    dy = [v - my for v in y]
    den = math.sqrt(sum(v * v for v in dx) * sum(v * v for v in dy))
    if not den:
        return None
    return sum(a * b for a, b in zip(dx, dy)) / den


def qtile(vals, p):
    a = sorted(v for v in (num(x) for x in vals) if v is not None)
    if not a:
        return None
    z = (len(a) - 1) * p
    i = int(z)
    j = min(i + 1, len(a) - 1)
    f = z - i
    return a[i] + (a[j] - a[i]) * f


def add_forward_and_regime(rows):
    closes = [num(r.get("sp500_close")) for r in rows]
    rets = [None]
    for i in range(1, len(rows)):
        a, b = closes[i - 1], closes[i]
        rets.append(None if a in (None, 0) or b is None else b / a - 1.0)

    ma200 = [None] * len(rows)
    q = []
    s = 0.0
    for i, c in enumerate(closes):
        q.append(c)
        if c is not None:
            s += c
        if len(q) > 200:
            old = q.pop(0)
            if old is not None:
                s -= old
        if len(q) == 200 and all(v is not None for v in q):
            ma200[i] = s / 200.0

    for i, r in enumerate(rows):
        c0 = closes[i]
        for h in H:
            ch = closes[i + h] if i + h < len(rows) else None
            r[f"final_fwd_{h}d"] = None if c0 in (None, 0) or ch is None else 100.0 * (ch / c0 - 1.0)
        if i >= 20 and c0 is not None and closes[i - 20] not in (None, 0):
            r["ret20_pct"] = 100.0 * (c0 / closes[i - 20] - 1.0)
        else:
            r["ret20_pct"] = None
        if i >= 20:
            w = [x for x in rets[i - 19 : i + 1] if x is not None]
            if len(w) == 20:
                mu = mean(w)
                var = sum((x - mu) ** 2 for x in w) / 19
                r["rv20_pct"] = math.sqrt(var) * math.sqrt(252) * 100.0
            else:
                r["rv20_pct"] = None
        else:
            r["rv20_pct"] = None
        m = ma200[i]
        slope = None
        if i >= 20 and m is not None and ma200[i - 20] not in (None, 0):
            slope = 100.0 * (m / ma200[i - 20] - 1.0)
        if c0 is None or m is None or slope is None:
            phase = None
        elif c0 >= m and slope > 0:
            phase = "bull_rising"
        elif c0 >= m and slope <= 0:
            phase = "bull_weakening"
        elif c0 < m and slope < 0:
            phase = "bear_falling"
        else:
            phase = "bear_recovery"
        r["ma200_phase_final"] = phase
        r["ma200_distance_pct"] = None if c0 in (None, 0) or m is None else 100.0 * (c0 / m - 1.0)
    return rows


def onset_indices(rows, flag="D_TO_BOTH_REBOUND_SCORE", decluster=5):
    cand = []
    prev = False
    for i, r in enumerate(rows):
        cur = bool(r.get(flag))
        if cur and not prev:
            cand.append(i)
        prev = cur
    keep, last = [], -10_000
    for i in cand:
        if i - last >= decluster:
            keep.append(i)
            last = i
    return keep


def summary_from_indices(rows, idx):
    out = {"n": len(idx)}
    for h in H:
        vals = [num(rows[i].get(f"final_fwd_{h}d")) for i in idx]
        vals = [v for v in vals if v is not None]
        out[f"{h}d"] = {"n": len(vals)} if not vals else {
            "n": len(vals),
            "mean_pct": round(mean(vals), 4),
            "median_pct": round(median(vals), 4),
            "positive_pct": round(100.0 * sum(v > 0 for v in vals) / len(vals), 2),
        }
    return out


def matched_controls(rows, event_ix):
    features = [
        "ret20_pct", "rv20_pct", "net_liq_4w_pct", "reserves_4w_pct",
        "breadth_20d_pct", "box_position", "market_score",
    ]
    banned = set()
    for e in event_ix:
        banned.update(range(max(0, e - 20), min(len(rows), e + 21)))
    candidates = [
        i for i, r in enumerate(rows)
        if i not in banned and num(r.get("final_fwd_20d")) is not None
    ]
    mu, sd = {}, {}
    for f in features:
        vals = [num(rows[i].get(f)) for i in candidates]
        vals = [v for v in vals if v is not None]
        mu[f] = mean(vals) if vals else 0.0
        s = math.sqrt(sum((v - mu[f]) ** 2 for v in vals) / max(1, len(vals) - 1)) if vals else 1.0
        sd[f] = s if s > 1e-12 else 1.0

    records = []
    used_controls = []
    for e in event_ix:
        er = rows[e]
        phase = er.get("ma200_phase_final")
        pool = [i for i in candidates if phase is None or rows[i].get("ma200_phase_final") == phase]
        phase_relaxed = False
        if len(pool) < 5:
            pool = candidates[:]
            phase_relaxed = True
        scored = []
        for i in pool:
            diffs = []
            for f in features:
                a, b = num(er.get(f)), num(rows[i].get(f))
                if a is not None and b is not None:
                    diffs.append(((a - b) / sd[f]) ** 2)
            if len(diffs) >= 5:
                scored.append((math.sqrt(sum(diffs) / len(diffs)), i, len(diffs)))
        scored.sort()
        chosen = scored[:5]
        used_controls.extend(i for _, i, _ in chosen)
        rec = {
            "event_date": er["date"],
            "phase": phase,
            "phase_relaxed": phase_relaxed,
            "controls": [
                {"date": rows[i]["date"], "distance": round(d, 4), "features_used": nf}
                for d, i, nf in chosen
            ],
        }
        for h in H:
            ev = num(er.get(f"final_fwd_{h}d"))
            cv = [num(rows[i].get(f"final_fwd_{h}d")) for _, i, _ in chosen]
            cv = [v for v in cv if v is not None]
            cm = mean(cv) if cv else None
            rec[f"event_{h}d_pct"] = None if ev is None else round(ev, 4)
            rec[f"control_mean_{h}d_pct"] = None if cm is None else round(cm, 4)
            rec[f"matched_lift_{h}d_pp"] = None if ev is None or cm is None else round(ev - cm, 4)
        records.append(rec)

    aggregate = {}
    for h in H:
        vals = [num(r.get(f"matched_lift_{h}d_pp")) for r in records]
        vals = [v for v in vals if v is not None]
        aggregate[f"{h}d"] = {"n": len(vals)} if not vals else {
            "n": len(vals), "mean_lift_pp": round(mean(vals), 4),
            "median_lift_pp": round(median(vals), 4),
            "positive_lift_pct": round(100.0 * sum(v > 0 for v in vals) / len(vals), 2),
            "p10_pp": round(qtile(vals, 0.10), 4), "p90_pp": round(qtile(vals, 0.90), 4),
        }
    return {
        "matching_features": features,
        "controls_per_event": 5,
        "event_exclusion_window_sessions": 20,
        "event_count": len(records),
        "unique_control_dates": len(set(used_controls)),
        "control_reuse_count": len(used_controls) - len(set(used_controls)),
        "aggregate": aggregate,
        "records": records,
    }


def threshold_sequence_indices(rows, dual_thr, breadth_thr, box_thr):
    dual_flags = []
    for r in rows:
        n, s = num(r.get("net_liq_4w_pct")), num(r.get("reserves_4w_pct"))
        dual_flags.append(bool(n is not None and s is not None and n <= dual_thr and s <= dual_thr))

    flags = [False] * len(rows)
    active_start = None
    last_dual_idx = None
    last_episode_start = None
    prev_full = False
    cand = []
    for i, r in enumerate(rows):
        dual = dual_flags[i]
        if dual:
            if i == 0 or not dual_flags[i - 1]:
                active_start = i
                last_episode_start = i
            last_dual_idx = i
            anchor = active_start
        else:
            anchor = last_episode_start if last_dual_idx is not None and i - last_dual_idx <= 20 else None
        recent = bool(dual or (last_dual_idx is not None and i - last_dual_idx <= 10))
        full = False
        if anchor is not None and recent:
            span = rows[anchor : i + 1]
            bpairs = [(anchor + j, num(x.get("breadth_20d_pct"))) for j, x in enumerate(span)]
            bpairs = [(j, v) for j, v in bpairs if v is not None]
            low_i, low_v = min(bpairs, key=lambda z: z[1]) if bpairs else (None, None)
            box_ok = any(num(x.get("box_position")) is not None and num(x.get("box_position")) <= box_thr for x in span)
            br = num(r.get("breadth_20d_pct"))
            pbr = num(rows[i - 1].get("breadth_20d_pct")) if i else None
            low_ok = low_v is not None and low_v <= breadth_thr
            rebound = bool(low_i is not None and i > low_i and br is not None and pbr is not None and br > low_v and br > pbr)
            d1, d3 = num(r.get("market_score_d1")), num(r.get("market_score_d3"))
            score = bool(d1 is not None and d3 is not None and d1 > 0 and d3 > 0)
            full = bool(low_ok and box_ok and rebound and score)
        flags[i] = full
        if full and not prev_full:
            cand.append(i)
        prev_full = full

    keep, last = [], -10_000
    for i in cand:
        if i - last >= 5:
            keep.append(i)
            last = i
    return keep


def threshold_surface(rows):
    grid = []
    for dual in (-1.5, -2.0, -2.5):
        for breadth in (15.0, 20.0, 25.0):
            for box in (0.20, 0.25, 0.30):
                ix = threshold_sequence_indices(rows, dual, breadth, box)
                s = summary_from_indices(rows, ix)
                grid.append({
                    "dual_threshold_pct": dual,
                    "breadth_low_pct": breadth,
                    "box_bottom": box,
                    "is_frozen_center": dual == -2.0 and breadth == 20.0 and box == 0.25,
                    **s,
                })
    center = next(x for x in grid if x["is_frozen_center"])
    valid10 = [x for x in grid if x.get("10d", {}).get("n", 0) > 0]
    positive = [x for x in valid10 if num(x["10d"].get("mean_pct")) is not None and x["10d"]["mean_pct"] > 0]
    return {
        "grid_definition": {"dual": [-1.5, -2.0, -2.5], "breadth": [15.0, 20.0, 25.0], "box": [0.20, 0.25, 0.30]},
        "center": center,
        "cells_with_positive_10d_mean": len(positive),
        "cells_with_mature_10d": len(valid10),
        "positive_10d_share_pct": None if not valid10 else round(100.0 * len(positive) / len(valid10), 2),
        "cells": grid,
        "warning": "Diagnostic perturbation only; the best historical cell is not a candidate rule.",
    }


def lead_lag(rows, event_ix):
    vars_ = [
        "net_liq_4w_pct", "reserves_4w_pct", "breadth_20d_pct", "box_position",
        "market_score", "market_score_d1", "market_score_d3", "rv20_pct",
    ]
    offsets = []
    for k in range(-20, 21):
        rec = {"offset": k}
        price_vals = []
        byvar = {v: [] for v in vars_}
        for e in event_ix:
            j = e + k
            if j < 0 or j >= len(rows):
                continue
            c0, cj = num(rows[e].get("sp500_close")), num(rows[j].get("sp500_close"))
            if c0 not in (None, 0) and cj is not None:
                price_vals.append(100.0 * (cj / c0 - 1.0))
            for v in vars_:
                x = num(rows[j].get(v))
                if x is not None:
                    byvar[v].append(x)
        rec["price_cum_from_t0"] = {
            "n": len(price_vals),
            "mean": None if not price_vals else round(mean(price_vals), 4),
            "median": None if not price_vals else round(median(price_vals), 4),
        }
        for v, vals in byvar.items():
            rec[v] = {
                "n": len(vals),
                "mean": None if not vals else round(mean(vals), 4),
                "median": None if not vals else round(median(vals), 4),
            }
        offsets.append(rec)

    def turn(v, mode):
        vals = [(r["offset"], num(r[v].get("mean"))) for r in offsets]
        vals = [(k, x) for k, x in vals if x is not None]
        if not vals:
            return None
        k, x = (min(vals, key=lambda z: z[1]) if mode == "min" else max(vals, key=lambda z: z[1]))
        return {"offset": k, "mean": round(x, 4)}

    turns = {
        "net_liq_min": turn("net_liq_4w_pct", "min"),
        "reserves_min": turn("reserves_4w_pct", "min"),
        "breadth_min": turn("breadth_20d_pct", "min"),
        "box_min": turn("box_position", "min"),
        "market_score_min": turn("market_score", "min"),
        "rv20_max": turn("rv20_pct", "max"),
        "price_path_min": turn("price_cum_from_t0", "min"),
        "price_path_max": turn("price_cum_from_t0", "max"),
    }
    return {"anchor": "Full Sequence completion onset T0", "window": [-20, 20], "event_count": len(event_ix), "turning_offsets": turns, "offsets": offsets}


def ols_r2(y, X):
    y = np.asarray(y, dtype=float)
    X = np.asarray(X, dtype=float)
    if len(y) < X.shape[1] + 2:
        return None
    X1 = np.column_stack([np.ones(len(y)), X])
    beta, *_ = np.linalg.lstsq(X1, y, rcond=None)
    pred = X1 @ beta
    sst = float(np.sum((y - y.mean()) ** 2))
    if sst <= 1e-15:
        return None
    return 1.0 - float(np.sum((y - pred) ** 2)) / sst


def residualize(y, X):
    y = np.asarray(y, dtype=float)
    X = np.asarray(X, dtype=float)
    X1 = np.column_stack([np.ones(len(y)), X])
    beta, *_ = np.linalg.lstsq(X1, y, rcond=None)
    return y - X1 @ beta


def partial_rank_corr(records, xkey, extra_controls=()):
    phases = sorted(set(r.get("phase") for r in records if r.get("phase")))
    base_phase = phases[0] if phases else None
    pairs = []
    for r in records:
        x, y, sev = num(r.get(xkey)), num(r.get("fwd10")), num(r.get("severity"))
        extras = [num(r.get(k)) for k in extra_controls]
        if x is None or y is None or sev is None or any(v is None for v in extras):
            continue
        ctrl = [sev]
        for p in phases[1:]:
            ctrl.append(1.0 if r.get("phase") == p else 0.0)
        ctrl.extend(extras)
        pairs.append((x, y, ctrl))
    if len(pairs) < 5:
        return {"n": len(pairs), "partial_spearman": None, "ols_r2_increment": None, "phase_baseline": base_phase}
    xr = rankdata([a for a, _, _ in pairs])
    yr = rankdata([b for _, b, _ in pairs])
    C = np.asarray([c for _, _, c in pairs], dtype=float)
    rx = residualize(xr, C)
    ry = residualize(yr, C)
    rho = pearson(list(rx), list(ry))
    yraw = [b for _, b, _ in pairs]
    xraw = [a for a, _, _ in pairs]
    base = ols_r2(yraw, C)
    aug = ols_r2(yraw, np.column_stack([C, xraw]))
    inc = None if base is None or aug is None else aug - base
    return {
        "n": len(pairs),
        "partial_spearman": None if rho is None else round(rho, 4),
        "ols_r2_base": None if base is None else round(base, 4),
        "ols_r2_augmented": None if aug is None else round(aug, 4),
        "ols_r2_increment": None if inc is None else round(inc, 4),
        "phase_baseline": base_phase,
    }


def orthogonal_information(rows, event_ix, audit, rmd):
    audit_by = {e["date"]: e for e in audit.get("events", [])}
    rmd_events = rmd.get("events_ranked_by_rmd3", [])
    rmd_by = {e["date"]: e for e in rmd_events}
    row_by = {r["date"]: r for r in rows}
    recs = []
    for i in event_ix:
        d = rows[i]["date"]
        a, z = audit_by.get(d, {}), rmd_by.get(d, {})
        start = a.get("dual_episode_start")
        sr = row_by.get(start, {}) if start else {}
        net, res = num(sr.get("net_liq_4w_pct")), num(sr.get("reserves_4w_pct"))
        severity = None if net is None or res is None else max(0.0, -2.0 - net) + max(0.0, -2.0 - res)
        recs.append({
            "date": d, "phase": rows[i].get("ma200_phase_final"), "severity": severity,
            "fwd10": rows[i].get("final_fwd_10d"),
            "rmd3": z.get("rmd3"), "price_residual": z.get("price_residual"),
            "breadth_residual": z.get("breadth_residual"), "score_residual": z.get("score_residual"),
            "box_residual": z.get("box_residual"),
        })
    base = {}
    for k in ("rmd3", "price_residual", "breadth_residual", "score_residual", "box_residual"):
        base[k] = partial_rank_corr(recs, k)
    unique = {
        "price_residual": partial_rank_corr(recs, "price_residual", ("breadth_residual", "score_residual")),
        "breadth_residual": partial_rank_corr(recs, "breadth_residual", ("price_residual", "score_residual")),
        "score_residual": partial_rank_corr(recs, "score_residual", ("price_residual", "breadth_residual")),
    }
    return {
        "primary_horizon": "10d",
        "controls": ["DUAL severity", "MA200 phase dummies"],
        "partial_after_severity_phase": base,
        "component_unique_partial_after_other_rmd3_components": unique,
        "records": recs,
        "warning": "n is very small; R2 increments are descriptive and unstable.",
    }


def redundancy_map(rows):
    exclude_exact = {
        "_i", "dual_episode_id", "breadth_trough_i", "box_bottom_i_since_dual", "dual_anchor_i",
    }
    def allowed(k, vals):
        kl = k.lower()
        if k in exclude_exact or k == "date" or k.startswith("D_TO_"):
            return False
        if any(t in kl for t in ("fwd", "mfe", "mae", "future", "outcome", "event_")):
            return False
        if kl.endswith("_id") or kl.endswith("_i") or kl.endswith("rank"):
            return False
        finite = 0
        for v in vals:
            if isinstance(v, bool):
                continue
            if num(v) is not None:
                finite += 1
        return finite >= 500

    keys = sorted(set().union(*(r.keys() for r in rows)))
    cols = {}
    for k in keys:
        vals = [r.get(k) for r in rows]
        if allowed(k, vals):
            cols[k] = [num(v) for v in vals]
    df = pd.DataFrame(cols)
    corr = df.corr(method="spearman", min_periods=500)
    high, mid = [], []
    names = list(corr.columns)
    for a_i in range(len(names)):
        for b_i in range(a_i + 1, len(names)):
            a, b = names[a_i], names[b_i]
            rho = num(corr.loc[a, b])
            if rho is None:
                continue
            overlap = int(df[[a, b]].dropna().shape[0])
            item = {"a": a, "b": b, "rho": round(rho, 4), "abs_rho": round(abs(rho), 4), "n": overlap}
            if abs(rho) >= 0.80:
                high.append(item)
            elif abs(rho) >= 0.60:
                mid.append(item)
    high.sort(key=lambda x: x["abs_rho"], reverse=True)
    mid.sort(key=lambda x: x["abs_rho"], reverse=True)

    graph = {n: set() for n in names}
    for p in high:
        graph[p["a"]].add(p["b"]); graph[p["b"]].add(p["a"])
    seen, families = set(), []
    for n in names:
        if n in seen or not graph[n]:
            continue
        stack, comp = [n], []
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x); comp.append(x); stack.extend(graph[x] - seen)
        if len(comp) >= 2:
            families.append(sorted(comp))
    families.sort(key=lambda x: (-len(x), x))
    return {
        "minimum_finite_observations": 500,
        "high_redundancy_threshold_abs_spearman": 0.80,
        "feature_count": len(names),
        "features": names,
        "high_redundancy_pair_count": len(high),
        "high_redundancy_pairs": high,
        "redundancy_families": families,
        "strong_nonredundant_links_060_080": mid[:100],
    }


def main():
    box = json.loads(BOX.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    rmd = json.loads(RMD.read_text(encoding="utf-8"))
    rows = [dict(r) for r in box.get("daily", [])]
    if len(rows) < 2000:
        raise RuntimeError("Market State Box daily history missing or too short")
    rows = seq.add_dual(rows)
    rows, _ = seq.enrich_sequence(rows)
    rows = add_forward_and_regime(rows)
    event_ix = onset_indices(rows)
    if len(event_ix) != 12:
        raise RuntimeError(f"Frozen Full Sequence event count changed: {len(event_ix)}")

    out = {
        "schema": "TASK14-STAGE2-FINAL-V1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "diagnostic_only": True,
        "production_effect": "none",
        "thresholds_changed": False,
        "study_spec": "research/task14_stage2_final_v1/STUDY_SPEC.md",
        "coverage": {"start": rows[0]["date"], "end": rows[-1]["date"], "observations": len(rows), "full_sequence_events": len(event_ix)},
        "matched_control": matched_controls(rows, event_ix),
        "threshold_stability_surface": threshold_surface(rows),
        "lead_lag_event_study": lead_lag(rows, event_ix),
        "orthogonal_information": orthogonal_information(rows, event_ix, audit, rmd),
        "indicator_redundancy_map": redundancy_map(rows),
        "decision": {
            "may_change_production": False,
            "may_change_existing_forward_oos": False,
            "may_optimize_thresholds_from_surface": False,
            "historical_stage2_status": "FINAL_DIAGNOSTIC_BLOCK_COMPLETE",
        },
        "warnings": [
            "Full Sequence historical n remains small and concentrated in 2022.",
            "FRED current-history values may contain revisions; not ALFRED vintage data.",
            "All five blocks are post-discovery diagnostics and cannot promote rules without prospective evidence.",
        ],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "events": len(event_ix),
        "matched_10d": out["matched_control"]["aggregate"]["10d"],
        "surface_positive_share": out["threshold_stability_surface"]["positive_10d_share_pct"],
        "turns": out["lead_lag_event_study"]["turning_offsets"],
        "orthogonal": out["orthogonal_information"]["partial_after_severity_phase"],
        "redundancy_families": len(out["indicator_redundancy_map"]["redundancy_families"]),
    }))


if __name__ == "__main__":
    main()
