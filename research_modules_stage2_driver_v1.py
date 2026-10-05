"""Driver for cross-module Stage-2 V1 using the vectorized concentration audit."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import research_modules_stage2_v1 as base


def main():
    src = json.loads(base.STATE.read_text(encoding="utf-8"))
    rows = base.enrich(src.get("daily") or [])
    if not rows:
        raise RuntimeError("market_state_box_v1 daily history missing")
    cpath = base.ROOT / "docs/data/concentration_stage2_walkforward_v1.json"
    if not cpath.exists():
        raise RuntimeError("vectorized concentration Stage-2 output missing")
    c = json.loads(cpath.read_text(encoding="utf-8"))
    out = {
        "schema": "CROSS-MODULE-STAGE2-V1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "diagnostic_only": True,
        "production_effect": "none",
        "thresholds_changed": False,
        "study_spec": "research/modules_stage2_v1/STUDY_SPEC.md",
        "coverage": {"start": rows[0]["date"], "end": rows[-1]["date"], "observations": len(rows)},
        "box": base.box_module(rows),
        "sentiment": base.sentiment_module(rows),
        "breadth": base.breadth_module(rows),
        "score": base.score_module(rows),
        "concentration": {
            "method": c.get("definition"),
            "engine": "vectorized equivalent of Concentration V1 distance/settings",
            "results": c.get("results") or [],
        },
        "decision": {
            "may_change_production": False,
            "may_change_existing_forward_oos": False,
            "may_select_best_threshold_from_grid": False,
        },
        "warnings": [
            "Sentiment and composite score histories are reconstructed, not fully publication-time archives.",
            "Box coverage is intermittent because only point-in-time eligible boxes are used.",
            "Common event studies are historical diagnostics; they are not prospective confirmation.",
            "Concentration walk-forward is stricter than the current-date analog view but still uses a feature set designed on historical data.",
        ],
    }
    base.OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    brief = {
        "box_10d": out["box"]["center"].get("10d"),
        "sentiment_10d": out["sentiment"]["center"].get("10d"),
        "breadth_10d": out["breadth"]["center"].get("10d"),
        "score_recovery_10d": out["score"]["center"].get("10d"),
        "score_ic10": out["score"]["rank_ic"].get("10d"),
        "concentration": {r["symbol"]: r["10d"] for r in out["concentration"]["results"]},
    }
    print(json.dumps(brief, ensure_ascii=False))


if __name__ == "__main__":
    main()
