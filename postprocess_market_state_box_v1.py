"""Normalize Market State x Box V1 output and publish a compact audit summary."""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "docs" / "data" / "market_state_box_v1.json"
SUMMARY_PATH = ROOT / "docs" / "data" / "market_state_box_v1_summary.json"

FEATURES = (
    "box_position",
    "sentiment_stress_pct",
    "breadth_20d_pct",
    "market_score_pct",
    "market_score_d3",
)


def distance(a: dict, b: dict):
    diffs, used = [], []
    for f in FEATURES:
        x, y = a.get(f), b.get(f)
        if x is None or y is None:
            continue
        scale = 20.0 if f == "market_score_d3" else 100.0
        try:
            z = ((float(x) - float(y)) / scale) ** 2
        except (TypeError, ValueError):
            continue
        if not math.isfinite(z):
            continue
        diffs.append(z)
        used.append(f)
    if len(diffs) < 4:
        return None, used
    return math.sqrt(sum(diffs) / len(diffs)), used


def rebuild_analogs(rows: list[dict], latest: dict, limit: int = 20) -> list[dict]:
    latest_i = len(rows) - 1
    scored = []
    for i, row in enumerate(rows):
        if i >= latest_i - 10:
            continue
        dist, used = distance(row, latest)
        if dist is not None:
            scored.append((dist, i, row, used))
    scored.sort(key=lambda x: x[0])
    picked, picked_i = [], []
    for dist, i, row, used in scored:
        if any(abs(i - j) < 10 for j in picked_i):
            continue
        picked_i.append(i)
        picked.append({
            "date": row.get("date"),
            "distance": round(dist, 4),
            "features_used": used,
            "box_position": row.get("box_position"),
            "sentiment_stress_pct": row.get("sentiment_stress_pct"),
            "breadth_20d_pct": row.get("breadth_20d_pct"),
            "market_score": row.get("market_score"),
            "market_regime": row.get("market_regime"),
            "fwd_1d": row.get("fwd_1d"),
            "fwd_3d": row.get("fwd_3d"),
            "fwd_5d": row.get("fwd_5d"),
            "fwd_10d": row.get("fwd_10d"),
            "mfe_10d": row.get("mfe_10d"),
            "mae_10d": row.get("mae_10d"),
        })
        if len(picked) >= limit:
            break
    return picked


def main() -> None:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    rows = data.get("daily") or []
    if not rows:
        raise RuntimeError("market_state_box_v1.json has no daily rows")

    # Current state must always be the latest overlapping trading day, even when
    # no active 20D/60D box exists on that day. In that case box_bottom=False.
    latest = dict(rows[-1])
    data["latest"] = latest
    data["similar_days"] = rebuild_analogs(rows, latest)
    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    summary = {
        "schema": data.get("schema"),
        "generated_at": data.get("generated_at"),
        "coverage": data.get("coverage"),
        "latest": data.get("latest"),
        "ablation": data.get("ablation"),
        "similar_days": data.get("similar_days"),
        "definitions": data.get("definitions"),
        "warnings": data.get("warnings"),
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("normalized latest", latest.get("date"), "analogs", len(data["similar_days"]))


if __name__ == "__main__":
    main()
