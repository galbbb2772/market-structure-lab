#!/usr/bin/env python3
"""Event-by-event audit for Market State Sequence V1.

Audits only the preregistered D_TO_BOTH_REBOUND_SCORE onset. No thresholds are
optimized here. If historical promotion criteria fail, only an observation-only
Forward OOS shadow is emitted.
"""
from __future__ import annotations

import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

import build_market_state_sequence_v1 as seq

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "docs/data/market_state_box_v1.json"
OUT = ROOT / "docs/data/market_state_sequence_event_audit_v1.json"
SHADOW = ROOT / "docs/data/market_state_sequence_forward_oos_v1.json"
FLAG = "D_TO_BOTH_REBOUND_SCORE"
FROZEN_THROUGH = "2026-10-02"
PREREG_COMMIT = "0ab2f08dffe2dcd6d8c43afe721cd4d59824ba63"


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def rmean(vals):
    a = [num(x) for x in vals]
    a = [x for x in a if x is not None]
    return None if not a else round(mean(a), 4)


def rmedian(vals):
    a = [num(x) for x in vals]
    a = [x for x in a if x is not None]
    return None if not a else round(median(a), 4)


def pct_pos(vals):
    a = [num(x) for x in vals]
    a = [x for x in a if x is not None]
    return None if not a else round(100.0 * sum(x > 0 for x in a) / len(a), 2)


def trailing_return(rows, i, n):
    if i < n:
        return None
    a = num(rows[i-n].get("sp500_close")); b = num(rows[i].get("sp500_close"))
    if a is None or b is None or a == 0:
        return None
    return round((b / a - 1.0) * 100.0, 4)


def drawdown_60(rows, i):
    lo = max(0, i - 59)
    closes = [num(rows[j].get("sp500_close")) for j in range(lo, i + 1)]
    closes = [x for x in closes if x is not None]
    cur = num(rows[i].get("sp500_close"))
    if cur is None or not closes:
        return None
    hi = max(closes)
    return round((cur / hi - 1.0) * 100.0, 4)


def ma200_phase(rows, i):
    if i < 219:
        return None
    closes = [num(rows[j].get("sp500_close")) for j in range(i-219, i+1)]
    if any(x is None for x in closes):
        return None
    ma_now = mean(closes[-200:])
    ma_20ago = mean(closes[-220:-20])
    close = closes[-1]
    above = close >= ma_now
    rising = ma_now >= ma_20ago
    if above and rising: return "bull_rising"
    if above and not rising: return "bull_weakening"
    if not above and not rising: return "bear_falling"
    return "bear_recovery"


def episode_end(rows, anchor):
    j = anchor
    while j + 1 < len(rows) and bool(rows[j + 1].get("dual_drain")):
        j += 1
    return j


def summarize(sample, baseline):
    out = {"n": len(sample)}
    for h in (1,3,5,10):
        vals = [r.get(f"fwd_{h}d") for r in sample]
        base = [r.get(f"fwd_{h}d") for r in baseline]
        m = rmean(vals); bm = rmean(base)
        out[f"{h}d"] = {
            "mean_pct": m,
            "median_pct": rmedian(vals),
            "positive_pct": pct_pos(vals),
            "baseline_mean_pct": bm,
            "mean_lift_vs_baseline_pp": None if m is None or bm is None else round(m - bm, 4),
        }
    return out


def loo_range(events, h):
    if len(events) < 3:
        return None
    means = []
    for k in range(len(events)):
        vals = [num(e.get(f"fwd_{h}d")) for i,e in enumerate(events) if i != k]
        vals = [x for x in vals if x is not None]
        if vals: means.append(mean(vals))
    return None if not means else [round(min(means),4), round(max(means),4)]


def group_stats(events, baseline, key):
    out = {}
    for value in sorted({e.get(key) for e in events}, key=lambda x: str(x)):
        s = [e for e in events if e.get(key) == value]
        out[str(value)] = summarize(s, baseline)
    return out


def main():
    src = json.loads(SRC.read_text(encoding="utf-8"))
    rows = [dict(r) for r in (src.get("daily") or [])]
    if len(rows) < 2000:
        raise RuntimeError("Market State Box V1 daily table missing")
    rows = seq.add_dual(rows)
    rows, episodes = seq.enrich_sequence(rows)
    idx_by_date = {r["date"]: i for i,r in enumerate(rows)}
    usable = [r for r in rows if num(r.get("fwd_10d")) is not None]
    onsets = [r for r in seq.event_onsets(rows, FLAG) if num(r.get("fwd_10d")) is not None]

    events = []
    for r in onsets:
        i = idx_by_date[r["date"]]
        anchor = r.get("dual_anchor_i")
        if anchor is None:
            raise RuntimeError(f"onset without DUAL anchor: {r['date']}")
        anchor = int(anchor)
        end_i = episode_end(rows, anchor)
        path = rows[anchor:i+1]
        br = [num(x.get("breadth_20d_pct")) for x in path]; br = [x for x in br if x is not None]
        bx = [num(x.get("box_position")) for x in path]; bx = [x for x in bx if x is not None]
        event = {
            "date": r["date"],
            "year": int(r["date"][:4]),
            "period": "pre_2022" if r["date"] < "2022-01-01" else "post_2022",
            "recent_2024": r["date"] >= "2024-01-01",
            "ma200_phase": ma200_phase(rows, i),
            "dual_episode_start": rows[anchor]["date"],
            "dual_episode_end": rows[end_i]["date"],
            "confirmation_lag_sessions": i - anchor,
            "sp500_close": r.get("sp500_close"),
            "ret_5d_pct": trailing_return(rows, i, 5),
            "ret_20d_pct": trailing_return(rows, i, 20),
            "ret_60d_pct": trailing_return(rows, i, 60),
            "drawdown_from_60d_high_pct": drawdown_60(rows, i),
            "box_position": r.get("box_position"),
            "min_box_position_since_dual": None if not bx else round(min(bx), 4),
            "breadth_20d_pct": r.get("breadth_20d_pct"),
            "min_breadth_pct_since_dual": None if not br else round(min(br), 3),
            "market_score": r.get("market_score"),
            "market_score_d1": r.get("market_score_d1"),
            "market_score_d3": r.get("market_score_d3"),
            "fwd_1d": r.get("fwd_1d"),
            "fwd_3d": r.get("fwd_3d"),
            "fwd_5d": r.get("fwd_5d"),
            "fwd_10d": r.get("fwd_10d"),
            "mfe_10d": r.get("mfe_10d"),
            "mae_10d": r.get("mae_10d"),
        }
        events.append(event)

    if len(events) != 12:
        raise RuntimeError(f"expected frozen 12 complete sequence onsets, got {len(events)}")

    full = summarize(events, usable)
    pre = [e for e in events if e["period"] == "pre_2022"]
    post = [e for e in events if e["period"] == "post_2022"]
    recent = [e for e in events if e["recent_2024"]]
    pre_base = [r for r in usable if r["date"] < "2022-01-01"]
    post_base = [r for r in usable if r["date"] >= "2022-01-01"]
    recent_base = [r for r in usable if r["date"] >= "2024-01-01"]

    best = max(events, key=lambda e: num(e.get("fwd_10d")) if num(e.get("fwd_10d")) is not None else -1e99)
    worst = min(events, key=lambda e: num(e.get("fwd_10d")) if num(e.get("fwd_10d")) is not None else 1e99)
    no_best = [e for e in events if e is not best]
    no_worst = [e for e in events if e is not worst]

    baseline5 = full["5d"]["baseline_mean_pct"]
    baseline10 = full["10d"]["baseline_mean_pct"]
    post_stats = summarize(post, post_base)
    criteria = {
        "n_total_gte_20": len(events) >= 20,
        "n_pre2022_gte_5": len(pre) >= 5,
        "n_post2022_gte_5": len(post) >= 5,
        "n_2024plus_gte_3": len(recent) >= 3,
        "full_5d_above_baseline": full["5d"]["mean_pct"] is not None and full["5d"]["mean_pct"] > baseline5,
        "full_10d_above_baseline": full["10d"]["mean_pct"] is not None and full["10d"]["mean_pct"] > baseline10,
        "post_5d_above_baseline": post_stats["5d"]["mean_lift_vs_baseline_pp"] is not None and post_stats["5d"]["mean_lift_vs_baseline_pp"] > 0,
        "post_10d_above_baseline": post_stats["10d"]["mean_lift_vs_baseline_pp"] is not None and post_stats["10d"]["mean_lift_vs_baseline_pp"] > 0,
        "no_recent_sign_reversal": len(recent) >= 3 and summarize(recent, recent_base)["5d"]["mean_lift_vs_baseline_pp"] >= 0 and summarize(recent, recent_base)["10d"]["mean_lift_vs_baseline_pp"] >= 0,
    }
    promotion_evidence_sufficient = all(criteria.values())

    out = {
        "schema": "MARKET-STATE-SEQUENCE-EVENT-AUDIT-V1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "preregistration_commit": PREREG_COMMIT,
        "thresholds_changed": False,
        "event_definition": FLAG,
        "event_count": len(events),
        "events": events,
        "summary": {
            "full": full,
            "pre_2022": summarize(pre, pre_base),
            "post_2022": post_stats,
            "recent_2024": summarize(recent, recent_base),
        },
        "concentration": {
            "by_year_count": dict(sorted(Counter(str(e["year"]) for e in events).items())),
            "by_phase_count": dict(sorted(Counter(str(e["ma200_phase"]) for e in events).items())),
            "by_year_stats": group_stats(events, usable, "year"),
            "by_phase_stats": group_stats(events, usable, "ma200_phase"),
        },
        "robustness": {
            "leave_one_out_5d_mean_range_pct": loo_range(events, 5),
            "leave_one_out_10d_mean_range_pct": loo_range(events, 10),
            "best_10d_event": {"date": best["date"], "fwd_10d": best["fwd_10d"]},
            "worst_10d_event": {"date": worst["date"], "fwd_10d": worst["fwd_10d"]},
            "remove_best_10d": summarize(no_best, usable),
            "remove_worst_10d": summarize(no_worst, usable),
        },
        "shadow_decision": {
            "historical_promotion_evidence_sufficient": promotion_evidence_sufficient,
            "criteria": criteria,
            "decision": "observation_only_forward_oos_shadow" if not promotion_evidence_sufficient else "eligible_for_separate_promotion_research_only",
            "production_change": False,
        },
        "warnings": [
            "This is an audit of a previously defined sequence; no new feature threshold is selected.",
            "FRED current-history retrieval can contain revisions and is not ALFRED vintage data.",
            "Market Score history inherits reconstruction caveats from Market State Box V1.",
        ],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    future = [e for e in events if e["date"] > FROZEN_THROUGH]
    shadow = {
        "schema": "MARKET-STATE-SEQUENCE-FORWARD-OOS-V1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "observation_only": True,
        "production_effect": "none",
        "frozen_through_market_date": FROZEN_THROUGH,
        "freeze_reference_commit": PREREG_COMMIT,
        "event_definition": FLAG,
        "future_event_count": len(future),
        "future_events": future,
        "promotion_gate": {
            "minimum_forward_events": 20,
            "minimum_calendar_months": 12,
            "note": "Any future promotion requires a separate preregistered review. Historical V1 audit does not promote the signal.",
        },
    }
    SHADOW.write_text(json.dumps(shadow, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"events": len(events), "shadow_decision": out["shadow_decision"], "future_events": len(future)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
