"""Bootstrap directional transition diagnostics for the Task 1/4 mechanism graph.

Historical / post-discovery only. No production or Forward-OOS changes.
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

import research_modules_stage2_v1 as mod
import research_cross_family_transition_stage2_v1 as tr

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "docs/data/cross_family_transition_stage2_v1.json"
OUT = ROOT / "docs/data/mechanism_graph_stage2_v1.json"
SEED = 202610051
ROUNDS = 20000
HORIZONS = (5, 10, 20, 40)

FORWARD_LINKS = [
    ("dual_onset", "breadth_low"),
    ("breadth_low", "box_bottom"),
    ("box_bottom", "breadth_rebound10"),
    ("breadth_rebound10", "score_recovery"),
    ("breadth_rebound10", "early_sequence"),
    ("score_recovery", "full_sequence"),
    ("dual_onset", "early_sequence"),
    ("dual_onset", "full_sequence"),
]


def num(x):
    return mod.num(x)


def qtile(xs, p):
    return mod.qtile(xs, p)


def source_event_contributions(source_events, dest_events, controls, h, same_family=False):
    dest_idx = sorted(int(r["_i"]) for r in dest_events)
    contrib = []
    hit_lags = []
    records = []
    for e in source_events:
        ei = int(e["_i"])
        lag = tr.first_lag(ei, dest_idx, same_family)
        treatment = 1.0 if lag is not None and lag <= h else 0.0
        if treatment and lag is not None:
            hit_lags.append(lag)
        cs = controls.get(ei, [])
        ctrl_hits = []
        for c in cs:
            clag = tr.first_lag(int(c["_i"]), dest_idx, False)
            ctrl_hits.append(1.0 if clag is not None and clag <= h else 0.0)
        if not ctrl_hits:
            continue
        cp = mean(ctrl_hits)
        contrib.append(treatment - cp)
        records.append({
            "source_date": e["date"],
            "treatment_hit": int(treatment),
            "first_hit_lag_sessions": lag,
            "matched_control_probability": round(cp, 4),
            "source_minus_control": round(treatment - cp, 4),
            "control_n": len(ctrl_hits),
        })
    return contrib, hit_lags, records


def bootstrap_link(source_events, dest_events, controls, h, seed_offset):
    contrib, hit_lags, records = source_event_contributions(source_events, dest_events, controls, h)
    n = len(contrib)
    if not n:
        return {"n": 0, "bootstrap_rounds": ROUNDS}
    treatment_rate = 100.0 * mean(r["treatment_hit"] for r in records)
    control_rate = 100.0 * mean(r["matched_control_probability"] for r in records)
    excess = 100.0 * mean(contrib)
    rng = random.Random(SEED + seed_offset)
    sims = []
    for _ in range(ROUNDS):
        sample = [contrib[rng.randrange(n)] for _ in range(n)]
        sims.append(100.0 * mean(sample))
    le0 = sum(x <= 0 for x in sims)
    return {
        "n": n,
        "bootstrap_rounds": ROUNDS,
        "treatment_hit_rate_pct": round(treatment_rate, 2),
        "matched_control_hit_rate_pct": round(control_rate, 2),
        "excess_hit_rate_pp": round(excess, 2),
        "bootstrap_ci95_excess_pp": [round(qtile(sims, 0.025), 2), round(qtile(sims, 0.975), 2)],
        "bootstrap_one_sided_prob_excess_le0": round((le0 + 1) / (ROUNDS + 1), 5),
        "hit_n": sum(r["treatment_hit"] for r in records),
        "median_first_hit_lag_sessions": None if not hit_lags else round(median(hit_lags), 2),
        "p25_first_hit_lag_sessions": None if not hit_lags else round(qtile(hit_lags, 0.25), 2),
        "p75_first_hit_lag_sessions": None if not hit_lags else round(qtile(hit_lags, 0.75), 2),
        "records": records,
    }


def main():
    frozen = json.loads(SRC.read_text(encoding="utf-8"))
    rows = tr.build_rows()
    by_date = {r["date"]: r for r in rows}
    frozen_dates = frozen["transition_study"]["event_dates"]
    sets = {
        name: [by_date[d] for d in dates if d in by_date]
        for name, dates in frozen_dates.items()
    }
    frozen_counts = frozen["transition_study"]["event_counts"]
    for name, events in sets.items():
        if len(events) != int(frozen_counts[name]):
            raise RuntimeError(f"Frozen event mismatch for {name}: {len(events)} != {frozen_counts[name]}")

    controls = {name: tr.control_map(rows, events) for name, events in sets.items()}
    directed = {}
    pair_results = []
    seen_directed = []
    for pair_i, (a, b) in enumerate(FORWARD_LINKS):
        fkey = f"{a}->{b}"
        rkey = f"{b}->{a}"
        if fkey not in directed:
            directed[fkey] = {f"{h}d": bootstrap_link(sets[a], sets[b], controls[a], h, pair_i * 100 + h) for h in HORIZONS}
            seen_directed.append(fkey)
        if rkey not in directed:
            directed[rkey] = {f"{h}d": bootstrap_link(sets[b], sets[a], controls[b], h, 10000 + pair_i * 100 + h) for h in HORIZONS}
            seen_directed.append(rkey)
        f20 = directed[fkey]["20d"].get("excess_hit_rate_pp")
        r20 = directed[rkey]["20d"].get("excess_hit_rate_pp")
        pair_results.append({
            "hypothesized_forward": fkey,
            "reverse": rkey,
            "forward_20d": {k: v for k, v in directed[fkey]["20d"].items() if k != "records"},
            "reverse_20d": {k: v for k, v in directed[rkey]["20d"].items() if k != "records"},
            "forward_minus_reverse_excess_20d_pp": None if f20 is None or r20 is None else round(f20 - r20, 2),
            "directional_sign_consistent": None if f20 is None or r20 is None else bool(f20 > r20),
        })

    out = {
        "schema": "MECHANISM-GRAPH-STAGE2-V1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "diagnostic_only": True,
        "production_effect": "none",
        "thresholds_changed": False,
        "study_spec": "research/mechanism_graph_stage2_v1/STUDY_SPEC.md",
        "source_schema": frozen.get("schema"),
        "coverage": frozen.get("coverage"),
        "event_counts": {k: len(v) for k, v in sets.items()},
        "directed_links": directed,
        "forward_reverse_pairs": pair_results,
        "summary": {
            "primary_pairs": len(FORWARD_LINKS),
            "directionally_consistent_pairs_20d": sum(x["directional_sign_consistent"] is True for x in pair_results),
            "forward_links_positive_excess_20d": sum((directed[f"{a}->{b}"]["20d"].get("excess_hit_rate_pp") or 0) > 0 for a, b in FORWARD_LINKS),
            "forward_links_ci_excludes_zero_20d": sum(
                (directed[f"{a}->{b}"]["20d"].get("bootstrap_ci95_excess_pp") or [0, 0])[0] > 0
                for a, b in FORWARD_LINKS
            ),
        },
        "decision": {
            "may_change_production": False,
            "may_change_forward_oos": False,
            "causal_claim_allowed": False,
        },
        "warnings": [
            "Historical/post-discovery diagnostic only; event-level bootstrap does not remove event dependence.",
            "Directional transition evidence is not causal proof.",
            "Small source event sets can produce wide confidence intervals.",
        ],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "summary": out["summary"],
        "pairs": [
            {
                "forward": x["hypothesized_forward"],
                "forward_excess20": x["forward_20d"].get("excess_hit_rate_pp"),
                "forward_ci20": x["forward_20d"].get("bootstrap_ci95_excess_pp"),
                "p_le0": x["forward_20d"].get("bootstrap_one_sided_prob_excess_le0"),
                "reverse_excess20": x["reverse_20d"].get("excess_hit_rate_pp"),
                "asymmetry": x["forward_minus_reverse_excess_20d_pp"],
            } for x in pair_results
        ],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
