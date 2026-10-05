"""Sentiment normalization robustness diagnostics.

Historical / post-discovery only. Rolling-percentile variants are diagnostic
comparators and must not replace the existing expanding definition from this study.
"""
from __future__ import annotations

import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

import research_modules_stage2_v1 as mod

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "docs/data/market_state_box_v1.json"
OUT = ROOT / "docs/data/sentiment_normalization_stage2_v1.json"
SEED = 20261005
ROUNDS = 5000
THRESHOLD = 80.0
GAP = 5
H = (5, 10, 20)
ERAS = {
    "2017_2019": ("2017-01-01", "2019-12-31"),
    "2020_2021": ("2020-01-01", "2021-12-31"),
    "2022_2026": ("2022-01-01", "2026-12-31"),
}


def num(x):
    return mod.num(x)


def qtile(xs, p):
    return mod.qtile(xs, p)


def rolling_percentile(values, window, min_n=60):
    out = []
    for i, x0 in enumerate(values):
        x = num(x0)
        if x is None:
            out.append(None)
            continue
        hist = [num(z) for z in values[max(0, i - window + 1):i + 1]]
        hist = [z for z in hist if z is not None]
        if len(hist) < min_n:
            out.append(None)
        else:
            out.append(100.0 * sum(z <= x for z in hist) / len(hist))
    return out


def events_for_field(rows, field, threshold=THRESHOLD, gap=GAP):
    return mod.event_onsets(rows, lambda r: num(r.get(field)) is not None and num(r.get(field)) >= threshold, gap=gap)


def cluster_count(events, gap=20):
    return mod.cluster_count(events, gap)


def summary(events):
    return mod.summary(events)


def era_result(events, start, end):
    z = [r for r in events if start <= r["date"] <= end]
    return {
        "start": start,
        "end": end,
        "event_count": len(z),
        "event_dates": [r["date"] for r in z],
        "independent_clusters_20": cluster_count(z, 20),
        "outcomes": summary(z),
    }


def full_era_results(events):
    out = {name: era_result(events, a, b) for name, (a, b) in ERAS.items()}
    z = [r for r in events if not ("2020-01-01" <= r["date"] <= "2021-12-31")]
    out["EXCLUDE_2020_2021"] = {
        "event_count": len(z),
        "event_dates": [r["date"] for r in z],
        "independent_clusters_20": cluster_count(z, 20),
        "outcomes": summary(z),
    }
    return out


def placebo(events, rows, seed_offset):
    actual = [num(r.get("fwd_10d")) for r in events]
    actual = [x for x in actual if x is not None]
    n = len(actual)
    event_idx = {int(r["_i"]) for r in events}
    eligible = [r for r in rows if num(r.get("fwd_10d")) is not None and int(r["_i"]) not in event_idx]
    if not actual or len(eligible) < n:
        return {"rounds": ROUNDS, "n": n, "empirical_one_sided_p": None}
    actual_mean = mean(actual)
    rng = random.Random(SEED + seed_offset)
    sims = []
    for _ in range(ROUNDS):
        sample = rng.sample(eligible, n)
        sims.append(mean(num(r.get("fwd_10d")) for r in sample))
    ge = sum(x >= actual_mean for x in sims)
    return {
        "rounds": ROUNDS,
        "n": n,
        "actual_10d_mean_pct": round(actual_mean, 4),
        "placebo_mean_pct": round(mean(sims), 4),
        "placebo_p95_pct": round(qtile(sims, 0.95), 4),
        "actual_percentile": round(100.0 * sum(x <= actual_mean for x in sims) / len(sims), 2),
        "empirical_one_sided_p": round((ge + 1) / (ROUNDS + 1), 5),
    }


def iqr_scale(rows, field):
    vals = [num(r.get(field)) for r in rows]
    vals = [x for x in vals if x is not None]
    if len(vals) < 10:
        return 1.0
    q1, q3 = qtile(vals, 0.25), qtile(vals, 0.75)
    d = (q3 - q1) if q1 is not None and q3 is not None else 0.0
    return d if d > 1e-9 else max(1.0, abs(mean(vals)))


def matched_control(events, rows, k=5):
    event_idx = [int(r["_i"]) for r in events]
    event_set = set(event_idx)
    sr = iqr_scale(rows, "s2_ret20_pct")
    sv = iqr_scale(rows, "s2_rv20_pct")
    records = []
    used_dates = []
    for e in events:
        eret = num(e.get("s2_ret20_pct")); erv = num(e.get("s2_rv20_pct"))
        ep = e.get("s2_price_regime"); ev = e.get("s2_vol_regime")
        if eret is None or erv is None or ep is None or ev is None:
            continue
        cand = []
        for r in rows:
            ri = int(r["_i"])
            if ri in event_set or num(r.get("fwd_20d")) is None:
                continue
            if any(abs(ri - x) <= 20 for x in event_idx):
                continue
            if r.get("s2_price_regime") != ep or r.get("s2_vol_regime") != ev:
                continue
            rr = num(r.get("s2_ret20_pct")); rv = num(r.get("s2_rv20_pct"))
            if rr is None or rv is None:
                continue
            d = math.sqrt(((eret - rr) / sr) ** 2 + ((erv - rv) / sv) ** 2)
            cand.append((d, r))
        cand.sort(key=lambda z: z[0])
        picked = cand[:k]
        if not picked:
            continue
        ctrls = [r for _, r in picked]
        used_dates.extend(r["date"] for r in ctrls)
        rec = {
            "event_date": e["date"],
            "price_regime": ep,
            "vol_regime": ev,
            "controls": [{"date": r["date"], "distance": round(d, 4)} for d, r in picked],
        }
        for h in H:
            a = num(e.get(f"fwd_{h}d"))
            b = [num(r.get(f"fwd_{h}d")) for r in ctrls]
            b = [x for x in b if x is not None]
            rec[f"event_{h}d_pct"] = a
            rec[f"control_mean_{h}d_pct"] = None if not b else round(mean(b), 4)
            rec[f"lift_{h}d_pp"] = None if a is None or not b else round(a - mean(b), 4)
        records.append(rec)
    agg = {}
    for h in H:
        vals = [num(r.get(f"lift_{h}d_pp")) for r in records]
        vals = [x for x in vals if x is not None]
        agg[f"{h}d"] = {"n": len(vals)} if not vals else {
            "n": len(vals),
            "mean_lift_pp": round(mean(vals), 4),
            "median_lift_pp": round(median(vals), 4),
            "positive_lift_pct": round(100.0 * sum(x > 0 for x in vals) / len(vals), 2),
        }
    return {
        "matching": "same price regime + same RV20 regime; nearest equal-weight IQR-normalized ret20/RV20; exclude +/-20 sessions around treatment",
        "controls_per_event": k,
        "unique_control_dates": len(set(used_dates)),
        "aggregate": agg,
        "records": records,
    }


def stability_flag(era_results):
    checked = []
    for name in ("2017_2019", "2020_2021", "2022_2026"):
        d = era_results[name]
        n = d["event_count"]
        m = d["outcomes"].get("10d", {}).get("mean_pct")
        if n >= 5 and m is not None:
            checked.append({"era": name, "n": n, "mean_10d_pct": m, "positive_mean": m > 0})
    return {
        "eras_with_at_least_5_events": checked,
        "positive_10d_mean_in_every_eligible_era": bool(checked) and all(x["positive_mean"] for x in checked),
    }


def variant(rows, name, field, seed_offset):
    ev = events_for_field(rows, field)
    eras = full_era_results(ev)
    return {
        "field": field,
        "threshold": THRESHOLD,
        "decluster_sessions": GAP,
        "event_count": len(ev),
        "event_dates": [r["date"] for r in ev],
        "independent_clusters_20": cluster_count(ev, 20),
        "overall": summary(ev),
        "eras": eras,
        "placebo_10d": placebo(ev, rows, seed_offset),
        "matched_control": matched_control(ev, rows, 5),
        "cross_era_stability": stability_flag(eras),
    }


def main():
    src = json.loads(SRC.read_text(encoding="utf-8"))
    rows = mod.enrich(src.get("daily") or [])
    raw = [r.get("sentiment_stress") for r in rows]
    r252 = rolling_percentile(raw, 252, 60)
    r756 = rolling_percentile(raw, 756, 60)
    for r, a, b in zip(rows, r252, r756):
        r["sn_roll252_pct"] = a
        r["sn_roll756_pct"] = b

    variants = {
        "EXPANDING_EXISTING": variant(rows, "EXPANDING_EXISTING", "sentiment_stress_pct", 1),
        "ROLLING_252_DIAGNOSTIC": variant(rows, "ROLLING_252_DIAGNOSTIC", "sn_roll252_pct", 2),
        "ROLLING_756_DIAGNOSTIC": variant(rows, "ROLLING_756_DIAGNOSTIC", "sn_roll756_pct", 3),
    }
    out = {
        "schema": "SENTIMENT-NORMALIZATION-STAGE2-V1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "diagnostic_only": True,
        "production_effect": "none",
        "thresholds_changed": False,
        "study_spec": "research/sentiment_normalization_stage2_v1/STUDY_SPEC.md",
        "coverage": {"start": rows[0]["date"], "end": rows[-1]["date"], "observations": len(rows)},
        "variants": variants,
        "decision": {
            "may_change_production": False,
            "may_change_forward_oos": False,
            "may_replace_existing_normalization": False,
            "may_promote_rolling_variant": False,
            "historical_best_variant_selection_allowed": False,
        },
        "warnings": [
            "Rolling variants are post-discovery diagnostic comparators, not replacement rules.",
            "Historical sentiment values are reconstructed from currently available Yahoo/FRED history and are not point-in-time archived outputs.",
            "The source sentiment composites themselves already contain rolling-percentile transforms; this study evaluates the robustness of a second normalization layer.",
        ],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        k: {
            "n": v["event_count"],
            "clusters20": v["independent_clusters_20"],
            "10d": v["overall"].get("10d"),
            "post2022_n": v["eras"]["2022_2026"]["event_count"],
            "exclude2020_2021_10d": v["eras"]["EXCLUDE_2020_2021"]["outcomes"].get("10d"),
            "placebo_p": v["placebo_10d"].get("empirical_one_sided_p"),
            "matched_10d_lift": v["matched_control"]["aggregate"].get("10d"),
            "stable": v["cross_era_stability"]["positive_10d_mean_in_every_eligible_era"],
        } for k, v in variants.items()
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
