"""Prospective evaluator for frozen Task 1/4 Forward-OOS ledgers V1.

No signal is generated here. No production behavior changes. The evaluator only
scores already-frozen append-only ledgers under the preregistered protocol.
"""
from __future__ import annotations

import json
import math
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import mean

import numpy as np

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "docs/data/market_state_box_v1.json"
RMD = ROOT / "docs/data/residual_mean_reversion_distance_forward_oos_v1.json"
CH = ROOT / "docs/data/task14_challenger_forward_oos_v1.json"
OUT = ROOT / "docs/data/task14_forward_oos_evaluation_v1.json"

FREEZE = "2026-10-02"
SEED = 140401
PERM = 100_000
PRIMARY_N = 20
MIN_MONTHS = 12
MIN_CLUSTERS = 8


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
        avg = ((p + 1) + q) / 2.0
        for k in range(p, q):
            ranks[order[k]] = avg
        p = q
    return np.asarray(ranks, dtype=float)


def corr(x, y):
    x = np.asarray(x, dtype=float); y = np.asarray(y, dtype=float)
    if len(x) < 3 or np.std(x) == 0 or np.std(y) == 0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def spearman(x, y):
    return corr(rankdata(x), rankdata(y))


def perm_spearman(x, y):
    if len(x) < 3:
        return {"rho": None, "p": None, "draws": 0}
    rx, ry = rankdata(x), rankdata(y)
    obs = corr(rx, ry)
    rng = np.random.default_rng(SEED)
    hit = 0
    for _ in range(PERM):
        r = corr(rx, ry[rng.permutation(len(ry))])
        if r is not None and abs(r) >= abs(obs) - 1e-12:
            hit += 1
    return {"rho": round(obs, 4), "p": round((hit + 1) / (PERM + 1), 6), "draws": PERM}


def signflip_exact(diffs):
    d = np.asarray(diffs, dtype=float)
    n = len(d)
    if n == 0 or n > PRIMARY_N:
        return None
    obs = abs(float(d.mean()))
    hit = 0
    total = 1 << n
    for mask in range(total):
        signs = np.fromiter((1.0 if (mask >> i) & 1 else -1.0 for i in range(n)), dtype=float, count=n)
        if abs(float((d * signs).mean())) >= obs - 1e-12:
            hit += 1
    return hit / total


def add_years(d: date, years: int):
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        return d.replace(month=2, day=28, year=d.year + years)


def cluster_count(event_dates, market_index, gap=20):
    xs = sorted(market_index[d] for d in event_dates if d in market_index)
    if not xs:
        return 0
    n = 1
    last = xs[0]
    for x in xs[1:]:
        if x - last > gap:
            n += 1
        last = x
    return n


def readiness(events, discrepancies, market_index):
    ds = sorted(e["event_date"] for e in events)
    n = len(ds)
    clusters = cluster_count(ds, market_index)
    months_ready = False
    if n:
        first = date.fromisoformat(ds[0]); last = date.fromisoformat(ds[-1])
        months_ready = last >= add_years(first, 1)
    return {
        "mature_event_count": n,
        "event_count_ready": n >= PRIMARY_N,
        "calendar_12m_ready": months_ready,
        "independent_cluster_count_20sessions": clusters,
        "cluster_gate_ready": clusters >= MIN_CLUSTERS,
        "unresolved_discrepancy_count": len(discrepancies or []),
        "discrepancy_gate_ready": len(discrepancies or []) == 0,
        "ready": n >= PRIMARY_N and months_ready and clusters >= MIN_CLUSTERS and len(discrepancies or []) == 0,
    }


def laplace_rate(rows, flag=None, value=None):
    s = rows if flag is None else [r for r in rows if bool(r.get(flag)) == bool(value)]
    if not s:
        return None
    y = [1 if r["y"] else 0 for r in s]
    return (sum(y) + 1) / (len(y) + 2)


def loo_hazard(rows):
    preds = []
    for i, test in enumerate(rows):
        train = [r for j, r in enumerate(rows) if j != i]
        base = laplace_rate(train)
        sev = laplace_rate(train, "high_dual_severity", test["high_dual_severity"])
        preds.append({
            "event_date": test["event_date"],
            "y": test["y"],
            "p_base": base,
            "p_severity": base if sev is None else sev,
        })
    def brier(k):
        if not preds:
            return None
        return mean((p[k] - (1.0 if p["y"] else 0.0)) ** 2 for p in preds)
    return {"brier_base": None if not preds else round(brier("p_base"), 6), "brier_severity": None if not preds else round(brier("p_severity"), 6), "records": preds}


def holm_two(p1, p2):
    if p1 is None or p2 is None:
        return {"rmd3": None, "dplus1": None}
    pairs = sorted([("rmd3", p1), ("dplus1", p2)], key=lambda z: z[1])
    first = min(1.0, pairs[0][1] * 2)
    second = max(first, pairs[1][1])
    return {pairs[0][0]: round(first, 6), pairs[1][0]: round(second, 6)}


def main():
    state = json.loads(STATE.read_text(encoding="utf-8"))
    rmd = json.loads(RMD.read_text(encoding="utf-8"))
    ch = json.loads(CH.read_text(encoding="utf-8"))
    rows = state.get("daily") or []
    market_index = {r["date"]: i for i, r in enumerate(rows)}
    closes = [num(r.get("sp500_close")) for r in rows]

    if rmd.get("frozen_through_market_date") != FREEZE or ch.get("frozen_through_market_date") != FREEZE:
        raise RuntimeError("Forward-OOS freeze boundary mismatch")

    # RMD3 primary sample.
    rmd_all = [e for e in rmd.get("events", []) if bool(e.get("mature_10d")) and num(e.get("rmd3")) is not None and num(e.get("fwd_10d")) is not None]
    rmd_all.sort(key=lambda e: e["event_date"])
    rmd_ready = readiness(rmd_all, rmd.get("source_recompute_discrepancies", []), market_index)
    rmd_primary = rmd_all[:PRIMARY_N] if rmd_ready["ready"] else rmd_all
    rmd_test = perm_spearman([e["rmd3"] for e in rmd_primary], [e["fwd_10d"] for e in rmd_primary])
    rmd_status = "PENDING"
    if rmd_ready["ready"]:
        rmd_status = "PASS" if rmd_test["rho"] is not None and rmd_test["rho"] > 0 and rmd_test["p"] <= 0.05 else "FAIL"

    # D+1 paired with Day0 from RMD3 ledger.
    d1 = ch.get("challengers", {}).get("dplus1_entry", {})
    d1_map = {e["event_date"]: e for e in d1.get("events", []) if bool(e.get("mature_10d")) and num(e.get("fwd_10d")) is not None}
    r0_map = {e["event_date"]: e for e in rmd_all}
    paired = []
    for d in sorted(set(d1_map) & set(r0_map)):
        paired.append({"event_date": d, "day0": float(r0_map[d]["fwd_10d"]), "dplus1": float(d1_map[d]["fwd_10d"])})
    d1_ready = readiness(paired, d1.get("source_recompute_discrepancies", []), market_index)
    d1_primary = paired[:PRIMARY_N] if d1_ready["ready"] else paired
    diffs = [r["dplus1"] - r["day0"] for r in d1_primary]
    d1_p = signflip_exact(diffs)
    d1_mean = None if not diffs else mean(diffs)
    d1_status = "PENDING"
    if d1_ready["ready"]:
        d1_status = "PASS" if d1_mean is not None and d1_mean > 0 and d1_p is not None and d1_p <= 0.05 else "FAIL"

    # Severity hazard.
    hz = ch.get("challengers", {}).get("dual_severity_hazard", {})
    hz_all = []
    for e in hz.get("events", []):
        if bool(e.get("mature_10d")) and e.get("break_prior_trough_10d") is not None:
            hz_all.append({"event_date": e["event_date"], "y": bool(e["break_prior_trough_10d"]), "high_dual_severity": bool(e.get("high_dual_severity"))})
    hz_all.sort(key=lambda e: e["event_date"])
    hz_ready = readiness(hz_all, hz.get("source_recompute_discrepancies", []), market_index)
    hz_primary = hz_all[:PRIMARY_N] if hz_ready["ready"] else hz_all
    hz_cal = loo_hazard(hz_primary)
    high = [r["y"] for r in hz_primary if r["high_dual_severity"]]
    low = [r["y"] for r in hz_primary if not r["high_dual_severity"]]
    high_rate = None if not high else sum(high) / len(high)
    low_rate = None if not low else sum(low) / len(low)
    hz_status = "PENDING"
    if hz_ready["ready"]:
        hz_status = "PASS" if hz_cal["brier_severity"] < hz_cal["brier_base"] and high_rate is not None and low_rate is not None and high_rate > low_rate else "FAIL"

    # Early Sequence versus unconditional forward-window baseline.
    early = ch.get("challengers", {}).get("early_sequence", {})
    early_all = [e for e in early.get("events", []) if bool(e.get("mature_10d")) and num(e.get("fwd_10d")) is not None]
    early_all.sort(key=lambda e: e["event_date"])
    early_ready = readiness(early_all, early.get("source_recompute_discrepancies", []), market_index)
    early_primary = early_all[:PRIMARY_N] if early_ready["ready"] else early_all
    early_vals = [float(e["fwd_10d"]) for e in early_primary]
    baseline = []
    if early_primary:
        start = market_index[early_primary[0]["event_date"]]
        end = market_index[early_primary[-1]["event_date"]]
        for i in range(start, end + 1):
            if i + 10 < len(rows) and closes[i] is not None and closes[i + 10] is not None:
                baseline.append(100.0 * (closes[i + 10] / closes[i] - 1.0))
    early_mean = None if not early_vals else mean(early_vals)
    base_mean = None if not baseline else mean(baseline)
    pos_rate = None if not early_vals else sum(v > 0 for v in early_vals) / len(early_vals)
    early_status = "PENDING"
    if early_ready["ready"]:
        early_status = "PASS" if early_mean is not None and base_mean is not None and early_mean > base_mean and pos_rate > 0.5 else "FAIL"

    holm = holm_two(rmd_test.get("p"), d1_p)

    out = {
        "schema": "TASK14-FORWARD-OOS-EVALUATION-V1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "observation_only": True,
        "production_effect": "none",
        "protocol_path": "research/task14_prospective_evaluation_v1/PROTOCOL.md",
        "frozen_through_market_date": FREEZE,
        "primary_confirmatory_n": PRIMARY_N,
        "latest_market_date": rows[-1]["date"] if rows else None,
        "tests": {
            "rmd3": {"status": rmd_status, "readiness": rmd_ready, "primary_sample_n": len(rmd_primary), "rho_10d": rmd_test["rho"], "permutation_two_sided_p": rmd_test["p"], "holm_adjusted_p_two_test_family": holm["rmd3"]},
            "dplus1_entry": {"status": d1_status, "readiness": d1_ready, "primary_sample_n": len(d1_primary), "mean_paired_improvement_pp": None if d1_mean is None else round(d1_mean, 6), "exact_signflip_two_sided_p": None if d1_p is None else round(d1_p, 6), "holm_adjusted_p_two_test_family": holm["dplus1"]},
            "dual_severity_hazard": {"status": hz_status, "readiness": hz_ready, "primary_sample_n": len(hz_primary), "brier_base": hz_cal["brier_base"], "brier_severity": hz_cal["brier_severity"], "high_severity_break_rate": None if high_rate is None else round(high_rate, 6), "low_severity_break_rate": None if low_rate is None else round(low_rate, 6)},
            "early_sequence": {"status": early_status, "readiness": early_ready, "primary_sample_n": len(early_primary), "mean_10d_pct": None if early_mean is None else round(early_mean, 6), "reference_all_days_mean_10d_pct": None if base_mean is None else round(base_mean, 6), "positive_rate": None if pos_rate is None else round(pos_rate, 6)},
        },
        "overall": {
            "any_ready": any(x["readiness"]["ready"] for x in [{"readiness": rmd_ready}, {"readiness": d1_ready}, {"readiness": hz_ready}, {"readiness": early_ready}]),
            "automatic_production_change": False,
            "note": "Primary V1 snapshot locks at the first 20 mature events once all readiness gates for that test are satisfied; later observations are monitoring only.",
        },
        "warnings": [
            "Historical development events through 2026-10-02 are excluded.",
            "No PENDING result should be interpreted as failure or success.",
            "No PASS result changes MAIN automatically; a separate preregistered review is required.",
        ],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: {"status": v["status"], "n": v["primary_sample_n"], "ready": v["readiness"]["ready"]} for k, v in out["tests"].items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
