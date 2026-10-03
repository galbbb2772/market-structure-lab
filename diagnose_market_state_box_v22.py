"""V2.2 diagnostic: market-state environment maps around box-bottom mean reversion events.

This does NOT optimize an entry rule. It asks a narrower question than V2/V2.1:
conditional on a point-in-time box-bottom event already existing, do sentiment,
breadth, and Market Score states change the forward outcome distribution enough to
be useful as environment filters?

All buckets use past-only percentile features already present in V1, or a past-only
rank computed here. Results are descriptive/diagnostic after prior V2 inspection;
any apparent good cell requires fresh OOS confirmation before strategy use.
"""
from __future__ import annotations

import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

import build_market_state_box_v2 as v2

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "docs/data/market_state_box_v1.json"
OUT = ROOT / "docs/data/market_state_box_v22_environment.json"
H = (3, 5, 10)
MIN_CELL_N = 5


def num(x):
    try:
        z = float(x)
        return z if math.isfinite(z) else None
    except (TypeError, ValueError):
        return None


def quintile(v):
    x = num(v)
    if x is None:
        return None
    return min(4, max(0, int(min(99.999, max(0.0, x)) // 20)))


def decluster(rows, gap=5):
    out, last = [], -10**9
    for r in sorted(rows, key=lambda x: int(x["_i"])):
        i = int(r["_i"])
        if i - last >= gap:
            out.append(r)
            last = i
    return out


def bootstrap95(vals, seed=7, rounds=1200):
    vals = [float(x) for x in vals if num(x) is not None]
    if len(vals) < 5:
        return None
    rng = random.Random(seed + len(vals))
    n = len(vals)
    sims = []
    for _ in range(rounds):
        sims.append(mean(vals[rng.randrange(n)] for _ in range(n)))
    sims.sort()
    return [round(sims[int(.025 * (rounds - 1))], 3), round(sims[int(.975 * (rounds - 1))], 3)]


def summarize(rows):
    rows = decluster(rows)
    out = {"n": len(rows)}
    for h in H:
        vals = [num(r.get(f"fwd_{h}d")) for r in rows]
        vals = [x for x in vals if x is not None]
        out[f"fwd_{h}d_mean"] = round(mean(vals), 3) if vals else None
        out[f"fwd_{h}d_median"] = round(median(vals), 3) if vals else None
        out[f"fwd_{h}d_positive_pct"] = round(100 * sum(x > 0 for x in vals) / len(vals), 1) if vals else None
        out[f"fwd_{h}d_mean_bootstrap95"] = bootstrap95(vals) if vals else None
    mfe = [num(r.get("mfe_10d")) for r in rows]
    mae = [num(r.get("mae_10d")) for r in rows]
    mfe = [x for x in mfe if x is not None]
    mae = [x for x in mae if x is not None]
    out["mfe_10d_mean"] = round(mean(mfe), 3) if mfe else None
    out["mae_10d_mean"] = round(mean(mae), 3) if mae else None
    return out


def enrich(rows):
    score_d3_rank = v2.pct_hist([r.get("market_score_d3") for r in rows])
    out = []
    for i, src in enumerate(rows):
        r = dict(src)
        r["_i"] = i
        r["score_d3_pct"] = score_d3_rank[i]
        r["sentiment_q"] = quintile(r.get("sentiment_stress_pct"))
        r["breadth_q"] = quintile(r.get("breadth_20d_pct"))
        r["score_level_q"] = quintile(r.get("market_score_pct"))
        r["score_d3_q"] = quintile(r.get("score_d3_pct"))
        out.append(r)
    return out


def period_rows(events, start=None, end=None):
    return [r for r in events if (start is None or r["date"] >= start) and (end is None or r["date"] <= end)]


def single_map(events, field):
    cells = []
    base = summarize(events)
    base5 = base.get("fwd_5d_mean")
    base10 = base.get("fwd_10d_mean")
    for q in range(5):
        rs = [r for r in events if r.get(field) == q]
        s = summarize(rs)
        s.update({
            "q": q,
            "range": [q * 20, (q + 1) * 20],
            "fwd_5d_mean_delta_vs_box": round(s["fwd_5d_mean"] - base5, 3) if s.get("fwd_5d_mean") is not None and base5 is not None else None,
            "fwd_10d_mean_delta_vs_box": round(s["fwd_10d_mean"] - base10, 3) if s.get("fwd_10d_mean") is not None and base10 is not None else None,
            "sample_ok": s["n"] >= MIN_CELL_N,
        })
        cells.append(s)
    return {"baseline_box_events": base, "cells": cells}


def pair_map(events, a, b):
    base = summarize(events)
    base5 = base.get("fwd_5d_mean")
    cells = []
    for qa in range(5):
        for qb in range(5):
            rs = [r for r in events if r.get(a) == qa and r.get(b) == qb]
            s = summarize(rs)
            s.update({
                "a_q": qa,
                "b_q": qb,
                "a_range": [qa * 20, (qa + 1) * 20],
                "b_range": [qb * 20, (qb + 1) * 20],
                "fwd_5d_mean_delta_vs_box": round(s["fwd_5d_mean"] - base5, 3) if s.get("fwd_5d_mean") is not None and base5 is not None else None,
                "sample_ok": s["n"] >= MIN_CELL_N,
            })
            cells.append(s)
    return {"baseline_box_events": base, "cells": cells}


def build_period(events):
    singles = {
        "sentiment": single_map(events, "sentiment_q"),
        "breadth": single_map(events, "breadth_q"),
        "score_level": single_map(events, "score_level_q"),
        "score_d3": single_map(events, "score_d3_q"),
    }
    pairs = {
        "breadth__score_d3": pair_map(events, "breadth_q", "score_d3_q"),
        "sentiment__breadth": pair_map(events, "sentiment_q", "breadth_q"),
        "breadth__score_level": pair_map(events, "breadth_q", "score_level_q"),
    }
    return {"raw_event_days": len(events), "declustered_box_baseline": summarize(events), "single_feature_maps": singles, "pair_maps": pairs}


def main():
    src = json.loads(SRC.read_text(encoding="utf-8"))
    rows = enrich(src.get("daily") or [])
    events = [r for r in rows if r.get("box_bottom") and r.get("fwd_10d") is not None]

    periods = {
        "full": period_rows(events),
        "pre_2022": period_rows(events, end="2021-12-31"),
        "post_2022": period_rows(events, start="2022-01-03"),
        "recent_2024_plus": period_rows(events, start="2024-01-02"),
    }
    output = {
        "schema": "MARKET-STATE-BOX-V2.2-ENVIRONMENT",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "purpose": "Estimate whether market-state variables are useful as environment filters conditional on an existing box-bottom event; not a direct return predictor and not a promoted strategy rule.",
        "selection_warning": "V2.2 follows V1/V2/V2.1 inspection. No favorable cell should be treated as fresh OOS discovery without later confirmation.",
        "event_definition": "V1 point-in-time box_bottom (eligible detected box, position <= 25%); events declustered by 5 sessions for summaries.",
        "state_bins": "Past-only percentile quintiles: 0-20,20-40,40-60,60-80,80-100. Score D3 rank is computed expanding/past-only.",
        "minimum_cell_n_for_sample_ok": MIN_CELL_N,
        "periods": {name: build_period(rs) for name, rs in periods.items()},
    }
    OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v["declustered_box_baseline"] for k, v in output["periods"].items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
