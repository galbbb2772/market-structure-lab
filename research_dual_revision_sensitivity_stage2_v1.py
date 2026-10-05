"""DUAL / FRED measurement-revision sensitivity diagnostics.

Historical / diagnostic only. Rebuilds the center DUAL daily panel with the
existing Sequence V1 timing implementation, hard-validates frozen event identity,
then perturbs only the two 4-week liquidity percentage-change fields.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

import build_market_state_sequence_v1 as seq
import research_modules_stage2_v1 as mod

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "docs/data/market_state_box_v1.json"
OUT = ROOT / "docs/data/dual_revision_sensitivity_stage2_v1.json"
SHIFTS = (-0.50, 0.00, 0.50)
H = (5, 10, 20)
EXPECTED_FULL_DATES = [
    "2019-06-04", "2022-01-26", "2022-03-09", "2022-05-13",
    "2022-05-23", "2022-06-07", "2022-07-01", "2022-07-12",
    "2022-09-28", "2022-10-13", "2022-10-25", "2023-01-04",
]


def num(x):
    return mod.num(x)


def qtile(xs, p):
    return mod.qtile(xs, p)


def add_forwards(rows):
    closes = [num(r.get("sp500_close")) for r in rows]
    for i, r in enumerate(rows):
        c = closes[i]
        for h in H:
            if c not in (None, 0) and i + h < len(rows) and closes[i + h] is not None:
                r[f"sens_fwd_{h}d"] = 100.0 * (closes[i + h] / c - 1.0)
            else:
                r[f"sens_fwd_{h}d"] = None
    return rows


def onset(rows, pred, gap=None):
    out = []
    prev = False
    last = -10**9
    for i, r in enumerate(rows):
        cur = bool(pred(r))
        if cur and not prev and (gap is None or i - last >= gap):
            out.append(r)
            last = i
        prev = cur
    return out


def event_sets(rows):
    dual = onset(rows, lambda r: bool(r.get("dual_drain")), gap=None)
    early = onset(
        rows,
        lambda r: bool(r.get("D_TO_BREADTH_LOW")) and bool(r.get("box_bottom_since_dual")) and bool(r.get("breadth_rebound_since_dual")),
        gap=5,
    )
    full = onset(rows, lambda r: bool(r.get("D_TO_BOTH_REBOUND_SCORE")), gap=5)
    return {"dual": dual, "early": early, "full": full}


def ret_summary(events):
    out = {"n": len(events)}
    for h in H:
        vals = [num(r.get(f"sens_fwd_{h}d")) for r in events]
        vals = [x for x in vals if x is not None]
        out[f"{h}d"] = {"n": len(vals)} if not vals else {
            "n": len(vals),
            "mean_pct": round(mean(vals), 4),
            "median_pct": round(median(vals), 4),
            "positive_pct": round(100.0 * sum(x > 0 for x in vals) / len(vals), 2),
            "p10_pct": round(qtile(vals, 0.10), 4),
            "p90_pct": round(qtile(vals, 0.90), 4),
        }
    return out


def shifted_rows(base_rows, net_shift, reserve_shift):
    rows = [dict(r) for r in base_rows]
    for i, r in enumerate(rows):
        r["_i"] = i
        nl = num(r.get("net_liq_4w_pct")); rv = num(r.get("reserves_4w_pct"))
        r["sens_net_liq_4w_pct"] = None if nl is None else nl + net_shift
        r["sens_reserves_4w_pct"] = None if rv is None else rv + reserve_shift
        r["dual_drain"] = bool(
            r["sens_net_liq_4w_pct"] is not None and r["sens_reserves_4w_pct"] is not None
            and r["sens_net_liq_4w_pct"] <= -2.0 and r["sens_reserves_4w_pct"] <= -2.0
        )
        for k in (
            "dual_episode_id", "dual_episode_day", "days_since_dual", "dual_phase", "dual_anchor_i", "recent_dual_10d",
            "breadth_trough_since_dual", "breadth_trough_i", "box_bottom_i_since_dual", "breadth_low_since_dual",
            "box_bottom_since_dual", "breadth_improving", "breadth_rebound_since_dual", "score_recovery_confirmed",
            "D_TO_BREADTH_LOW", "D_TO_BREADTH_REBOUND", "D_TO_BOX_BOTTOM", "D_TO_REBOUND_SCORE", "D_TO_BOTH_REBOUND_SCORE",
        ):
            r.pop(k, None)
    rows, _ = seq.enrich_sequence(rows)
    return add_forwards(rows)


def event_identity(center, variant):
    ci = sorted(int(r["_i"]) for r in center)
    vi = sorted(int(r["_i"]) for r in variant)
    cs, vs = set(ci), set(vi)
    union = cs | vs
    exact = len(cs & vs)

    def near_count(a, b, window=3):
        if not b:
            return 0
        return sum(min(abs(x - y) for y in b) <= window for x in a)

    nearest = [min(abs(x - y) for y in vi) for x in ci] if ci and vi else []
    return {
        "center_count": len(ci),
        "variant_count": len(vi),
        "exact_overlap_count": exact,
        "exact_jaccard": None if not union else round(exact / len(union), 4),
        "center_events_with_variant_within_3_sessions_n": near_count(ci, vi, 3),
        "center_events_with_variant_within_3_sessions_pct": None if not ci else round(100.0 * near_count(ci, vi, 3) / len(ci), 2),
        "variant_events_with_center_within_3_sessions_n": near_count(vi, ci, 3),
        "variant_events_with_center_within_3_sessions_pct": None if not vi else round(100.0 * near_count(vi, ci, 3) / len(vi), 2),
        "median_nearest_gap_from_center_sessions": None if not nearest else round(median(nearest), 2),
    }


def aggregate_stability(cells, key):
    noncenter = [c for c in cells if not c["is_center"]]
    counts = [c["events"][key]["count"] for c in noncenter]
    jac = [c["vs_center"][key]["exact_jaccard"] for c in noncenter if c["vs_center"][key]["exact_jaccard"] is not None]
    ret = [c["vs_center"][key]["center_events_with_variant_within_3_sessions_pct"] for c in noncenter if c["vs_center"][key]["center_events_with_variant_within_3_sessions_pct"] is not None]
    center_count = next(c["events"][key]["count"] for c in cells if c["is_center"])
    preserved = sum(c["vs_center"][key]["center_events_with_variant_within_3_sessions_n"] == center_count for c in noncenter)
    return {
        "noncenter_cells": len(noncenter),
        "event_count_min_median_max": [min(counts), round(median(counts), 2), max(counts)],
        "minimum_exact_jaccard": None if not jac else round(min(jac), 4),
        "minimum_center_event_retention_within_3_sessions_pct": None if not ret else round(min(ret), 2),
        "cells_preserving_every_center_event_within_3_sessions": preserved,
    }


def validate_center(center_sets):
    counts = {k: len(v) for k, v in center_sets.items()}
    if counts != {"dual": 58, "early": 15, "full": 12}:
        raise RuntimeError(f"center reproduction count failure: {counts}")
    full_dates = [r["date"] for r in center_sets["full"]]
    if full_dates != EXPECTED_FULL_DATES:
        raise RuntimeError(f"center Full Sequence date identity failure: {full_dates}")
    return {"counts": counts, "full_dates_exact_match": True}


def main():
    src = json.loads(SRC.read_text(encoding="utf-8"))
    raw = src.get("daily") or []
    if not raw:
        raise RuntimeError("market_state_box_v1 daily rows missing")

    # Same existing current-history FRED reconstruction/timing as Sequence V1.
    base = seq.add_dual([dict(r) for r in raw])
    base = add_forwards(base)

    built = {}
    center_sets = None
    center_key = "net+0.00|res+0.00"
    for ns in SHIFTS:
        for rs in SHIFTS:
            key = f"net{ns:+.2f}|res{rs:+.2f}"
            rows = shifted_rows(base, ns, rs)
            sets = event_sets(rows)
            built[key] = {"rows": rows, "sets": sets, "net_shift_pp": ns, "reserve_shift_pp": rs}
            if ns == 0 and rs == 0:
                center_sets = sets
    if center_sets is None:
        raise RuntimeError("center cell missing")
    center_reproduction = validate_center(center_sets)

    cells = []
    for key, d in built.items():
        sets = d["sets"]
        cell = {
            "key": key,
            "net_liq_shift_pp": d["net_shift_pp"],
            "reserves_shift_pp": d["reserve_shift_pp"],
            "is_center": key == center_key,
            "events": {},
            "vs_center": {},
        }
        for name in ("dual", "early", "full"):
            ev = sets[name]
            cell["events"][name] = {
                "count": len(ev),
                "dates": [r["date"] for r in ev],
                "returns": None if name == "dual" else ret_summary(ev),
            }
            cell["vs_center"][name] = event_identity(center_sets[name], ev)
        cells.append(cell)

    center = next(c for c in cells if c["is_center"])
    out = {
        "schema": "DUAL-REVISION-SENSITIVITY-STAGE2-V1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "diagnostic_only": True,
        "production_effect": "none",
        "thresholds_changed": False,
        "study_spec": "research/dual_revision_sensitivity_stage2_v1/STUDY_SPEC.md",
        "source_schema": src.get("schema"),
        "coverage": src.get("coverage"),
        "center_reproduction": center_reproduction,
        "perturbation_grid_pp": {"net_liq": list(SHIFTS), "reserves": list(SHIFTS)},
        "center": center,
        "cells": cells,
        "aggregate_stability": {name: aggregate_stability(cells, name) for name in ("dual", "early", "full")},
        "decision": {
            "may_change_production": False,
            "may_change_forward_oos": False,
            "may_select_best_grid_cell": False,
        },
        "warnings": [
            "Center DUAL history was rebuilt at runtime with the existing current-history FRED implementation and hard-validated against frozen event identities.",
            "+/-0.50 pp is a fixed synthetic sensitivity envelope, not an estimated FRED revision distribution.",
            "This is not ALFRED vintage reconstruction.",
            "Historical return differences across perturbation cells cannot be used to choose a new threshold.",
        ],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "center_reproduction": center_reproduction,
        "stability": out["aggregate_stability"],
        "cells": [
            {"key": c["key"], "counts": {k: c["events"][k]["count"] for k in ("dual", "early", "full")},
             "retention3": {k: c["vs_center"][k]["center_events_with_variant_within_3_sessions_pct"] for k in ("dual", "early", "full")}}
            for c in cells
        ],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
