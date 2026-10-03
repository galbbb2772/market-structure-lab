"""Publish a compact, review-friendly Market State x Box V1 validation summary."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "docs" / "data" / "market_state_box_v1_validation.json"
OUT = ROOT / "docs" / "data" / "market_state_box_v1_validation_summary.json"

KEY_COMBOS = (
    "baseline",
    "box_only",
    "box_sentiment",
    "box_breadth",
    "box_score_recovery",
    "box_sentiment_breadth",
    "box_sentiment_score",
    "box_breadth_score",
    "all_four",
)


def compact_stat(s: dict) -> dict:
    keys = (
        "n",
        "fwd_3d_avg_pct", "fwd_3d_positive_pct", "fwd_3d_mean_bootstrap95",
        "fwd_5d_avg_pct", "fwd_5d_positive_pct", "fwd_5d_positive_wilson95", "fwd_5d_mean_bootstrap95",
        "fwd_10d_avg_pct", "fwd_10d_positive_pct", "fwd_10d_positive_wilson95", "fwd_10d_mean_bootstrap95",
        "mfe_10d_avg_pct", "mae_10d_avg_pct",
    )
    return {k: s.get(k) for k in keys}


def main() -> None:
    d = json.loads(SRC.read_text(encoding="utf-8"))
    split = {}
    for name, block in (d.get("time_split") or {}).items():
        combos = block.get("combos") or {}
        split[name] = {
            "start": block.get("start"),
            "end": block.get("end"),
            "days": block.get("days"),
            "combos": {k: compact_stat(combos.get(k) or {}) for k in KEY_COMBOS},
        }

    payload = {
        "schema": "MARKET-STATE-BOX-V1-VALIDATION-SUMMARY",
        "coverage": d.get("coverage"),
        "thresholds_frozen": d.get("thresholds_frozen"),
        "prevalence": d.get("prevalence"),
        "raw_combo_counts": d.get("raw_combo_counts"),
        "pairwise_overlap": d.get("pairwise_overlap"),
        "annual_counts": d.get("annual_counts"),
        "time_split": split,
        "caveat": d.get("caveat"),
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("validation summary written", OUT)


if __name__ == "__main__":
    main()
