#!/usr/bin/env python3
"""Append-only Forward OOS ledger for frozen RMD3 on Sequence V1 events.

No production behavior changes. New eligible sequence onsets after 2026-10-02
receive an immutable first-seen RMD3 score. Later runs may only mature outcomes.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

import build_market_state_sequence_v1 as seq

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "docs/data/market_state_box_v1.json"
OUT = ROOT / "docs/data/residual_mean_reversion_distance_forward_oos_v1.json"
FLAG = "D_TO_BOTH_REBOUND_SCORE"
FROZEN_THROUGH = "2026-10-02"
FREEZE_COMMIT = "14283ffc5c5f41156a580d4731d4c3b79d800246"
MIN_RET20_HISTORY = 252
IMMUTABLE_FIELDS = (
    "event_date", "first_seen_at", "first_seen_market_date",
    "ret20_expanding_percentile", "breadth_20d_pct", "market_score_pct",
    "price_residual", "breadth_residual", "score_residual", "rmd3",
)


def num(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def ret20_percentiles(daily):
    hist = []
    out = {}
    for i, r in enumerate(daily):
        c = num(r.get("sp500_close"))
        c0 = num(daily[i - 20].get("sp500_close")) if i >= 20 else None
        ret20 = None if c is None or c0 in (None, 0) else (c / c0 - 1.0) * 100.0
        if ret20 is None:
            continue
        hist.append(ret20)
        if len(hist) >= MIN_RET20_HISTORY:
            out[r["date"]] = sum(v <= ret20 for v in hist) / len(hist)
    return out


def compute_score(row, price_pct):
    breadth_pct = num(row.get("breadth_20d_pct"))
    score_pct = num(row.get("market_score_pct"))
    if price_pct is None or breadth_pct is None or score_pct is None:
        raise RuntimeError(
            f"Missing RMD3 component on {row.get('date')}: "
            f"price={price_pct}, breadth={breadth_pct}, score={score_pct}"
        )
    price_residual = 1.0 - clamp(price_pct)
    breadth_residual = 1.0 - clamp(breadth_pct / 100.0)
    score_residual = 1.0 - clamp(score_pct / 100.0)
    rmd3 = mean([price_residual, breadth_residual, score_residual])
    return {
        "ret20_expanding_percentile": round(price_pct * 100.0, 6),
        "breadth_20d_pct": round(breadth_pct, 6),
        "market_score_pct": round(score_pct, 6),
        "price_residual": round(price_residual, 8),
        "breadth_residual": round(breadth_residual, 8),
        "score_residual": round(score_residual, 8),
        "rmd3": round(rmd3, 8),
    }


def outcome_payload(row):
    out = {}
    for h in (1, 3, 5, 10):
        v = num(row.get(f"fwd_{h}d"))
        out[f"fwd_{h}d"] = None if v is None else round(v, 6)
        out[f"mature_{h}d"] = v is not None
    mfe = num(row.get("mfe_10d"))
    mae = num(row.get("mae_10d"))
    out["mfe_10d"] = None if mfe is None else round(mfe, 6)
    out["mae_10d"] = None if mae is None else round(mae, 6)
    return out


def load_existing():
    if not OUT.exists():
        return {}
    d = json.loads(OUT.read_text(encoding="utf-8"))
    if d.get("schema") != "RMD3-SEQUENCE-FORWARD-OOS-V1":
        raise RuntimeError("Existing RMD3 Forward OOS ledger schema mismatch")
    if d.get("freeze_reference_commit") != FREEZE_COMMIT:
        raise RuntimeError("Existing RMD3 Forward OOS ledger freeze commit mismatch")
    return {e["event_date"]: e for e in d.get("events", [])}


def main():
    src = json.loads(STATE.read_text(encoding="utf-8"))
    rows = [dict(r) for r in (src.get("daily") or [])]
    if len(rows) < 2000:
        raise RuntimeError("Market State Box V1 daily history missing/too short")
    rows = seq.add_dual(rows)
    rows, _ = seq.enrich_sequence(rows)
    by_date = {r["date"]: r for r in rows}
    price_pct = ret20_percentiles(rows)
    latest_market_date = rows[-1]["date"]

    onsets = seq.event_onsets(rows, FLAG)
    eligible = [r for r in onsets if r["date"] > FROZEN_THROUGH]

    existing = load_existing()
    now = datetime.now(timezone.utc).isoformat()
    discrepancies = []

    for r in eligible:
        d = r["date"]
        score_now = compute_score(r, price_pct.get(d))
        if d not in existing:
            existing[d] = {
                "event_date": d,
                "first_seen_at": now,
                "first_seen_market_date": latest_market_date,
                **score_now,
                **outcome_payload(r),
            }
        else:
            frozen = existing[d]
            # Keep all event-date score fields immutable; expose any upstream revision.
            diffs = {}
            for k in (
                "ret20_expanding_percentile", "breadth_20d_pct", "market_score_pct",
                "price_residual", "breadth_residual", "score_residual", "rmd3",
            ):
                a = num(frozen.get(k)); b = num(score_now.get(k))
                if a is None or b is None:
                    if a != b:
                        diffs[k] = {"frozen": a, "current_recompute": b}
                elif abs(a - b) > 1e-8:
                    diffs[k] = {"frozen": a, "current_recompute": b}
            if diffs:
                discrepancies.append({"event_date": d, "fields": diffs})
            # Only outcomes can mature/change from null to known values.
            matured = outcome_payload(r)
            for k, v in matured.items():
                if k.startswith("mature_"):
                    frozen[k] = bool(v)
                elif frozen.get(k) is None and v is not None:
                    frozen[k] = v

    events = [existing[d] for d in sorted(existing)]
    first_event_date = events[0]["event_date"] if events else None
    mature10 = sum(bool(e.get("mature_10d")) for e in events)

    out = {
        "schema": "RMD3-SEQUENCE-FORWARD-OOS-V1",
        "generated_at": now,
        "research_only": True,
        "observation_only": True,
        "production_effect": "none",
        "freeze_reference_commit": FREEZE_COMMIT,
        "frozen_through_market_date": FROZEN_THROUGH,
        "event_definition": FLAG,
        "score_definition": "RMD3 = equal-weight mean(price_residual, breadth_residual, score_residual)",
        "append_only_score_fields": list(IMMUTABLE_FIELDS),
        "latest_market_date": latest_market_date,
        "forward_event_count": len(events),
        "mature_10d_event_count": mature10,
        "first_forward_event_date": first_event_date,
        "events": events,
        "source_recompute_discrepancies": discrepancies,
        "promotion_gate": {
            "minimum_forward_events": 20,
            "minimum_calendar_months": 12,
            "event_count_ready": len(events) >= 20,
            "calendar_gate_ready": False,
            "ready": False,
            "note": "Calendar gate is intentionally not inferred here; any promotion requires a separate preregistered review after both gates are met.",
        },
        "warnings": [
            "Historical development events through 2026-10-02 are excluded from Forward OOS counts.",
            "Frozen event-date RMD3 values are never overwritten by later upstream revisions.",
            "FRED current-history inputs can contain revisions and are not ALFRED vintage data.",
            "Market Score history inherits reconstruction caveats from Market State Box V1.",
        ],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "forward_event_count": len(events),
        "mature_10d_event_count": mature10,
        "latest_market_date": latest_market_date,
        "source_recompute_discrepancies": len(discrepancies),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
