"""Second-stage validation for Market State x Box V1.

No V1 thresholds are changed here. The script measures condition overlap,
calendar distribution, and fixed-rule time-split behavior so a zero/low sample
cannot be hidden by post-hoc parameter tuning.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "docs" / "data" / "market_state_box_v1.json"
OUT = ROOT / "docs" / "data" / "market_state_box_v1_validation.json"

FLAGS = ("box_bottom", "sentiment_extreme", "breadth_extreme_low", "score_recovering")
COMBOS = {
    "baseline": (),
    "box_only": ("box_bottom",),
    "box_sentiment": ("box_bottom", "sentiment_extreme"),
    "box_breadth": ("box_bottom", "breadth_extreme_low"),
    "box_score_recovery": ("box_bottom", "score_recovering"),
    "box_sentiment_breadth": ("box_bottom", "sentiment_extreme", "breadth_extreme_low"),
    "box_sentiment_score": ("box_bottom", "sentiment_extreme", "score_recovering"),
    "box_breadth_score": ("box_bottom", "breadth_extreme_low", "score_recovering"),
    "all_four": FLAGS,
}
SEGMENTS = {
    "pre_2022": lambda d: d < "2022-01-01",
    "oos_2022_plus": lambda d: d >= "2022-01-01",
    "recent_2024_plus": lambda d: d >= "2024-01-01",
}


def decluster(items: list[tuple[int, dict]], gap: int = 5) -> list[dict]:
    out, last = [], -10**9
    for i, row in items:
        if i - last >= gap:
            out.append(row)
            last = i
    return out


def wilson(successes: int, n: int, z: float = 1.96):
    if n <= 0:
        return None
    p = successes / n
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [round(max(0, center - half) * 100, 1), round(min(1, center + half) * 100, 1)]


def bootstrap_mean_ci(vals: list[float], seed: int = 17, reps: int = 2000):
    if len(vals) < 5:
        return None
    rng = random.Random(seed)
    means = []
    n = len(vals)
    for _ in range(reps):
        means.append(mean(vals[rng.randrange(n)] for _ in range(n)))
    means.sort()
    return [round(means[int(.025 * (reps - 1))], 3), round(means[int(.975 * (reps - 1))], 3)]


def event_summary(items: list[tuple[int, dict]]) -> dict:
    rows = decluster(items, 5)
    out = {"n": len(rows)}
    for h in (1, 3, 5, 10):
        vals = [float(r[f"fwd_{h}d"]) for r in rows if r.get(f"fwd_{h}d") is not None]
        pos = sum(v > 0 for v in vals)
        out[f"fwd_{h}d_avg_pct"] = round(mean(vals), 3) if vals else None
        out[f"fwd_{h}d_median_pct"] = round(median(vals), 3) if vals else None
        out[f"fwd_{h}d_positive_pct"] = round(100 * pos / len(vals), 1) if vals else None
        out[f"fwd_{h}d_positive_wilson95"] = wilson(pos, len(vals)) if vals else None
        out[f"fwd_{h}d_mean_bootstrap95"] = bootstrap_mean_ci(vals, 17 + h) if vals else None
    mfe = [float(r["mfe_10d"]) for r in rows if r.get("mfe_10d") is not None]
    mae = [float(r["mae_10d"]) for r in rows if r.get("mae_10d") is not None]
    out["mfe_10d_avg_pct"] = round(mean(mfe), 3) if mfe else None
    out["mae_10d_avg_pct"] = round(mean(mae), 3) if mae else None
    return out


def pairwise(rows: list[dict]) -> dict:
    out = {}
    n = len(rows)
    for i, a in enumerate(FLAGS):
        for b in FLAGS[i + 1:]:
            aa = sum(bool(r.get(a)) for r in rows)
            bb = sum(bool(r.get(b)) for r in rows)
            both = sum(bool(r.get(a)) and bool(r.get(b)) for r in rows)
            union = aa + bb - both
            n11 = both
            n10 = aa - both
            n01 = bb - both
            n00 = n - n11 - n10 - n01
            den = math.sqrt(max(0, (n11+n10)*(n01+n00)*(n11+n01)*(n10+n00)))
            phi = ((n11*n00 - n10*n01) / den) if den else None
            out[f"{a}|{b}"] = {
                "a_n": aa,
                "b_n": bb,
                "both_n": both,
                "union_n": union,
                "jaccard": round(both / union, 4) if union else None,
                "p_b_given_a_pct": round(100 * both / aa, 2) if aa else None,
                "p_a_given_b_pct": round(100 * both / bb, 2) if bb else None,
                "phi": round(phi, 4) if phi is not None else None,
            }
    return out


def main() -> None:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    rows = data.get("daily") or []
    if not rows:
        raise RuntimeError("no daily rows")

    prevalence = {
        f: {"days": sum(bool(r.get(f)) for r in rows),
            "pct": round(100 * sum(bool(r.get(f)) for r in rows) / len(rows), 2)}
        for f in FLAGS
    }

    raw_combo_counts = {
        name: sum(all(bool(r.get(f)) for f in flags) for r in rows)
        for name, flags in COMBOS.items()
    }

    annual = {}
    for r in rows:
        year = str(r.get("date", ""))[:4]
        if not year:
            continue
        y = annual.setdefault(year, {f: 0 for f in FLAGS})
        y["days"] = y.get("days", 0) + 1
        for f in FLAGS:
            y[f] += int(bool(r.get(f)))
        y["all_four"] = y.get("all_four", 0) + int(all(bool(r.get(f)) for f in FLAGS))
        y["box_breadth_score"] = y.get("box_breadth_score", 0) + int(
            bool(r.get("box_bottom")) and bool(r.get("breadth_extreme_low")) and bool(r.get("score_recovering"))
        )

    segments = {}
    indexed = list(enumerate(rows))
    for seg, selector in SEGMENTS.items():
        seg_items = [(i, r) for i, r in indexed if selector(str(r.get("date", "")))]
        combo_stats = {}
        for name, flags in COMBOS.items():
            chosen = [(i, r) for i, r in seg_items if all(bool(r.get(f)) for f in flags)]
            combo_stats[name] = event_summary(chosen)
        segments[seg] = {
            "start": seg_items[0][1].get("date") if seg_items else None,
            "end": seg_items[-1][1].get("date") if seg_items else None,
            "days": len(seg_items),
            "combos": combo_stats,
        }

    validation = {
        "schema": "MARKET-STATE-BOX-V1-VALIDATION",
        "source_generated_at": data.get("generated_at"),
        "coverage": data.get("coverage"),
        "thresholds_frozen": True,
        "threshold_note": "This file does not optimize the V1 thresholds after seeing results.",
        "prevalence": prevalence,
        "raw_combo_counts": raw_combo_counts,
        "pairwise_overlap": pairwise(rows),
        "annual_counts": annual,
        "time_split": segments,
        "caveat": "Time split is an OOS proxy only: sentiment and Market Score histories include reconstructed, non-publication-time observations.",
    }
    OUT.write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    print("validation written", OUT, "all_four raw days", raw_combo_counts["all_four"])


if __name__ == "__main__":
    main()
