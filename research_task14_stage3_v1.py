"""Task 1/4 Stage-3 Evidence Audit V1.

Research-only. Tests evidence independence, paired D+1 timing, RMD3 incremental
information, hazard calibration, outlier sensitivity, and multiple testing.
No production/OOS definition is changed.
"""
from __future__ import annotations

import itertools
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

import numpy as np

ROOT = Path(__file__).resolve().parent
BOX = ROOT / "docs/data/market_state_box_v1.json"
AUDIT = ROOT / "docs/data/market_state_sequence_event_audit_v1.json"
RMD = ROOT / "docs/data/residual_mean_reversion_distance_v1.json"
EXT = ROOT / "docs/data/task14_extended_diagnostics_v1.json"
STAGE2 = ROOT / "docs/data/task14_stage2_research_v1.json"
CHALL = ROOT / "docs/data/task14_challenger_forward_oos_v1.json"
RMD_OOS = ROOT / "docs/data/residual_mean_reversion_distance_forward_oos_v1.json"
OUT = ROOT / "docs/data/task14_stage3_evidence_audit_v1.json"

SEED = 140315
BOOT = 50_000
PERM = 100_000
H = (3, 5, 10, 20)


def num(x):
    try:
        z = float(x)
        return z if math.isfinite(z) else None
    except (TypeError, ValueError):
        return None


def rankdata(a):
    a = list(map(float, a))
    order = sorted(range(len(a)), key=lambda i: a[i])
    ranks = [0.0] * len(a)
    p = 0
    while p < len(order):
        q = p + 1
        while q < len(order) and a[order[q]] == a[order[p]]:
            q += 1
        r = ((p + 1) + q) / 2.0
        for k in range(p, q):
            ranks[order[k]] = r
        p = q
    return np.asarray(ranks, dtype=float)


def corr(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) < 3 or np.std(x) == 0 or np.std(y) == 0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def spearman(x, y):
    return corr(rankdata(x), rankdata(y))


def ret(closes, i, h, delay=0):
    j = i + delay
    k = j + h
    if j < 0 or k >= len(closes) or closes[j] is None or closes[k] is None:
        return None
    return 100.0 * (closes[k] / closes[j] - 1.0)


def bootstrap_ci(values, draws=BOOT, seed=SEED):
    a = np.asarray([float(v) for v in values if v is not None], dtype=float)
    if len(a) == 0:
        return {"n": 0, "mean": None, "ci95": [None, None]}
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(a), size=(draws, len(a)))
    m = a[idx].mean(axis=1)
    return {
        "n": int(len(a)),
        "mean": round(float(a.mean()), 4),
        "ci95": [round(float(np.quantile(m, 0.025)), 4), round(float(np.quantile(m, 0.975)), 4)],
    }


def exact_signflip_p(diffs):
    d = np.asarray([float(x) for x in diffs], dtype=float)
    n = len(d)
    if n == 0:
        return None
    obs = abs(float(d.mean()))
    hit = 0
    total = 1 << n
    for mask in range(total):
        signs = np.fromiter((1.0 if (mask >> i) & 1 else -1.0 for i in range(n)), dtype=float, count=n)
        if abs(float((d * signs).mean())) >= obs - 1e-12:
            hit += 1
    return hit / total


def permutation_spearman(x, y, draws=PERM, seed=SEED):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    obs = spearman(x, y)
    if obs is None:
        return {"n": len(x), "rho": None, "two_sided_p": None}
    rx = rankdata(x)
    ry = rankdata(y)
    rng = np.random.default_rng(seed)
    hit = 0
    for _ in range(draws):
        rp = ry[rng.permutation(len(ry))]
        r = corr(rx, rp)
        if r is not None and abs(r) >= abs(obs) - 1e-12:
            hit += 1
    return {"n": len(x), "rho": round(obs, 4), "two_sided_p": round((hit + 1) / (draws + 1), 6), "draws": draws}


def residualize(y, X):
    y = np.asarray(y, dtype=float)
    X = np.asarray(X, dtype=float)
    X = np.column_stack([np.ones(len(X)), X])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return y - X @ beta


def partial_spearman(x, y, controls):
    rx, ry = rankdata(x), rankdata(y)
    C = np.asarray(controls, dtype=float)
    # Rank continuous severity in col0; phase dummies remain 0/1.
    if C.ndim == 1:
        C = C.reshape(-1, 1)
    if C.shape[1] >= 1:
        C[:, 0] = rankdata(C[:, 0])
    a = residualize(rx, C)
    b = residualize(ry, C)
    r = corr(a, b)
    return None if r is None else round(r, 4)


def bh_adjust(pvals):
    keys = list(pvals)
    m = len(keys)
    order = sorted(keys, key=lambda k: pvals[k])
    raw = [pvals[k] for k in order]
    adj = [0.0] * m
    running = 1.0
    for i in range(m - 1, -1, -1):
        rank = i + 1
        running = min(running, raw[i] * m / rank)
        adj[i] = min(1.0, running)
    return {order[i]: round(adj[i], 6) for i in range(m)}


def laplace_rate(records, predicate=None):
    s = records if predicate is None else [r for r in records if predicate(r)]
    if not s:
        return None
    y = [1 if r["y"] else 0 for r in s]
    return (sum(y) + 1.0) / (len(y) + 2.0)


def brier(records, key):
    vals = [(float(r[key]) - (1.0 if r["y"] else 0.0)) ** 2 for r in records]
    return None if not vals else round(mean(vals), 6)


def main():
    box = json.loads(BOX.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    rmd = json.loads(RMD.read_text(encoding="utf-8"))
    ext = json.loads(EXT.read_text(encoding="utf-8"))
    stage2 = json.loads(STAGE2.read_text(encoding="utf-8"))
    chall = json.loads(CHALL.read_text(encoding="utf-8"))
    rmd_oos = json.loads(RMD_OOS.read_text(encoding="utf-8"))

    daily = box.get("daily") or []
    dates = [r["date"] for r in daily]
    closes = [num(r.get("sp500_close")) for r in daily]
    idx = {d: i for i, d in enumerate(dates)}
    events = [dict(e) for e in audit.get("events", [])]
    if len(events) != 12:
        raise RuntimeError(f"Expected 12 frozen completion events, got {len(events)}")
    events.sort(key=lambda e: idx[e["date"]])

    # Populate same-close forward returns, including 20D absent from event-audit source.
    for e in events:
        i = idx[e["date"]]
        for h in H:
            e[f"calc_fwd_{h}d"] = ret(closes, i, h, 0)
            e[f"calc_dplus1_fwd_{h}d"] = ret(closes, i, h, 1)

    # 1) Dependence clustering by completion-date market-session gap.
    def make_clusters(max_gap):
        groups = []
        cur = []
        last_i = None
        for e in events:
            ii = idx[e["date"]]
            if last_i is None or ii - last_i <= max_gap:
                cur.append(e)
            else:
                groups.append(cur)
                cur = [e]
            last_i = ii
        if cur:
            groups.append(cur)
        return groups

    cluster_defs = {}
    for gap in (10, 20, 30):
        groups = make_clusters(gap)
        cluster_defs[str(gap)] = {
            "n_clusters": len(groups),
            "sizes": [len(g) for g in groups],
            "clusters": [[e["date"] for e in g] for g in groups],
        }
    primary_clusters = make_clusters(20)
    cluster_weighted = {}
    for h in (5, 10, 20):
        means = []
        for g in primary_clusters:
            v = [e[f"calc_fwd_{h}d"] for e in g if e[f"calc_fwd_{h}d"] is not None]
            if v:
                means.append(mean(v))
        cluster_weighted[f"{h}d"] = bootstrap_ci(means, seed=SEED + h)

    # Equal-year weighting (descriptive antidote to 2022 event-count dominance).
    years = sorted(set(int(e["year"]) for e in events))
    year_weighted = {}
    for h in (5, 10, 20):
        ym = {}
        for y in years:
            vals = [e[f"calc_fwd_{h}d"] for e in events if int(e["year"]) == y and e[f"calc_fwd_{h}d"] is not None]
            if vals:
                ym[str(y)] = round(mean(vals), 4)
        year_weighted[f"{h}d"] = {"year_means": ym, "equal_year_mean_pct": round(mean(ym.values()), 4) if ym else None}

    # 2) D+1 paired event-by-event test.
    dplus = {}
    dplus_p = {}
    for h in (5, 10, 20):
        recs, diffs = [], []
        for e in events:
            a = e[f"calc_fwd_{h}d"]
            b = e[f"calc_dplus1_fwd_{h}d"]
            if a is None or b is None:
                continue
            diff = b - a
            diffs.append(diff)
            recs.append({"date": e["date"], "day0_pct": round(a, 4), "dplus1_pct": round(b, 4), "paired_diff_pp": round(diff, 4)})
        p = exact_signflip_p(diffs)
        dplus_p[f"dplus1_{h}d"] = p
        dplus[f"{h}d"] = {
            "n": len(diffs),
            "day0_mean_pct": round(mean(r["day0_pct"] for r in recs), 4),
            "dplus1_mean_pct": round(mean(r["dplus1_pct"] for r in recs), 4),
            "mean_paired_improvement_pp": round(mean(diffs), 4),
            "median_paired_improvement_pp": round(median(diffs), 4),
            "improved_event_count": sum(d > 0 for d in diffs),
            "exact_signflip_two_sided_p": None if p is None else round(p, 6),
            "paired_diff_bootstrap": bootstrap_ci(diffs, seed=SEED + 100 + h),
            "records": recs,
        }

    # 3) RMD3 direct permutation, partial correlation, and cluster-level correlation.
    rmap = {e["date"]: e for e in rmd.get("events_ranked_by_rmd3", [])}
    hmap = {e["date"]: e for e in ext.get("second_leg_hazard", {}).get("events", [])}
    aligned = []
    for e in events:
        rr = rmap.get(e["date"], {})
        hh = hmap.get(e["date"], {})
        if num(rr.get("rmd3")) is None:
            continue
        aligned.append({
            "date": e["date"],
            "rmd3": float(rr["rmd3"]),
            "severity": float(num(hh.get("dual_severity_pp_beyond_threshold")) or 0.0),
            "phase": e.get("ma200_phase"),
            "fwd3": e["calc_fwd_3d"],
            "fwd5": e["calc_fwd_5d"],
            "fwd10": e["calc_fwd_10d"],
        })
    rmd_perm = {}
    for h in (3, 5, 10):
        xs = [r["rmd3"] for r in aligned if r[f"fwd{h}"] is not None]
        ys = [r[f"fwd{h}"] for r in aligned if r[f"fwd{h}"] is not None]
        rmd_perm[f"{h}d"] = permutation_spearman(xs, ys, seed=SEED + 200 + h)

    xs = [r["rmd3"] for r in aligned]
    ys = [r["fwd10"] for r in aligned]
    controls = [[r["severity"], 1.0 if r["phase"] == "bear_falling" else 0.0, 1.0 if r["phase"] == "bear_recovery" else 0.0] for r in aligned]
    partial = partial_spearman(xs, ys, controls)

    cluster_pairs = []
    for g in primary_clusters:
        rr = [rmap.get(e["date"], {}) for e in g]
        x = [num(r.get("rmd3")) for r in rr]
        y = [e["calc_fwd_10d"] for e in g]
        pairs = [(a, b) for a, b in zip(x, y) if a is not None and b is not None]
        if pairs:
            cluster_pairs.append((mean(a for a, _ in pairs), mean(b for _, b in pairs), [e["date"] for e in g]))
    cluster_rho = spearman([x for x, _, _ in cluster_pairs], [y for _, y, _ in cluster_pairs]) if len(cluster_pairs) >= 3 else None

    # 4) Hazard leave-one-out calibration versus unconditional base rate.
    median_rmd = float(stage2.get("rmd_x_dual_severity", {}).get("rmd3_historical_median", 0.762857))
    hz = []
    for e in ext.get("second_leg_hazard", {}).get("events", []):
        if e.get("break_prior_trough_10d") is None or num(e.get("rmd3")) is None:
            continue
        sev = float(num(e.get("dual_severity_pp_beyond_threshold")) or 0.0)
        hz.append({"date": e["date"], "y": bool(e["break_prior_trough_10d"]), "severity_high": sev > 6.0, "rmd_high": float(e["rmd3"]) >= median_rmd})
    loo = []
    for i, test in enumerate(hz):
        train = [r for j, r in enumerate(hz) if j != i]
        base = laplace_rate(train)
        ps = laplace_rate(train, lambda r, z=test: r["severity_high"] == z["severity_high"])
        pr = laplace_rate(train, lambda r, z=test: r["rmd_high"] == z["rmd_high"])
        p2 = laplace_rate(train, lambda r, z=test: r["severity_high"] == z["severity_high"] and r["rmd_high"] == z["rmd_high"])
        loo.append({
            "date": test["date"], "y": test["y"],
            "p_base": base,
            "p_severity": base if ps is None else ps,
            "p_rmd": base if pr is None else pr,
            "p_2d": base if p2 is None else p2,
        })
    hazard_cal = {
        "n": len(loo),
        "event_rate_pct": round(100.0 * sum(r["y"] for r in loo) / len(loo), 2) if loo else None,
        "brier": {k: brier(loo, k) for k in ("p_base", "p_severity", "p_rmd", "p_2d")},
        "records": [{**r, **{k: round(v, 4) if isinstance(v, float) else v for k, v in r.items() if k.startswith("p_")}} for r in loo],
    }

    # 5) Single-event deletion stress.
    loo_stress = []
    for drop in events:
        keep = [e for e in events if e["date"] != drop["date"]]
        seq10 = mean(e["calc_fwd_10d"] for e in keep if e["calc_fwd_10d"] is not None)
        dd = []
        xx, yy = [], []
        for e in keep:
            if e["calc_fwd_10d"] is not None and e["calc_dplus1_fwd_10d"] is not None:
                dd.append(e["calc_dplus1_fwd_10d"] - e["calc_fwd_10d"])
            rr = rmap.get(e["date"], {})
            if num(rr.get("rmd3")) is not None and e["calc_fwd_10d"] is not None:
                xx.append(float(rr["rmd3"])); yy.append(e["calc_fwd_10d"])
        loo_stress.append({"dropped": drop["date"], "sequence_10d_mean_pct": round(seq10, 4), "dplus1_10d_mean_improvement_pp": round(mean(dd), 4), "rmd3_10d_rho": None if spearman(xx, yy) is None else round(spearman(xx, yy), 4)})

    def range_of(key):
        vals = [num(r.get(key)) for r in loo_stress]
        vals = [v for v in vals if v is not None]
        return {"min": None if not vals else round(min(vals), 4), "median": None if not vals else round(median(vals), 4), "max": None if not vals else round(max(vals), 4)}

    # 6) Multiple-testing family.
    pvals = {}
    for h in (5, 10, 20):
        pvals[f"sequence_placebo_{h}d"] = float(stage2["placebo_random_dates"]["horizons"][str(h)]["empirical_one_sided_p"])
        pvals[f"dplus1_paired_{h}d"] = float(dplus_p[f"dplus1_{h}d"])
    for h in (3, 5, 10):
        pvals[f"rmd3_perm_{h}d"] = float(rmd_perm[f"{h}d"]["two_sided_p"])
    bh = bh_adjust(pvals)
    tests = {}
    m = len(pvals)
    for k, p in pvals.items():
        tests[k] = {"raw_p": round(p, 6), "bonferroni_p": round(min(1.0, p * m), 6), "bh_fdr_p": bh[k]}

    # Evidence gates are descriptive and deliberately conservative.
    year_counts = {}
    for e in events:
        year_counts[str(e["year"])] = year_counts.get(str(e["year"]), 0) + 1
    max_year_share = max(year_counts.values()) / len(events)
    rmd_forward = int(rmd_oos.get("forward_event_count", 0))
    chall_counts = {k: int(v.get("forward_event_count", 0)) for k, v in chall.get("challengers", {}).items()}
    gates = {
        "effective_20session_clusters_gte8": len(primary_clusters) >= 8,
        "max_single_year_share_le50pct": max_year_share <= 0.50,
        "sequence_placebo_10d_p_le_0_10": pvals["sequence_placebo_10d"] <= 0.10,
        "rmd3_perm_10d_p_le_0_10": pvals["rmd3_perm_10d"] <= 0.10,
        "dplus1_paired_10d_p_le_0_10": pvals["dplus1_paired_10d"] <= 0.10,
        "rmd3_forward_events_gte20": rmd_forward >= 20,
        "all_challengers_forward_events_gte20": bool(chall_counts) and all(v >= 20 for v in chall_counts.values()),
    }

    out = {
        "schema": "TASK14-STAGE3-EVIDENCE-AUDIT-V1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "diagnostic_only": True,
        "production_effect": "none",
        "thresholds_changed": False,
        "coverage": {"market_start": dates[0], "market_end": dates[-1], "completion_events": len(events)},
        "event_independence": {"cluster_rule_primary": "consecutive completion events <=20 market sessions apart share a cluster", "cluster_sensitivity": cluster_defs, "primary_cluster_weighted_forward": cluster_weighted, "year_counts": year_counts, "max_single_year_share_pct": round(100.0 * max_year_share, 2), "equal_year_weighting": year_weighted},
        "dplus1_paired_test": dplus,
        "rmd3_evidence": {"permutation": rmd_perm, "partial_spearman_10d_controlling_severity_and_phase": partial, "cluster_level_20session": {"n_clusters_with_rmd": len(cluster_pairs), "rho": None if cluster_rho is None else round(cluster_rho, 4), "records": [{"rmd3_mean": round(x, 6), "fwd10_mean_pct": round(y, 4), "dates": ds} for x, y, ds in cluster_pairs]}},
        "hazard_loo_calibration": hazard_cal,
        "single_event_deletion": {"records": loo_stress, "ranges": {"sequence_10d_mean_pct": range_of("sequence_10d_mean_pct"), "dplus1_10d_mean_improvement_pp": range_of("dplus1_10d_mean_improvement_pp"), "rmd3_10d_rho": range_of("rmd3_10d_rho")}},
        "multiple_testing": {"family_size": m, "note": "Retrospective diagnostic family, not a preregistered confirmatory family.", "tests": tests},
        "forward_oos_status": {"rmd3_forward_event_count": rmd_forward, "challenger_forward_event_counts": chall_counts},
        "evidence_gates": gates,
        "decision": {"may_change_production": False, "may_change_existing_forward_oos": False, "status": "evidence_quality_diagnostic_only", "next_requirement": "Accumulate genuinely future OOS events; do not tune historical rules from this audit."},
        "warnings": [
            "Only 12 historical completion events exist and 2022 dominates the event count.",
            "Cluster and equal-year weighting reduce pseudo-replication but cannot manufacture independent regimes.",
            "Partial correlation and hazard calibration are unstable at n=12 and are descriptive only.",
            "Multiple-testing adjustments are retrospective diagnostics, not formal preregistered confirmatory inference.",
        ],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Wrote", OUT)
    print(json.dumps({
        "clusters20": len(primary_clusters),
        "cluster_sizes20": [len(x) for x in primary_clusters],
        "dplus1_10d": dplus["10d"],
        "rmd3_perm_10d": rmd_perm["10d"],
        "rmd3_partial_10d": partial,
        "hazard_brier": hazard_cal["brier"],
        "gates": gates,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
