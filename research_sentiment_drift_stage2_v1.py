"""Sentiment history drift and data-quality diagnostics.

Research-only. Rolling percentile comparators are diagnostics, not candidate rules.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median, pstdev

import research_modules_stage2_v1 as mod

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "docs/data/market_state_box_v1.json"
OUT = ROOT / "docs/data/sentiment_drift_stage2_v1.json"
THRESHOLDS = (70.0, 80.0, 90.0)
ERAS = {
    "2017_2019": ("2017-01-01", "2019-12-31"),
    "2020_2021": ("2020-01-01", "2021-12-31"),
    "2022_2026": ("2022-01-01", "2026-12-31"),
}


def num(x):
    return mod.num(x)


def qtile(xs, p):
    return mod.qtile(xs, p)


def stats(xs):
    a = [num(x) for x in xs]
    a = [x for x in a if x is not None]
    if not a:
        return {"n": 0}
    return {
        "n": len(a),
        "mean": round(mean(a), 4),
        "median": round(median(a), 4),
        "std": round(pstdev(a), 4) if len(a) > 1 else 0.0,
        "p10": round(qtile(a, 0.10), 4),
        "p90": round(qtile(a, 0.90), 4),
        "max": round(max(a), 4),
        "min": round(min(a), 4),
    }


def corr(xs, ys):
    p = [(num(a), num(b)) for a, b in zip(xs, ys)]
    p = [(a, b) for a, b in p if a is not None and b is not None]
    if len(p) < 3:
        return {"n": len(p), "rho": None}
    r = mod.pearson([a for a, _ in p], [b for _, b in p])
    return {"n": len(p), "rho": None if r is None else round(r, 4)}


def rolling_percentile(values, window, min_n=60):
    out = []
    for i, x in enumerate(values):
        v = num(x)
        if v is None:
            out.append(None); continue
        start = max(0, i - window + 1)
        hist = [num(z) for z in values[start:i + 1]]
        hist = [z for z in hist if z is not None]
        if len(hist) < min_n:
            out.append(None)
        else:
            out.append(100.0 * sum(z <= v for z in hist) / len(hist))
    return out


def onset_indices(rows, field, threshold, gap=5):
    out = []
    prev = False
    last = -10**9
    for i, r in enumerate(rows):
        v = num(r.get(field))
        cur = v is not None and v >= threshold
        if cur and not prev and i - last >= gap:
            out.append(i); last = i
        prev = cur
    return out


def onset_indices_values(values, threshold, gap=5):
    out = []
    prev = False
    last = -10**9
    for i, v0 in enumerate(values):
        v = num(v0); cur = v is not None and v >= threshold
        if cur and not prev and i - last >= gap:
            out.append(i); last = i
        prev = cur
    return out


def forward_summary(rows, idx):
    vals = [num(rows[i].get("fwd_10d")) for i in idx]
    vals = [x for x in vals if x is not None]
    if not vals:
        return {"n": 0}
    return {
        "n": len(vals), "mean_pct": round(mean(vals), 4), "median_pct": round(median(vals), 4),
        "positive_pct": round(100.0 * sum(x > 0 for x in vals) / len(vals), 2),
        "p10_pct": round(qtile(vals, 0.10), 4), "p90_pct": round(qtile(vals, 0.90), 4),
    }


def year_profile(rows, roll252, roll756, ref_mean, ref_std):
    years = sorted(set(r["date"][:4] for r in rows))
    out = {}
    components = ("optimism", "pessimism", "total_negative", "euphoria", "sentiment_stress", "sentiment_stress_pct")
    exp_onsets = {t: set(onset_indices(rows, "sentiment_stress_pct", t)) for t in THRESHOLDS}
    r252_on = set(onset_indices_values(roll252, 80.0))
    r756_on = set(onset_indices_values(roll756, 80.0))
    for y in years:
        idx = [i for i, r in enumerate(rows) if r["date"].startswith(y)]
        rec = {"observations": len(idx), "missing_pct": {}}
        for f in components:
            miss = sum(num(rows[i].get(f)) is None for i in idx)
            rec["missing_pct"][f] = round(100.0 * miss / len(idx), 2) if idx else None
        raw = [rows[i].get("sentiment_stress") for i in idx]
        exp = [rows[i].get("sentiment_stress_pct") for i in idx]
        rec["raw_stress"] = stats(raw)
        rec["expanding_percentile"] = stats(exp)
        if rec["raw_stress"].get("mean") is not None and ref_std > 1e-12:
            rec["raw_stress_mean_shift_z_vs_2018_2021"] = round((rec["raw_stress"]["mean"] - ref_mean) / ref_std, 4)
        else:
            rec["raw_stress_mean_shift_z_vs_2018_2021"] = None
        rec["expanding_thresholds"] = {}
        for t in THRESHOLDS:
            rec["expanding_thresholds"][str(int(t))] = {
                "days_ge": sum(num(rows[i].get("sentiment_stress_pct")) is not None and num(rows[i].get("sentiment_stress_pct")) >= t for i in idx),
                "onsets": sum(i in exp_onsets[t] for i in idx),
            }
        rec["rolling252"] = {
            "stats": stats([roll252[i] for i in idx]),
            "days_ge80": sum(num(roll252[i]) is not None and num(roll252[i]) >= 80 for i in idx),
            "onsets_ge80": sum(i in r252_on for i in idx),
        }
        rec["rolling756"] = {
            "stats": stats([roll756[i] for i in idx]),
            "days_ge80": sum(num(roll756[i]) is not None and num(roll756[i]) >= 80 for i in idx),
            "onsets_ge80": sum(i in r756_on for i in idx),
        }
        dec = {f"D{k+1}": 0 for k in range(10)}
        for i in idx:
            v = num(rows[i].get("sentiment_stress_pct"))
            if v is not None:
                k = min(9, max(0, int(v // 10)))
                dec[f"D{k+1}"] += 1
        rec["expanding_percentile_decile_occupancy"] = dec

        pess = [num(rows[i].get("pessimism")) for i in idx]
        neg = [num(rows[i].get("total_negative")) for i in idx]
        inv_e = [None if num(rows[i].get("euphoria")) is None else 100.0 - num(rows[i].get("euphoria")) for i in idx]
        rec["components"] = {
            "pessimism": stats(pess),
            "total_negative": stats(neg),
            "inverted_euphoria": stats(inv_e),
            "correlations": {
                "pessimism|total_negative": corr(pess, neg),
                "pessimism|inverted_euphoria": corr(pess, inv_e),
                "total_negative|inverted_euphoria": corr(neg, inv_e),
            },
            "near_zero_variance_flags": {
                "pessimism": stats(pess).get("std", 0) < 1e-6,
                "total_negative": stats(neg).get("std", 0) < 1e-6,
                "inverted_euphoria": stats(inv_e).get("std", 0) < 1e-6,
            },
        }
        out[y] = rec
    return out


def era_profile(rows, exp80):
    out = {}
    for name, (start, end) in ERAS.items():
        idx = [i for i, r in enumerate(rows) if start <= r["date"] <= end]
        ev = [i for i in exp80 if i in set(idx)]
        out[name] = {
            "start": start, "end": end, "observations": len(idx),
            "raw_stress": stats([rows[i].get("sentiment_stress") for i in idx]),
            "expanding_percentile": stats([rows[i].get("sentiment_stress_pct") for i in idx]),
            "onset_ge80_n": len(ev), "onset_ge80_dates": [rows[i]["date"] for i in ev],
            "onset_ge80_fwd10": forward_summary(rows, ev),
        }
    return out


def overlap(a, b, window=5):
    def one(x, y):
        return sum(bool(y) and min(abs(i - j) for j in y) <= window for i in x)
    return {
        "a_n": len(a), "b_n": len(b), "window_sessions": window,
        "a_with_b_n": one(a, b), "a_with_b_pct": None if not a else round(100.0 * one(a, b) / len(a), 2),
        "b_with_a_n": one(b, a), "b_with_a_pct": None if not b else round(100.0 * one(b, a) / len(b), 2),
    }


def main():
    src = json.loads(SRC.read_text(encoding="utf-8"))
    rows = mod.enrich(src.get("daily") or [])
    raw = [r.get("sentiment_stress") for r in rows]
    roll252 = rolling_percentile(raw, 252, 60)
    roll756 = rolling_percentile(raw, 756, 60)
    for r, a, b in zip(rows, roll252, roll756):
        r["sd_roll252_pct"] = a; r["sd_roll756_pct"] = b

    ref = [num(r.get("sentiment_stress")) for r in rows if "2018-01-01" <= r["date"] <= "2021-12-31"]
    ref = [x for x in ref if x is not None]
    ref_mean = mean(ref); ref_std = pstdev(ref) if len(ref) > 1 else 0.0
    exp80 = onset_indices(rows, "sentiment_stress_pct", 80.0)
    r252 = onset_indices_values(roll252, 80.0)
    r756 = onset_indices_values(roll756, 80.0)

    yearly = year_profile(rows, roll252, roll756, ref_mean, ref_std)
    out = {
        "schema": "SENTIMENT-DRIFT-STAGE2-V1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "diagnostic_only": True,
        "production_effect": "none",
        "thresholds_changed": False,
        "study_spec": "research/sentiment_drift_stage2_v1/STUDY_SPEC.md",
        "coverage": {"start": rows[0]["date"], "end": rows[-1]["date"], "observations": len(rows)},
        "reference_2018_2021": {"raw_stress_mean": round(ref_mean, 4), "raw_stress_std": round(ref_std, 4), "n": len(ref)},
        "calendar_year": yearly,
        "fixed_eras": era_profile(rows, exp80),
        "rolling_sensitivity": {
            "expanding_vs_rolling252_corr": corr([r.get("sentiment_stress_pct") for r in rows], roll252),
            "expanding_vs_rolling756_corr": corr([r.get("sentiment_stress_pct") for r in rows], roll756),
            "expanding80_onsets": {"n": len(exp80), "dates": [rows[i]["date"] for i in exp80]},
            "rolling252_80_onsets": {"n": len(r252), "dates": [rows[i]["date"] for i in r252]},
            "rolling756_80_onsets": {"n": len(r756), "dates": [rows[i]["date"] for i in r756]},
            "overlap_expanding_vs_rolling252": overlap(exp80, r252, 5),
            "overlap_expanding_vs_rolling756": overlap(exp80, r756, 5),
        },
        "diagnostic_flags": {
            "no_expanding80_onsets_2022_2026": sum(1 for i in exp80 if rows[i]["date"] >= "2022-01-01") == 0,
            "rolling252_has_2022_2026_onsets": any(rows[i]["date"] >= "2022-01-01" for i in r252),
            "rolling756_has_2022_2026_onsets": any(rows[i]["date"] >= "2022-01-01" for i in r756),
            "material_component_missingness_years": [y for y, d in yearly.items() if any(v >= 5.0 for k, v in d["missing_pct"].items() if k in ("pessimism", "total_negative", "euphoria"))],
            "near_zero_component_variance_years": [y for y, d in yearly.items() if any(d["components"]["near_zero_variance_flags"].values())],
        },
        "decision": {"may_change_production": False, "may_change_forward_oos": False, "may_replace_expanding_percentile": False},
        "warnings": [
            "Rolling percentiles are sensitivity diagnostics only, not candidate replacements.",
            "Historical sentiment/model history is reconstructed, not a fully publication-time archive.",
        ],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    post = out["fixed_eras"]["2022_2026"]
    print(json.dumps({
        "expanding80_n": len(exp80),
        "post2022_expanding80_n": post["onset_ge80_n"],
        "post2022_expanding_max": post["expanding_percentile"].get("max"),
        "rolling252_post2022": out["diagnostic_flags"]["rolling252_has_2022_2026_onsets"],
        "rolling756_post2022": out["diagnostic_flags"]["rolling756_has_2022_2026_onsets"],
        "missing_years": out["diagnostic_flags"]["material_component_missingness_years"],
        "zero_variance_years": out["diagnostic_flags"]["near_zero_component_variance_years"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
