"""Supplemental non-overlap robustness check for Market State Sequence V1.

This does not alter any preregistered threshold or sequence definition. It only
replaces repeated daily observations inside a DUAL phase with the first day that
enters that phase, so long episodes cannot inflate sample counts.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import build_market_state_sequence_v1 as core

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "docs/data/market_state_box_v1.json"
OUT = ROOT / "docs/data/market_state_sequence_phase_onsets_v1.json"

PHASES = (
    "active_d1", "active_d2_3", "active_d4_10", "active_d11plus",
    "post_d1_3", "post_d4_10", "post_d11_20", "no_recent_dual",
)
SEGS = ("full", "pre_2022", "post_2022", "recent_2024")


def phase_onsets(rows, phase):
    cand = []
    for i, r in enumerate(rows):
        if r.get("dual_phase") == phase and (i == 0 or rows[i-1].get("dual_phase") != phase):
            cand.append(i)
    keep = []
    last = -10_000
    for i in cand:
        if i - last >= core.DECLUSTER:
            keep.append(rows[i]); last = i
    return keep


def in_seg(r, name):
    d = r["date"]
    if name == "full": return True
    if name == "pre_2022": return d < "2022-01-01"
    if name == "post_2022": return d >= "2022-01-01"
    if name == "recent_2024": return d >= "2024-01-01"
    raise KeyError(name)


def main():
    src = json.loads(SRC.read_text(encoding="utf-8"))
    rows = [dict(r) for r in (src.get("daily") or [])]
    rows = core.add_dual(rows)
    rows, _ = core.enrich_sequence(rows)
    usable = [r for r in rows if core.num(r.get("fwd_10d")) is not None]

    out_stats = {}
    for seg in SEGS:
        baseline = [r for r in usable if in_seg(r, seg)]
        out_stats[seg] = {}
        for phase in PHASES:
            sample = [r for r in phase_onsets(rows, phase) if in_seg(r, seg) and core.num(r.get("fwd_10d")) is not None]
            out_stats[seg][phase] = core.outcome_stats(sample, baseline)

    out = {
        "schema": "MARKET-STATE-SEQUENCE-PHASE-ONSETS-V1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "method": "first trading day entering each DUAL phase; same 5-session de-cluster guardrail",
        "thresholds_changed": False,
        "phase_onset_stats": out_stats,
        "warning": "Supplemental robustness check only; no production rule or threshold is introduced.",
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Wrote", OUT)
    print(json.dumps(out_stats["full"], ensure_ascii=False))


if __name__ == "__main__":
    main()
