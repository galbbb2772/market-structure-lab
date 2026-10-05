#!/usr/bin/env python3
"""Append-only Forward OOS ledgers for four frozen Task 1/4 challengers.

Challengers:
A) Early Sequence
B) RMD2 Price+Score
C) D+1 Entry Timing
D) DUAL Severity Hazard

All definitions were frozen in research/task14_challengers_v1/PREREGISTRATION.md.
No production behavior changes.
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
OUT = ROOT / "docs/data/task14_challenger_forward_oos_v1.json"
FROZEN_THROUGH = "2026-10-02"
FREEZE_COMMIT = "ec476e7af68ddc33ca021acdba8e4b61a02ed8f6"
FULL_FLAG = "D_TO_BOTH_REBOUND_SCORE"
MIN_RET20_HISTORY = 252
DECLUSTER = 5


def num(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def event_onsets_predicate(rows, predicate):
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
        if i - last >= DECLUSTER:
            keep.append(i)
            last = i
    return keep


def ret20_percentiles(rows):
    hist = []
    out = {}
    for i, r in enumerate(rows):
        c = num(r.get("sp500_close"))
        c0 = num(rows[i - 20].get("sp500_close")) if i >= 20 else None
        ret20 = None if c is None or c0 in (None, 0) else (c / c0 - 1.0) * 100.0
        if ret20 is None:
            continue
        hist.append(ret20)
        if len(hist) >= MIN_RET20_HISTORY:
            out[r["date"]] = sum(v <= ret20 for v in hist) / len(hist)
    return out


def outcome_from_index(rows, i):
    c0 = num(rows[i].get("sp500_close"))
    out = {}
    for h in (1, 3, 5, 10, 20):
        mature = c0 is not None and i + h < len(rows) and num(rows[i + h].get("sp500_close")) is not None
        out[f"mature_{h}d"] = bool(mature)
        if mature:
            ch = num(rows[i + h].get("sp500_close"))
            out[f"fwd_{h}d"] = round(100.0 * (ch / c0 - 1.0), 6)
        else:
            out[f"fwd_{h}d"] = None
    for h in (10, 20):
        mature = bool(out[f"mature_{h}d"])
        if not mature:
            out[f"mfe_{h}d"] = None
            out[f"mae_{h}d"] = None
            continue
        vals = [num(rows[j].get("sp500_close")) for j in range(i + 1, i + h + 1)]
        vals = [x for x in vals if x is not None]
        rets = [100.0 * (x / c0 - 1.0) for x in vals]
        out[f"mfe_{h}d"] = round(max(rets), 6)
        out[f"mae_{h}d"] = round(min(rets), 6)
    return out


def hazard_outcomes(rows, i, trough):
    out = {}
    for h in (5, 10, 20):
        mature = i + h < len(rows)
        out[f"mature_{h}d"] = bool(mature)
        if not mature:
            out[f"future_min_{h}d"] = None
            out[f"retest_within_1pct_{h}d"] = None
            out[f"break_prior_trough_{h}d"] = None
            continue
        fut = [num(rows[j].get("sp500_close")) for j in range(i + 1, i + h + 1)]
        fut = [x for x in fut if x is not None]
        mn = min(fut) if fut else None
        out[f"future_min_{h}d"] = None if mn is None else round(mn, 6)
        out[f"retest_within_1pct_{h}d"] = None if mn is None else bool(mn <= trough * 1.01)
        out[f"break_prior_trough_{h}d"] = None if mn is None else bool(mn < trough)
    return out


def rmd2_ps_score(row, price_pct):
    score_pct = num(row.get("market_score_pct"))
    if price_pct is None or score_pct is None:
        raise RuntimeError(
            f"Missing RMD2-PS component on {row.get('date')}: price={price_pct}, score={score_pct}"
        )
    price_residual = 1.0 - clamp(price_pct)
    score_residual = 1.0 - clamp(score_pct / 100.0)
    rmd2 = mean([price_residual, score_residual])
    return {
        "ret20_expanding_percentile": round(price_pct * 100.0, 6),
        "market_score_pct": round(score_pct, 6),
        "price_residual": round(price_residual, 8),
        "score_residual": round(score_residual, 8),
        "rmd2_ps": round(rmd2, 8),
    }


def load_existing():
    if not OUT.exists():
        return None
    d = json.loads(OUT.read_text(encoding="utf-8"))
    if d.get("schema") != "TASK14-CHALLENGER-FORWARD-OOS-V1":
        raise RuntimeError("Existing Task 1/4 challenger ledger schema mismatch")
    if d.get("freeze_reference_commit") != FREEZE_COMMIT:
        raise RuntimeError("Existing Task 1/4 challenger ledger freeze commit mismatch")
    if d.get("frozen_through_market_date") != FROZEN_THROUGH:
        raise RuntimeError("Existing Task 1/4 challenger ledger freeze date mismatch")
    return d


def existing_map(existing, key):
    if not existing:
        return {}
    return {e["event_date"]: e for e in existing.get("challengers", {}).get(key, {}).get("events", [])}


def update_outcomes_only(frozen, current):
    for k, v in current.items():
        if k.startswith("mature_"):
            frozen[k] = bool(v)
        elif frozen.get(k) is None and v is not None:
            frozen[k] = v


def compare_immutable(frozen, current, fields):
    diffs = {}
    for k in fields:
        a, b = frozen.get(k), current.get(k)
        if isinstance(a, (int, float)) or isinstance(b, (int, float)):
            aa, bb = num(a), num(b)
            if aa is None or bb is None:
                if aa != bb:
                    diffs[k] = {"frozen": a, "current_recompute": b}
            elif abs(aa - bb) > 1e-8:
                diffs[k] = {"frozen": a, "current_recompute": b}
        elif a != b:
            diffs[k] = {"frozen": a, "current_recompute": b}
    return diffs


def promotion_gate(events):
    return {
        "minimum_forward_events": 20,
        "minimum_calendar_months": 12,
        "event_count_ready": len(events) >= 20,
        "calendar_gate_ready": False,
        "ready": False,
        "automatic_promotion": False,
        "note": "A separate preregistered review is required after both minimum gates are met.",
    }


def main():
    src = json.loads(STATE.read_text(encoding="utf-8"))
    rows = [dict(r) for r in (src.get("daily") or [])]
    if len(rows) < 2000:
        raise RuntimeError("Market State Box V1 daily history missing/too short")
    rows = seq.add_dual(rows)
    rows, _ = seq.enrich_sequence(rows)
    latest_market_date = rows[-1]["date"]
    price_pct = ret20_percentiles(rows)
    existing = load_existing()
    now = datetime.now(timezone.utc).isoformat()

    # Challenger A: Early Sequence.
    early_pred = lambda r: bool(r.get("D_TO_BREADTH_LOW")) and bool(r.get("box_bottom_since_dual")) and bool(r.get("breadth_rebound_since_dual"))
    early_ix = [i for i in event_onsets_predicate(rows, early_pred) if rows[i]["date"] > FROZEN_THROUGH]
    early_map = existing_map(existing, "early_sequence")
    early_discrepancies = []
    early_immut = (
        "event_date", "breadth_20d_pct", "breadth_trough_since_dual",
        "box_position", "market_score", "market_score_d1", "market_score_d3",
        "score_recovery_confirmed",
    )
    for i in early_ix:
        r = rows[i]; d = r["date"]
        current = {
            "event_date": d,
            "breadth_20d_pct": r.get("breadth_20d_pct"),
            "breadth_trough_since_dual": r.get("breadth_trough_since_dual"),
            "box_position": r.get("box_position"),
            "market_score": r.get("market_score"),
            "market_score_d1": r.get("market_score_d1"),
            "market_score_d3": r.get("market_score_d3"),
            "score_recovery_confirmed": bool(r.get("score_recovery_confirmed")),
        }
        outcomes = outcome_from_index(rows, i)
        if d not in early_map:
            early_map[d] = {
                **current,
                "first_seen_at": now,
                "first_seen_market_date": latest_market_date,
                **outcomes,
            }
        else:
            diffs = compare_immutable(early_map[d], current, early_immut)
            if diffs:
                early_discrepancies.append({"event_date": d, "fields": diffs})
            update_outcomes_only(early_map[d], outcomes)

    # Full Sequence eligible events shared by B/C/D.
    full_onsets = seq.event_onsets(rows, FULL_FLAG)
    full_ix = [r.get("_i") for r in full_onsets if r.get("date") > FROZEN_THROUGH]
    # _i is assigned by enrich_sequence; guard in case a source changes.
    full_ix = [i for i in full_ix if isinstance(i, int)]

    # Challenger B: RMD2 Price+Score.
    rmd_map = existing_map(existing, "rmd2_price_score")
    rmd_discrepancies = []
    rmd_immut = (
        "event_date", "ret20_expanding_percentile", "market_score_pct",
        "price_residual", "score_residual", "rmd2_ps",
    )
    for i in full_ix:
        r = rows[i]; d = r["date"]
        score = rmd2_ps_score(r, price_pct.get(d))
        current = {"event_date": d, **score}
        outcomes = outcome_from_index(rows, i)
        if d not in rmd_map:
            rmd_map[d] = {
                **current,
                "first_seen_at": now,
                "first_seen_market_date": latest_market_date,
                **outcomes,
            }
        else:
            diffs = compare_immutable(rmd_map[d], current, rmd_immut)
            if diffs:
                rmd_discrepancies.append({"event_date": d, "fields": diffs})
            update_outcomes_only(rmd_map[d], outcomes)

    # Challenger C: one-session delayed entry.
    d1_map = existing_map(existing, "dplus1_entry")
    d1_discrepancies = []
    d1_signal_immut = ("event_date", "signal_close")
    for i in full_ix:
        r = rows[i]; d = r["date"]
        signal_close = num(r.get("sp500_close"))
        current = {"event_date": d, "signal_close": None if signal_close is None else round(signal_close, 6)}
        if d not in d1_map:
            d1_map[d] = {
                **current,
                "first_seen_at": now,
                "first_seen_market_date": latest_market_date,
                "target_delay_sessions": 1,
                "entry_date": None,
                "entry_close": None,
                **{f"mature_{h}d": False for h in (1, 3, 5, 10, 20)},
                **{f"fwd_{h}d": None for h in (1, 3, 5, 10, 20)},
                "mfe_10d": None,
                "mae_10d": None,
                "mfe_20d": None,
                "mae_20d": None,
            }
        else:
            diffs = compare_immutable(d1_map[d], current, d1_signal_immut)
            if diffs:
                d1_discrepancies.append({"event_date": d, "fields": diffs})
        frozen = d1_map[d]
        if i + 1 < len(rows):
            entry = rows[i + 1]
            entry_close = num(entry.get("sp500_close"))
            if frozen.get("entry_date") is None:
                frozen["entry_date"] = entry["date"]
                frozen["entry_close"] = None if entry_close is None else round(entry_close, 6)
            else:
                expected = {"entry_date": entry["date"], "entry_close": None if entry_close is None else round(entry_close, 6)}
                diffs = compare_immutable(frozen, expected, ("entry_date", "entry_close"))
                if diffs:
                    d1_discrepancies.append({"event_date": d, "fields": diffs})
            update_outcomes_only(frozen, outcome_from_index(rows, i + 1))

    # Challenger D: DUAL Severity path hazard.
    haz_map = existing_map(existing, "dual_severity_hazard")
    haz_discrepancies = []
    haz_immut = (
        "event_date", "dual_episode_start", "net_liq_4w_pct_at_start",
        "reserves_4w_pct_at_start", "severity_pp", "high_dual_severity",
        "prior_trough_close",
    )
    for i in full_ix:
        r = rows[i]; d = r["date"]
        anchor = r.get("dual_anchor_i")
        if not isinstance(anchor, int) or anchor < 0 or anchor > i:
            raise RuntimeError(f"Missing valid DUAL anchor for full Sequence event {d}: {anchor}")
        start = rows[anchor]
        net = num(start.get("net_liq_4w_pct"))
        res = num(start.get("reserves_4w_pct"))
        if net is None or res is None:
            raise RuntimeError(f"Missing DUAL severity inputs for {d}")
        severity = max(0.0, -2.0 - net) + max(0.0, -2.0 - res)
        past = [num(rows[j].get("sp500_close")) for j in range(anchor, i + 1)]
        past = [x for x in past if x is not None]
        if not past:
            raise RuntimeError(f"Missing trough path for {d}")
        trough = min(past)
        current = {
            "event_date": d,
            "dual_episode_start": start["date"],
            "net_liq_4w_pct_at_start": round(net, 6),
            "reserves_4w_pct_at_start": round(res, 6),
            "severity_pp": round(severity, 6),
            "high_dual_severity": bool(severity > 6.0),
            "prior_trough_close": round(trough, 6),
        }
        outcomes = hazard_outcomes(rows, i, trough)
        if d not in haz_map:
            haz_map[d] = {
                **current,
                "first_seen_at": now,
                "first_seen_market_date": latest_market_date,
                **outcomes,
            }
        else:
            diffs = compare_immutable(haz_map[d], current, haz_immut)
            if diffs:
                haz_discrepancies.append({"event_date": d, "fields": diffs})
            update_outcomes_only(haz_map[d], outcomes)

    early_events = [early_map[d] for d in sorted(early_map)]
    rmd_events = [rmd_map[d] for d in sorted(rmd_map)]
    d1_events = [d1_map[d] for d in sorted(d1_map)]
    haz_events = [haz_map[d] for d in sorted(haz_map)]

    out = {
        "schema": "TASK14-CHALLENGER-FORWARD-OOS-V1",
        "generated_at": now,
        "research_only": True,
        "observation_only": True,
        "production_effect": "none",
        "freeze_reference_commit": FREEZE_COMMIT,
        "preregistration_path": "research/task14_challengers_v1/PREREGISTRATION.md",
        "frozen_through_market_date": FROZEN_THROUGH,
        "latest_market_date": latest_market_date,
        "challengers": {
            "early_sequence": {
                "definition": "D_TO_BREADTH_LOW AND box_bottom_since_dual AND breadth_rebound_since_dual; onset only; 5-session decluster; no score-recovery requirement",
                "forward_event_count": len(early_events),
                "mature_10d_event_count": sum(bool(e.get("mature_10d")) for e in early_events),
                "events": early_events,
                "source_recompute_discrepancies": early_discrepancies,
                "promotion_gate": promotion_gate(early_events),
            },
            "rmd2_price_score": {
                "eligible_event_definition": FULL_FLAG,
                "score_definition": "RMD2_PS = equal-weight mean(price_residual, score_residual)",
                "primary_rank_horizon": "10d",
                "forward_event_count": len(rmd_events),
                "mature_10d_event_count": sum(bool(e.get("mature_10d")) for e in rmd_events),
                "events": rmd_events,
                "source_recompute_discrepancies": rmd_discrepancies,
                "promotion_gate": promotion_gate(rmd_events),
            },
            "dplus1_entry": {
                "eligible_event_definition": FULL_FLAG,
                "entry_definition": "close of next trading session after signal onset",
                "target_delay_sessions": 1,
                "forward_event_count": len(d1_events),
                "entry_available_count": sum(e.get("entry_date") is not None for e in d1_events),
                "mature_10d_event_count": sum(bool(e.get("mature_10d")) for e in d1_events),
                "events": d1_events,
                "source_recompute_discrepancies": d1_discrepancies,
                "promotion_gate": promotion_gate(d1_events),
            },
            "dual_severity_hazard": {
                "eligible_event_definition": FULL_FLAG,
                "severity_definition": "max(0,-2-net_liq_4w_pct_at_episode_start)+max(0,-2-reserves_4w_pct_at_episode_start)",
                "candidate_flag_definition": "HIGH_DUAL_SEVERITY = severity_pp > 6.0",
                "primary_hazard_outcome": "break_prior_trough_10d",
                "forward_event_count": len(haz_events),
                "mature_10d_event_count": sum(bool(e.get("mature_10d")) for e in haz_events),
                "events": haz_events,
                "source_recompute_discrepancies": haz_discrepancies,
                "promotion_gate": promotion_gate(haz_events),
            },
        },
        "warnings": [
            "All four challenger definitions were selected after historical diagnostics and therefore require independent Forward-OOS evidence.",
            "Historical development events through 2026-10-02 are excluded from Forward-OOS counts.",
            "First-seen score/state fields are immutable; later refreshes may only mature outcomes or report upstream discrepancies.",
            "No challenger automatically changes MAIN, production sizing, or existing Task 1/4 Forward-OOS ledgers.",
            "FRED current-history inputs can contain revisions and are not ALFRED vintage data.",
        ],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "latest_market_date": latest_market_date,
        "early_sequence_forward": len(early_events),
        "rmd2_forward": len(rmd_events),
        "dplus1_forward": len(d1_events),
        "severity_forward": len(haz_events),
        "discrepancies": {
            "early": len(early_discrepancies),
            "rmd2": len(rmd_discrepancies),
            "dplus1": len(d1_discrepancies),
            "severity": len(haz_discrepancies),
        },
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
