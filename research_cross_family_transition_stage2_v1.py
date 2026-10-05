"""Cross-family ordered-transition diagnostics and sparse factor follow-up.

Historical / post-discovery only. No production or Forward-OOS changes.
Definitions are frozen in research/cross_family_transition_stage2_v1/STUDY_SPEC.md.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

import build_market_state_sequence_v1 as seq
import research_modules_stage2_v1 as mod
import research_factor_map_stage2_v1 as fm

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "docs/data/market_state_box_v1.json"
FACTOR = ROOT / "docs/data/factor_map_stage2_v1.json"
OUT = ROOT / "docs/data/cross_family_transition_stage2_v1.json"
HORIZONS = (5, 10, 20, 40)
RET_H = (5, 10, 20)


def num(x):
    return mod.num(x)


def qtile(xs, p):
    return mod.qtile(xs, p)


def onset(rows, pred, gap=5):
    return mod.event_onsets(rows, pred, gap=gap)


def build_rows():
    state = json.loads(STATE.read_text(encoding="utf-8"))
    rows = mod.enrich(state.get("daily") or [])
    rows = seq.add_dual(rows)
    rows, _ = seq.enrich_sequence(rows)
    rows = fm.add_local_fields(rows)
    return rows


def event_sets(rows):
    full, early = fm.sequence_events(rows)
    sets = {
        "sentiment_extreme": onset(rows, lambda r: num(r.get("sentiment_stress_pct")) is not None and num(r.get("sentiment_stress_pct")) >= 80.0),
        "dual_onset": onset(rows, lambda r: bool(r.get("dual_drain"))),
        "box_bottom": onset(rows, lambda r: num(r.get("box_position")) is not None and num(r.get("box_position")) <= 0.25),
        "breadth_low": onset(rows, mod.breadth_pred(20)),
        "breadth_rebound10": onset(rows, lambda r: bool(r.get("fm_breadth_rebound10"))),
        "score_recovery": onset(rows, lambda r: num(r.get("s2_score_min10_pct")) is not None and num(r.get("s2_score_min10_pct")) <= 20.0 and num(r.get("market_score_d1")) is not None and num(r.get("market_score_d3")) is not None and num(r.get("market_score_d1")) > 0 and num(r.get("market_score_d3")) > 0),
        "early_sequence": early,
        "full_sequence": full,
    }
    return sets


def first_lag(source_i, dest_idx, same_family=False):
    for j in dest_idx:
        if j > source_i or (not same_family and j == source_i):
            return j - source_i
    return None


def lag_summary(lags):
    vals = [x for x in lags if x is not None]
    if not vals:
        return {"n": 0, "median_sessions": None, "p25_sessions": None, "p75_sessions": None}
    return {
        "n": len(vals),
        "median_sessions": round(median(vals), 2),
        "p25_sessions": round(qtile(vals, 0.25), 2),
        "p75_sessions": round(qtile(vals, 0.75), 2),
    }


def scale_iqr(rows, field):
    vals = [num(r.get(field)) for r in rows]
    vals = [x for x in vals if x is not None]
    if not vals:
        return 1.0
    a, b = qtile(vals, 0.25), qtile(vals, 0.75)
    d = (b - a) if a is not None and b is not None else 0.0
    return d if d > 1e-9 else max(1.0, abs(mean(vals)))


def control_map(rows, source_events, k=5):
    source_idx = [int(r["_i"]) for r in source_events]
    source_set = set(source_idx)
    sret = scale_iqr(rows, "s2_ret20_pct")
    srv = scale_iqr(rows, "s2_rv20_pct")
    out = {}
    for e in source_events:
        ei = int(e["_i"])
        pr, vr = e.get("s2_price_regime"), e.get("s2_vol_regime")
        er, ev = num(e.get("s2_ret20_pct")), num(e.get("s2_rv20_pct"))
        cand = []
        for r in rows:
            ri = int(r["_i"])
            if ri in source_set or ri + 40 >= len(rows):
                continue
            if any(abs(ri - x) <= 20 for x in source_idx):
                continue
            if pr is None or vr is None or r.get("s2_price_regime") != pr or r.get("s2_vol_regime") != vr:
                continue
            rr, rv = num(r.get("s2_ret20_pct")), num(r.get("s2_rv20_pct"))
            if None in (er, ev, rr, rv):
                continue
            d = math.sqrt(((er - rr) / sret) ** 2 + ((ev - rv) / srv) ** 2)
            cand.append((d, r))
        cand.sort(key=lambda x: x[0])
        picked = [r for _, r in cand[:k]]
        out[ei] = picked
    return out


def transition_pair(source_name, source_events, dest_name, dest_events, controls):
    dest_idx = sorted(int(r["_i"]) for r in dest_events)
    same = source_name == dest_name
    src_lags = [first_lag(int(r["_i"]), dest_idx, same) for r in source_events]
    result = {
        "source_n": len(source_events),
        "destination_n": len(dest_events),
        "first_hit_lag_all": lag_summary(src_lags),
    }
    for h in HORIZONS:
        hits = [x is not None and x <= h for x in src_lags]
        treatment_rate = None if not hits else 100.0 * sum(hits) / len(hits)
        per_source_ctrl = []
        ctrl_n = 0
        for e in source_events:
            cs = controls.get(int(e["_i"]), [])
            if not cs:
                continue
            vals = []
            for c in cs:
                lag = first_lag(int(c["_i"]), dest_idx, False)
                vals.append(1.0 if lag is not None and lag <= h else 0.0)
            if vals:
                per_source_ctrl.append(mean(vals)); ctrl_n += len(vals)
        base = None if not per_source_ctrl else 100.0 * mean(per_source_ctrl)
        result[f"within_{h}"] = {
            "hit_n": sum(hits),
            "hit_rate_pct": None if treatment_rate is None else round(treatment_rate, 2),
            "matched_control_dates_n": ctrl_n,
            "matched_control_hit_rate_pct": None if base is None else round(base, 2),
            "excess_hit_rate_pp": None if treatment_rate is None or base is None else round(treatment_rate - base, 2),
        }
    return result


def outcome_summary(events):
    return mod.summary(events)


def sentiment_destination_split(sent_events, dest_events, h=20):
    dest_idx = sorted(int(r["_i"]) for r in dest_events)
    yes, no, lags = [], [], []
    for e in sent_events:
        lag = first_lag(int(e["_i"]), dest_idx, False)
        if lag is not None and lag <= h:
            yes.append(e); lags.append(lag)
        else:
            no.append(e)
    out = {
        "reached_within_sessions": h,
        "reached": outcome_summary(yes),
        "not_reached": outcome_summary(no),
        "lag": lag_summary(lags),
    }
    for x in RET_H:
        a = out["reached"].get(f"{x}d", {}).get("mean_pct")
        b = out["not_reached"].get(f"{x}d", {}).get("mean_pct")
        out[f"reached_minus_not_{x}d_pp"] = None if a is None or b is None else round(a - b, 4)
    return out


def transition_study(rows, sets):
    controls = {name: control_map(rows, events) for name, events in sets.items()}
    matrix = {}
    for sname, sev in sets.items():
        matrix[sname] = {}
        for dname, dev in sets.items():
            matrix[sname][dname] = transition_pair(sname, sev, dname, dev, controls[sname])
    sent = sets["sentiment_extreme"]
    sent_splits = {
        d: sentiment_destination_split(sent, sets[d], 20)
        for d in ("box_bottom", "breadth_low", "breadth_rebound10", "score_recovery", "early_sequence", "full_sequence")
    }
    return {
        "event_counts": {k: len(v) for k, v in sets.items()},
        "event_dates": {k: [r["date"] for r in v] for k, v in sets.items()},
        "source_outcomes": {k: outcome_summary(v) for k, v in sets.items()},
        "matrix": matrix,
        "sentiment_20session_destination_splits": sent_splits,
    }


def sparse_models(rows):
    baseline = ["s2_ret20_pct", "s2_rv20_pct", "fm_above200"]
    fam = {
        "sentiment": ["sentiment_stress_pct"],
        "liquidity": ["net_liq_4w_pct", "reserves_4w_pct"],
        "score": ["market_score_pct", "market_score_d1", "market_score_d3"],
    }
    models = {
        "baseline": baseline,
        "baseline_plus_sentiment": baseline + fam["sentiment"],
        "baseline_plus_liquidity": baseline + fam["liquidity"],
        "baseline_plus_score": baseline + fam["score"],
        "baseline_plus_sentiment_liquidity": baseline + fam["sentiment"] + fam["liquidity"],
        "baseline_plus_sentiment_score": baseline + fam["sentiment"] + fam["score"],
        "baseline_plus_liquidity_score": baseline + fam["liquidity"] + fam["score"],
        "baseline_plus_sentiment_liquidity_score": baseline + fam["sentiment"] + fam["liquidity"] + fam["score"],
    }
    union = sorted(set(f for fs in models.values() for f in fs))
    out = {"models": models, "horizons": {}}
    for h in RET_H:
        ykey = f"fwd_{h}d"
        common = fm.usable_rows(rows, union, ykey)
        result = {}
        for name, features in models.items():
            cv = fm.loyo_mse(common, features, ykey)
            result[name] = cv
        bm = result["baseline"]["mse"]
        for name, r in result.items():
            r["mse_improvement_vs_baseline_pct"] = None if bm in (None, 0) or r["mse"] is None else round(100.0 * (bm - r["mse"]) / bm, 4)
        out["horizons"][f"{h}d"] = {"common_complete_case_n": len(common), "results": result}
    if FACTOR.exists():
        d = json.loads(FACTOR.read_text(encoding="utf-8"))
        dense = d.get("five_family_factor_map", {}).get("orthogonal_ols_and_loyo", {})
        out["dense_five_family_reference"] = {
            k: {
                "complete_case_n": v.get("complete_case_n"),
                "loyo_full_vs_baseline_mse_improvement_pct": v.get("loyo_full_vs_baseline_mse_improvement_pct"),
            }
            for k, v in dense.items()
        }
    return out


def main():
    rows = build_rows()
    sets = event_sets(rows)
    out = {
        "schema": "CROSS-FAMILY-TRANSITION-STAGE2-V1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "diagnostic_only": True,
        "production_effect": "none",
        "thresholds_changed": False,
        "study_spec": "research/cross_family_transition_stage2_v1/STUDY_SPEC.md",
        "coverage": {"start": rows[0]["date"], "end": rows[-1]["date"], "observations": len(rows)},
        "transition_study": transition_study(rows, sets),
        "sparse_factor_followup": sparse_models(rows),
        "decision": {
            "may_change_production": False,
            "may_change_forward_oos": False,
            "may_select_new_threshold": False,
            "may_promote_sparse_model": False,
        },
        "warnings": [
            "Historical post-discovery diagnostics only; transition association is not causal proof.",
            "Small transition cells must be down-weighted.",
            "FRED current-history values may contain revisions and are not ALFRED vintage data.",
            "Sparse subsets were frozen after observing the prior dense-factor diagnostic; they are not fresh OOS model selection.",
        ],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    t = out["transition_study"]["matrix"]["sentiment_extreme"]
    sp = out["sparse_factor_followup"]["horizons"]["10d"]["results"]
    print(json.dumps({
        "event_counts": out["transition_study"]["event_counts"],
        "sentiment_to_box_20": t["box_bottom"]["within_20"],
        "sentiment_to_breadth_rebound_20": t["breadth_rebound10"]["within_20"],
        "sentiment_to_early_20": t["early_sequence"]["within_20"],
        "sentiment_to_full_20": t["full_sequence"]["within_20"],
        "sparse_10d": {k: v["mse_improvement_vs_baseline_pct"] for k, v in sp.items()},
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
