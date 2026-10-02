"""Strict OOS robustness study for bullish price-vs-up/down-ratio divergence.

Focuses on the previously promising state:
- negative divergence (price weak, up/down structure relatively stronger)
- contemporaneous correlation >= 0.25
- positive ratio-leading correlation >= 0.25

All signal features use only trailing data. Forward returns are evaluation only.
Period boundaries are strict: a horizon is counted only if its exit date remains
inside the same evaluation period.
"""
from __future__ import annotations

import json
from pathlib import Path
from statistics import mean, median

import research_updown_divergence_events as base

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "docs/data/structure_lab.json"
OUT_PATH = ROOT / "docs/data/updown_divergence_oos.json"
SYMBOLS = base.SYMBOLS
THRESHOLDS = [1.0, 1.5, 2.0]
HORIZONS = base.HORIZONS
PERIODS = {
    "IS_1992_2009": ("1992-01-02", "2009-12-31"),
    "OOS_2010_2019": ("2010-01-01", "2019-12-31"),
    "OOS_2020_PLUS": ("2020-01-01", "9999-12-31"),
}
MIN_TRAIN_EVENTS = 10


def baseline_period(bars, start, end):
    out = {}
    for h in HORIZONS:
        vals = []
        for i, b in enumerate(bars):
            if not (start <= b["date"] <= end):
                continue
            if i + h >= len(bars) or bars[i + h]["date"] > end:
                continue
            vals.append(bars[i + h]["close"] / bars[i]["close"] - 1)
        if not vals:
            out[str(h)] = {"n": 0}
            continue
        out[str(h)] = {
            "n": len(vals),
            "avg_return_pct": round(mean(vals) * 100, 3),
            "median_return_pct": round(median(vals) * 100, 3),
            "up_rate_pct": round(sum(v > 0 for v in vals) / len(vals) * 100, 2),
        }
    return out


def event_indices_for_period(bars, f, threshold, start, end):
    idx = base.extract_events(
        bars,
        f,
        side="bull",
        threshold=threshold,
        require_corr=True,
        require_lead=True,
        start_date=start,
    )
    return [i for i in idx if bars[i]["date"] <= end]


def strict_forward_stats(bars, indices, side, end):
    out = {}
    for h in HORIZONS:
        vals, adverse, favorable = [], [], []
        for i in indices:
            if i + h >= len(bars) or bars[i + h]["date"] > end:
                continue
            base_px = bars[i]["close"]
            path = bars[i + 1 : i + h + 1]
            vals.append(bars[i + h]["close"] / base_px - 1)
            if side == "bull":
                adverse.append(min(b["low"] for b in path) / base_px - 1)
                favorable.append(max(b["high"] for b in path) / base_px - 1)
            else:
                adverse.append(max(b["high"] for b in path) / base_px - 1)
                favorable.append(min(b["low"] for b in path) / base_px - 1)
        if not vals:
            out[str(h)] = {"n": 0}
            continue
        hit = sum(v > 0 for v in vals) / len(vals) if side == "bull" else sum(v < 0 for v in vals) / len(vals)
        out[str(h)] = {
            "n": len(vals),
            "avg_return_pct": round(mean(vals) * 100, 3),
            "median_return_pct": round(median(vals) * 100, 3),
            "direction_hit_rate_pct": round(hit * 100, 2),
            "avg_adverse_excursion_pct": round(mean(adverse) * 100, 3),
            "avg_favorable_excursion_pct": round(mean(favorable) * 100, 3),
        }
    return out


def enrich_forward(signal_stats, baseline):
    out = {}
    for h in HORIZONS:
        s = signal_stats.get(str(h), {"n": 0})
        b = baseline.get(str(h), {"n": 0})
        row = dict(s)
        if s.get("n", 0) and b.get("n", 0):
            row["baseline_avg_return_pct"] = b.get("avg_return_pct")
            row["baseline_up_rate_pct"] = b.get("up_rate_pct")
            row["excess_avg_return_pct"] = round(s.get("avg_return_pct", 0) - b.get("avg_return_pct", 0), 3)
            row["excess_up_rate_pp"] = round(s.get("direction_hit_rate_pct", 0) - b.get("up_rate_pct", 0), 2)
        out[str(h)] = row
    return out


def study_threshold(bars, f, threshold, start, end):
    idx = event_indices_for_period(bars, f, threshold, start, end)
    baseline = baseline_period(bars, start, end)
    sig = strict_forward_stats(bars, idx, "bull", end)
    return {
        "events": len(idx),
        "baseline": baseline,
        "forward": enrich_forward(sig, baseline),
        "recent_events": base.sample_events(bars, f, idx),
    }


def choose_threshold(period_results):
    candidates = []
    for th in THRESHOLDS:
        r = period_results[f"{th:.1f}"]
        h20 = r["forward"].get("20", {})
        excess_ret = h20.get("excess_avg_return_pct")
        excess_hit = h20.get("excess_up_rate_pp")
        if (
            r["events"] >= MIN_TRAIN_EVENTS
            and h20.get("n", 0) >= MIN_TRAIN_EVENTS
            and excess_ret is not None
            and excess_hit is not None
            and excess_ret > 0
            and excess_hit > 0
        ):
            candidates.append((excess_ret, th))
    return max(candidates)[1] if candidates else None


def main():
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    out = {
        "schema": "UPDOWN-DIVERGENCE-OOS-V2",
        "method": {
            "signal": "bull divergence + corr>=0.25 + positive ratio-leading corr>=0.25",
            "thresholds": THRESHOLDS,
            "ratio_window": base.RATIO_WINDOW,
            "z_window": base.Z_WINDOW,
            "corr_window": base.CORR_WINDOW,
            "lead_lookback": base.LAG_LOOKBACK,
            "max_positive_lead_days": base.MAX_LEAD,
            "cooldown_trading_days": base.COOLDOWN,
            "periods": PERIODS,
            "strict_period_boundaries": True,
            "selection_rule": "within IS_1992_2009, choose threshold with highest positive 20d excess average return only if both excess average return and excess up-rate are positive and >=10 events; otherwise choose no threshold",
            "lookahead": "none in feature/signal construction; forward returns are evaluation only",
        },
        "results": {},
    }

    for sym in SYMBOLS:
        inst = raw.get("instruments", {}).get(sym)
        if not inst:
            out["results"][sym] = {"error": "missing"}
            continue
        bars = base.load_bars(inst)
        f = base.features(bars)
        periods_out = {}
        for pname, (start, end) in PERIODS.items():
            periods_out[pname] = {
                f"{th:.1f}": study_threshold(bars, f, th, start, end)
                for th in THRESHOLDS
            }

        selected = choose_threshold(periods_out["IS_1992_2009"])
        selected_key = f"{selected:.1f}" if selected is not None else None
        locked = {
            pname: periods_out[pname][selected_key]
            for pname in PERIODS
        } if selected_key else {}

        out["results"][sym] = {
            "name": inst.get("name", sym),
            "start": bars[0]["date"],
            "end": bars[-1]["date"],
            "threshold_grid": periods_out,
            "selected_threshold_from_IS": selected,
            "locked_threshold_results": locked,
        }

        print("\n", sym, inst.get("name", sym), "selected", selected, flush=True)
        for pname in PERIODS:
            print(" ", pname, flush=True)
            for th in THRESHOLDS:
                r = periods_out[pname][f"{th:.1f}"]
                h20 = r["forward"]["20"]
                print(
                    "   th", th,
                    "n", h20.get("n"),
                    "20d avg", h20.get("avg_return_pct"),
                    "excess", h20.get("excess_avg_return_pct"),
                    "up", h20.get("direction_hit_rate_pct"),
                    "excess_pp", h20.get("excess_up_rate_pp"),
                    flush=True,
                )

    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Wrote", OUT_PATH, flush=True)


if __name__ == "__main__":
    main()
