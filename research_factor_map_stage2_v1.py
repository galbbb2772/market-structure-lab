"""Cross-family Market Structure Lab Stage-2 diagnostics.

Historical / post-discovery only. No production rule or Forward-OOS ledger changes.
Definitions are frozen in research/factor_map_stage2_v1/STUDY_SPEC.md.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

import numpy as np

import build_market_state_sequence_v1 as seq
import research_modules_stage2_v1 as mod
import research_updown_divergence_events as div
import research_updown_divergence_regime as divreg
import research_updown_divergence_regime_gate_oos as divgate

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "docs/data/market_state_box_v1.json"
STRUCT = ROOT / "docs/data/structure_lab.json"
DIV_OOS = ROOT / "docs/data/updown_divergence_oos.json"
DIV_ROBUST = ROOT / "docs/data/updown_divergence_regime_gate_robust.json"
OUT = ROOT / "docs/data/factor_map_stage2_v1.json"
START = "2016-12-27"
H = (5, 10, 20)


def num(x):
    return mod.num(x)


def event_summary(rows):
    return mod.summary(rows)


def add_local_fields(rows):
    for i, r in enumerate(rows):
        b = num(r.get("breadth_20d_pct"))
        p1 = num(rows[i - 1].get("breadth_20d_pct")) if i >= 1 else None
        p3 = num(rows[i - 3].get("breadth_20d_pct")) if i >= 3 else None
        r["fm_breadth_d1"] = None if b is None or p1 is None else b - p1
        r["fm_breadth_d3"] = None if b is None or p3 is None else b - p3
        r["fm_above200"] = 1.0 if r.get("s2_price_regime") == "above200" else 0.0 if r.get("s2_price_regime") == "below200" else None

        lo = None
        lo_i = None
        for j in range(max(0, i - 9), i + 1):
            z = num(rows[j].get("breadth_20d_pct"))
            if z is not None and (lo is None or z < lo):
                lo, lo_i = z, j
        r["fm_breadth_rebound10"] = bool(
            lo is not None and lo <= 20.0 and lo_i is not None and lo_i < i
            and b is not None and p1 is not None and b > lo and b > p1
        )

        nl = num(r.get("net_liq_4w_pct")); rr = num(r.get("reserves_4w_pct"))
        r["fm_liquidity_stress"] = None if nl is None or rr is None else -(nl + rr) / 2.0
        s = num(r.get("sentiment_stress_pct"))
        r["fm_sentiment_stress"] = s
        r["fm_breadth_stress"] = None if b is None else 100.0 - b
        bp = num(r.get("box_position"))
        r["fm_box_depth"] = None if bp is None else -bp
        sc = num(r.get("market_score_pct"))
        r["fm_score_stress"] = None if sc is None else 100.0 - sc
    return rows


def split_summary(events, predicate):
    yes = [r for r in events if predicate(r)]
    no = [r for r in events if not predicate(r)]
    out = {"with": event_summary(yes), "without": event_summary(no)}
    for h in H:
        a = out["with"].get(f"{h}d", {}).get("mean_pct")
        b = out["without"].get(f"{h}d", {}).get("mean_pct")
        out[f"mean_lift_with_minus_without_{h}d_pp"] = None if a is None or b is None else round(a - b, 4)
    return out


def sentiment_block(rows):
    events = mod.event_onsets(rows, lambda r: num(r.get("sentiment_stress_pct")) is not None and num(r.get("sentiment_stress_pct")) >= 80.0)
    price_x_vol = {}
    for p in ("above200", "below200"):
        for v in ("high_ge20", "low_lt20"):
            z = [r for r in events if r.get("s2_price_regime") == p and r.get("s2_vol_regime") == v]
            price_x_vol[f"{p}|{v}"] = event_summary(z)
    model_regime = {}
    for z in ("red", "yellow", "blue", "green"):
        model_regime[z] = event_summary([r for r in events if r.get("market_regime") == z])

    return {
        "definition": "sentiment_stress_pct >= 80 false->true onset, 5-session de-cluster",
        "event_count": len(events),
        "event_dates": [r["date"] for r in events],
        "overall": event_summary(events),
        "price_x_rv20": price_x_vol,
        "market_model_regime": model_regime,
        "interactions": {
            "box_bottom": split_summary(events, lambda r: num(r.get("box_position")) is not None and num(r.get("box_position")) <= 0.25),
            "breadth_rebound10": split_summary(events, lambda r: bool(r.get("fm_breadth_rebound10"))),
            "early_sequence": split_summary(events, lambda r: bool(r.get("fm_early_sequence"))),
            "full_sequence": split_summary(events, lambda r: bool(r.get("D_TO_BOTH_REBOUND_SCORE"))),
        },
    }


def sequence_events(rows):
    full = seq.event_onsets(rows, "D_TO_BOTH_REBOUND_SCORE")
    early = mod.event_onsets(
        rows,
        lambda r: bool(r.get("D_TO_BREADTH_LOW")) and bool(r.get("box_bottom_since_dual")) and bool(r.get("breadth_rebound_since_dual")),
        gap=5,
    )
    return full, early


def nearest_stats(a, b, windows=(0, 5, 10, 20)):
    bidx = [int(r["_i"]) for r in b]
    mins = []
    for r in a:
        i = int(r["_i"])
        mins.append(None if not bidx else min(abs(i - j) for j in bidx))
    out = {"n": len(a), "reference_n": len(b)}
    for w in windows:
        n = sum(x is not None and x <= w for x in mins)
        out[f"within_{w}_sessions_n"] = n
        out[f"within_{w}_sessions_pct"] = None if not a else round(100.0 * n / len(a), 2)
    finite = [x for x in mins if x is not None]
    out["median_nearest_gap_sessions"] = None if not finite else round(median(finite), 2)
    return out


def near_split(events, refs, gap=10):
    idx = [int(r["_i"]) for r in refs]
    near, far = [], []
    for r in events:
        i = int(r["_i"])
        hit = bool(idx and min(abs(i - j) for j in idx) <= gap)
        (near if hit else far).append(r)
    out = {"near": event_summary(near), "far": event_summary(far)}
    for h in H:
        a = out["near"].get(f"{h}d", {}).get("mean_pct")
        b = out["far"].get(f"{h}d", {}).get("mean_pct")
        out[f"near_minus_far_{h}d_pp"] = None if a is None or b is None else round(a - b, 4)
    return out


def divergence_block(rows, full, early):
    raw = json.loads(STRUCT.read_text(encoding="utf-8"))
    oos = json.loads(DIV_OOS.read_text(encoding="utf-8"))
    robust = json.loads(DIV_ROBUST.read_text(encoding="utf-8"))
    threshold = oos.get("results", {}).get("^GSPC", {}).get("selected_threshold_from_IS")
    selected_gate = robust.get("results", {}).get("^GSPC", {}).get("selected_gate")
    if threshold is None:
        threshold = 1.5
    if abs(float(threshold) - 1.5) > 1e-9:
        raise RuntimeError(f"Expected locked SPX divergence threshold 1.5, got {threshold}")
    if selected_gate != "NOT_HIGH_VOL":
        raise RuntimeError(f"Expected locked SPX robust gate NOT_HIGH_VOL, got {selected_gate}")

    inst = raw["instruments"]["^GSPC"]
    bars = div.load_bars(inst)
    feat = div.features(bars)
    labels = divreg.compute_regimes(bars)
    idx = div.extract_events(bars, feat, side="bull", threshold=1.5, require_corr=True, require_lead=True, start_date=START)
    gate_fn = divgate.gate_defs()["NOT_HIGH_VOL"]
    gated = [i for i in idx if gate_fn(i, labels)]

    by_date = {r["date"]: r for r in rows}
    ev = [by_date[bars[i]["date"]] for i in idx if bars[i]["date"] in by_date]
    gev = [by_date[bars[i]["date"]] for i in gated if bars[i]["date"] in by_date]

    return {
        "locked_threshold": 1.5,
        "locked_filters": "corr>=0.25 and positive ratio-leading corr>=0.25",
        "locked_robust_gate": "NOT_HIGH_VOL",
        "raw_event_count_in_state_coverage": len(ev),
        "gated_event_count_in_state_coverage": len(gev),
        "raw_event_dates": [r["date"] for r in ev],
        "gated_event_dates": [r["date"] for r in gev],
        "raw_outcomes": event_summary(ev),
        "gated_outcomes": event_summary(gev),
        "raw_vs_full_sequence": {
            "divergence_to_sequence": nearest_stats(ev, full),
            "sequence_to_divergence": nearest_stats(full, ev),
            "divergence_near10_vs_far": near_split(ev, full, 10),
            "sequence_near10_vs_far": near_split(full, ev, 10),
        },
        "raw_vs_early_sequence": {
            "divergence_to_early": nearest_stats(ev, early),
            "early_to_divergence": nearest_stats(early, ev),
            "divergence_near10_vs_far": near_split(ev, early, 10),
            "early_near10_vs_far": near_split(early, ev, 10),
        },
        "gated_vs_full_sequence": {
            "divergence_to_sequence": nearest_stats(gev, full),
            "sequence_to_divergence": nearest_stats(full, gev),
        },
        "gated_vs_early_sequence": {
            "divergence_to_early": nearest_stats(gev, early),
            "early_to_divergence": nearest_stats(early, gev),
        },
    }


def rankdata(vals):
    return mod.rankdata(vals)


def spearman_pairs(rows, a, b):
    x, y = [], []
    for r in rows:
        u, v = num(r.get(a)), num(r.get(b))
        if u is not None and v is not None:
            x.append(u); y.append(v)
    if len(x) < 3:
        return {"n": len(x), "rho": None}
    rho = mod.pearson(rankdata(x), rankdata(y))
    return {"n": len(x), "rho": None if rho is None else round(rho, 4)}


def usable_rows(rows, features, ykey):
    out = []
    for r in rows:
        if num(r.get(ykey)) is None:
            continue
        if all(num(r.get(f)) is not None for f in features):
            out.append(r)
    return out


def design(train, test, features, ykey):
    mu, sd = {}, {}
    for f in features:
        vals = np.array([float(r[f]) for r in train], dtype=float)
        mu[f] = float(vals.mean())
        s = float(vals.std(ddof=0))
        sd[f] = s if s > 1e-12 else 1.0
    def mat(rs):
        x = np.ones((len(rs), len(features) + 1), dtype=float)
        for j, f in enumerate(features, start=1):
            x[:, j] = [(float(r[f]) - mu[f]) / sd[f] for r in rs]
        y = np.array([float(r[ykey]) for r in rs], dtype=float)
        return x, y
    return (*mat(train), *mat(test))


def in_sample_r2(rows, features, ykey):
    if len(rows) < len(features) + 5:
        return None
    x, y, _, _ = design(rows, rows, features, ykey)
    beta = np.linalg.lstsq(x, y, rcond=None)[0]
    pred = x @ beta
    sse = float(np.sum((y - pred) ** 2))
    sst = float(np.sum((y - y.mean()) ** 2))
    return None if sst <= 0 else 1.0 - sse / sst


def loyo_mse(rows, features, ykey):
    years = sorted(set(r["date"][:4] for r in rows))
    se = []
    folds = []
    for y in years:
        test = [r for r in rows if r["date"].startswith(y)]
        train = [r for r in rows if not r["date"].startswith(y)]
        if len(test) < 10 or len(train) < len(features) + 10:
            continue
        xtr, ytr, xte, yte = design(train, test, features, ykey)
        beta = np.linalg.lstsq(xtr, ytr, rcond=None)[0]
        pred = xte @ beta
        fold_se = (yte - pred) ** 2
        se.extend(float(x) for x in fold_se)
        folds.append({"year": y, "n": len(test), "mse": round(float(fold_se.mean()), 6)})
    return {"n": len(se), "mse": None if not se else round(mean(se), 6), "folds": folds}


def factor_map(rows):
    baseline = ["s2_ret20_pct", "s2_rv20_pct", "fm_above200"]
    families = {
        "liquidity": ["net_liq_4w_pct", "reserves_4w_pct"],
        "sentiment": ["sentiment_stress_pct"],
        "breadth": ["breadth_20d_pct", "fm_breadth_d1", "fm_breadth_d3"],
        "box": ["box_position"],
        "score": ["market_score_pct", "market_score_d1", "market_score_d3"],
    }
    reps = {
        "liquidity": "fm_liquidity_stress",
        "sentiment": "fm_sentiment_stress",
        "breadth": "fm_breadth_stress",
        "box": "fm_box_depth",
        "score": "fm_score_stress",
    }
    all_family_features = [f for fs in families.values() for f in fs]
    all_features = baseline + all_family_features

    pairwise = {}
    names = list(reps)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            pairwise[f"{a}|{b}"] = spearman_pairs(rows, reps[a], reps[b])

    representative_ic = {}
    for fam, f in reps.items():
        representative_ic[fam] = {f"{h}d": spearman_pairs(rows, f, f"fwd_{h}d") for h in H}

    horizons = {}
    for h in H:
        ykey = f"fwd_{h}d"
        complete = usable_rows(rows, all_features, ykey)
        full_r2 = in_sample_r2(complete, all_features, ykey)
        base_r2 = in_sample_r2(complete, baseline, ykey)
        full_cv = loyo_mse(complete, all_features, ykey)
        base_cv = loyo_mse(complete, baseline, ykey)
        fam_out = {}
        for fam, fs in families.items():
            reduced = [f for f in all_features if f not in fs]
            rr = in_sample_r2(complete, reduced, ykey)
            cv = loyo_mse(complete, reduced, ykey)
            fam_out[fam] = {
                "in_sample_r2_without_family": None if rr is None else round(rr, 6),
                "incremental_r2_full_minus_without": None if full_r2 is None or rr is None else round(full_r2 - rr, 6),
                "loyo_mse_without_family": cv["mse"],
                "loyo_mse_improvement_pct_from_family": None if cv["mse"] in (None, 0) or full_cv["mse"] is None else round(100.0 * (cv["mse"] - full_cv["mse"]) / cv["mse"], 4),
            }
        horizons[f"{h}d"] = {
            "complete_case_n": len(complete),
            "in_sample_r2_baseline": None if base_r2 is None else round(base_r2, 6),
            "in_sample_r2_full": None if full_r2 is None else round(full_r2, 6),
            "in_sample_r2_full_minus_baseline": None if full_r2 is None or base_r2 is None else round(full_r2 - base_r2, 6),
            "loyo_baseline": base_cv,
            "loyo_full": full_cv,
            "loyo_full_vs_baseline_mse_improvement_pct": None if base_cv["mse"] in (None, 0) or full_cv["mse"] is None else round(100.0 * (base_cv["mse"] - full_cv["mse"]) / base_cv["mse"], 4),
            "family_leave_one_out": fam_out,
        }

    feature_ic10 = {}
    for fam, fs in families.items():
        feature_ic10[fam] = {f: spearman_pairs(rows, f, "fwd_10d") for f in fs}

    return {
        "baseline_controls": baseline,
        "families": families,
        "representative_composites": reps,
        "representative_pairwise_spearman": pairwise,
        "representative_forward_spearman": representative_ic,
        "feature_forward_10d_spearman": feature_ic10,
        "orthogonal_ols_and_loyo": horizons,
    }


def main():
    state = json.loads(STATE.read_text(encoding="utf-8"))
    base_rows = mod.enrich(state.get("daily") or [])

    # Rebuild the existing frozen DUAL/Sequence state. This uses the same conservative FRED timing as Sequence V1.
    rows = seq.add_dual(base_rows)
    rows, _ = seq.enrich_sequence(rows)
    rows = add_local_fields(rows)

    # Freeze event identity before sentiment block.
    full, early = sequence_events(rows)
    full_idx = {int(r["_i"]) for r in full}
    early_idx = {int(r["_i"]) for r in early}
    for r in rows:
        r["fm_full_sequence_onset"] = int(r["_i"]) in full_idx
        r["fm_early_sequence"] = int(r["_i"]) in early_idx

    out = {
        "schema": "CROSS-FAMILY-FACTOR-MAP-STAGE2-V1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "diagnostic_only": True,
        "production_effect": "none",
        "thresholds_changed": False,
        "study_spec": "research/factor_map_stage2_v1/STUDY_SPEC.md",
        "coverage": {
            "start": rows[0]["date"] if rows else None,
            "end": rows[-1]["date"] if rows else None,
            "observations": len(rows),
            "full_sequence_events": len(full),
            "early_sequence_events": len(early),
        },
        "sentiment_regime_and_interactions": sentiment_block(rows),
        "breadth_divergence_orthogonality": divergence_block(rows, full, early),
        "five_family_factor_map": factor_map(rows),
        "decision": {
            "may_change_production": False,
            "may_change_forward_oos": False,
            "may_optimize_weights": False,
            "may_promote_historical_interaction": False,
        },
        "warnings": [
            "Historical / post-discovery diagnostic only; interaction cells can be very small.",
            "FRED current-history values may contain revisions and are not ALFRED vintage data.",
            "In-sample incremental R2 without positive Leave-One-Year-Out contribution is explanatory, not prospective evidence.",
            "The locked bullish divergence threshold and robust gate are reused; they are not re-selected here.",
        ],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    s = out["sentiment_regime_and_interactions"]
    d = out["breadth_divergence_orthogonality"]
    f = out["five_family_factor_map"]["orthogonal_ols_and_loyo"]["10d"]
    print(json.dumps({
        "sentiment_events": s["event_count"],
        "sentiment_10d": s["overall"].get("10d"),
        "divergence_events": d["raw_event_count_in_state_coverage"],
        "divergence_gated_events": d["gated_event_count_in_state_coverage"],
        "factor_complete_n_10d": f["complete_case_n"],
        "factor_loyo_full_vs_baseline_improvement_pct": f["loyo_full_vs_baseline_mse_improvement_pct"],
        "family_loyo_10d": {k: v["loyo_mse_improvement_pct_from_family"] for k, v in f["family_leave_one_out"].items()},
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
