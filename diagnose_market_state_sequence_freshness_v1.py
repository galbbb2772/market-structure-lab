"""Sequence Freshness / Second-Drop V1.

Diagnostic-only study of the already-frozen D_TO_BOTH_REBOUND_SCORE events.
No event definition, strategy rule, or production sizing is changed.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

SRC = Path("docs/data/market_state_sequence_event_audit_v1.json")
OUT = Path("docs/data/market_state_sequence_freshness_v1.json")

FEATURES = (
    "confirmation_lag_sessions",
    "ret_5d_pct",
    "ret_20d_pct",
    "ret_60d_pct",
    "drawdown_from_60d_high_pct",
    "breadth_20d_pct",
    "min_breadth_pct_since_dual",
    "breadth_rebound_distance_pp",
    "box_position",
    "min_box_position_since_dual",
    "box_rebound_distance",
    "market_score",
    "market_score_d1",
    "market_score_d3",
)


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def rankdata(values):
    # Average ranks for ties, 1-based. Tiny N and no scipy dependency needed.
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


def spearman_pairs(events, feature, outcome):
    pairs = []
    for e in events:
        a = num(e.get(feature)); b = num(e.get(outcome))
        if a is not None and b is not None:
            pairs.append((a, b))
    if len(pairs) < 3:
        return {"n": len(pairs), "rho": None}
    x = [p[0] for p in pairs]; y = [p[1] for p in pairs]
    r = pearson(rankdata(x), rankdata(y))
    return {"n": len(pairs), "rho": None if r is None else round(r, 4)}


def loo_spearman(events, feature, outcome):
    vals = []
    for i in range(len(events)):
        r = spearman_pairs(events[:i] + events[i + 1:], feature, outcome)["rho"]
        if r is not None:
            vals.append(r)
    return {
        "n_loo": len(vals),
        "min_rho": None if not vals else round(min(vals), 4),
        "max_rho": None if not vals else round(max(vals), 4),
        "median_rho": None if not vals else round(median(vals), 4),
    }


def lag_band(e):
    x = num(e.get("confirmation_lag_sessions"))
    if x is None: return "missing"
    if x <= 5: return "0_5"
    if x <= 10: return "6_10"
    if x <= 20: return "11_20"
    return "21_plus"


def breadth_band(e):
    x = num(e.get("breadth_20d_pct"))
    if x is None: return "missing"
    if x <= 20: return "le20"
    if x <= 40: return "20_40"
    if x <= 60: return "40_60"
    return "gt60"


def ret20_band(e):
    x = num(e.get("ret_20d_pct"))
    if x is None: return "missing"
    if x <= -5: return "le_minus5"
    if x <= 0: return "minus5_0"
    return "gt0"


def summarize(events):
    out = {"n": len(events)}
    for h in (1, 3, 5, 10):
        vals = [num(e.get(f"fwd_{h}d")) for e in events]
        vals = [v for v in vals if v is not None]
        out[f"{h}d"] = {
            "n": len(vals),
            "mean_pct": None if not vals else round(mean(vals), 4),
            "median_pct": None if not vals else round(median(vals), 4),
            "positive_pct": None if not vals else round(100.0 * sum(v > 0 for v in vals) / len(vals), 2),
        }
    f5 = [num(e.get("fwd_5d")) for e in events]; f5 = [v for v in f5 if v is not None]
    f10 = [num(e.get("fwd_10d")) for e in events]; f10 = [v for v in f10 if v is not None]
    mae = [num(e.get("mae_10d")) for e in events]; mae = [v for v in mae if v is not None]
    mfe = [num(e.get("mfe_10d")) for e in events]; mfe = [v for v in mfe if v is not None]
    out["second_drop_5d_pct"] = None if not f5 else round(100.0 * sum(v < 0 for v in f5) / len(f5), 2)
    out["second_drop_10d_pct"] = None if not f10 else round(100.0 * sum(v < 0 for v in f10) / len(f10), 2)
    out["severe_adverse_10d_pct"] = None if not mae else round(100.0 * sum(v <= -5 for v in mae) / len(mae), 2)
    out["mfe_10d_mean_pct"] = None if not mfe else round(mean(mfe), 4)
    out["mae_10d_mean_pct"] = None if not mae else round(mean(mae), 4)
    return out


def grouped(events, fn, ordered_keys):
    return {k: summarize([e for e in events if fn(e) == k]) for k in ordered_keys}


def main():
    src = json.loads(SRC.read_text(encoding="utf-8"))
    if src.get("schema") != "MARKET-STATE-SEQUENCE-EVENT-AUDIT-V1":
        raise RuntimeError("unexpected event-audit schema")
    events = [dict(e) for e in src.get("events", [])]
    if len(events) != 12:
        raise RuntimeError(f"frozen V1 historical event count drifted: {len(events)} != 12")
    if src.get("event_definition") != "D_TO_BOTH_REBOUND_SCORE":
        raise RuntimeError("event definition drifted")

    for e in events:
        b = num(e.get("breadth_20d_pct")); bl = num(e.get("min_breadth_pct_since_dual"))
        e["breadth_rebound_distance_pp"] = None if b is None or bl is None else round(b - bl, 4)
        bp = num(e.get("box_position")); bmin = num(e.get("min_box_position_since_dual"))
        e["box_rebound_distance"] = None if bp is None or bmin is None else round(bp - bmin, 4)
        e["second_drop_5d"] = num(e.get("fwd_5d")) is not None and num(e.get("fwd_5d")) < 0
        e["second_drop_10d"] = num(e.get("fwd_10d")) is not None and num(e.get("fwd_10d")) < 0
        e["severe_adverse_10d"] = num(e.get("mae_10d")) is not None and num(e.get("mae_10d")) <= -5
        e["freshness_lag_band"] = lag_band(e)
        e["confirmation_breadth_band"] = breadth_band(e)
        e["prior_20d_return_band"] = ret20_band(e)

    correlations = {}
    for feature in FEATURES:
        correlations[feature] = {}
        for outcome in ("fwd_5d", "fwd_10d"):
            correlations[feature][outcome] = {
                **spearman_pairs(events, feature, outcome),
                "leave_one_out": loo_spearman(events, feature, outcome),
            }

    year_count = {}
    phase_count = {}
    for e in events:
        year_count[str(e.get("year"))] = year_count.get(str(e.get("year")), 0) + 1
        p = str(e.get("ma200_phase"))
        phase_count[p] = phase_count.get(p, 0) + 1

    out = {
        "schema": "MARKET-STATE-SEQUENCE-FRESHNESS-V1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "diagnostic_only": True,
        "thresholds_changed": False,
        "preregistration_path": "research/market_state_sequence_freshness_v1/PREREGISTRATION.md",
        "source_schema": src.get("schema"),
        "event_definition": src.get("event_definition"),
        "event_count": len(events),
        "fixed_bands": {
            "confirmation_lag_sessions": ["0_5", "6_10", "11_20", "21_plus"],
            "confirmation_breadth_percentile": ["le20", "20_40", "40_60", "gt60"],
            "prior_20d_spx_return_pct": ["le_minus5", "minus5_0", "gt0"],
            "severe_adverse_10d_mae_pct": -5.0,
        },
        "full_summary": summarize(events),
        "fixed_band_summaries": {
            "confirmation_lag": grouped(events, lag_band, ["0_5", "6_10", "11_20", "21_plus"]),
            "confirmation_breadth": grouped(events, breadth_band, ["le20", "20_40", "40_60", "gt60"]),
            "prior_20d_return": grouped(events, ret20_band, ["le_minus5", "minus5_0", "gt0"]),
        },
        "continuous_spearman": correlations,
        "concentration": {"by_year_count": year_count, "by_phase_count": phase_count},
        "events_sorted_by_confirmation_lag": sorted(events, key=lambda e: (num(e.get("confirmation_lag_sessions")) is None, num(e.get("confirmation_lag_sessions")) or 10**9)),
        "decision": {
            "may_change_production": False,
            "may_change_existing_forward_oos_shadow": False,
            "status": "mechanism_diagnostic_only",
            "note": "Any freshness rule requires a separate preregistration and independent forward test.",
        },
        "warnings": [
            "The 12 historical events were already observed before this freshness diagnostic; all mechanism findings are post-discovery diagnostics, not fresh OOS evidence.",
            "Fixed bands are coarse descriptive bands and must not be optimized or promoted from this V1 output.",
            "FRED current-history data can contain revisions and is not ALFRED vintage data.",
        ],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Wrote", OUT)
    print(json.dumps({"event_count": out["event_count"], "full": out["full_summary"], "year": year_count, "phase": phase_count}, ensure_ascii=False))


if __name__ == "__main__":
    main()
