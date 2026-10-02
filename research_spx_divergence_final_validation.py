"""Final validation pack for the surviving S&P 500 up/down-divergence signal.

Rule is FROZEN before this study:
- S&P 500 only
- bullish/negative divergence threshold = 1.5 sigma
- contemporaneous corr >= 0.25
- positive ratio-leading corr >= 0.25
- 20-trading-day cooldown
- regime gate = NOT_HIGH_VOL (trailing 20d realized-vol percentile < 70%)

No parameter is selected or tuned here. This script only measures robustness:
1) full event ledger and forward paths
2) event-bootstrap confidence intervals
3) fixed-rule rolling/non-overlapping stability windows
4) leave-one-event-out sensitivity
5) untouched 2020+ holdout diagnostics
"""
from __future__ import annotations

import json, math, random
from pathlib import Path
from statistics import mean, median

import research_updown_divergence_events as base
import research_updown_divergence_regime as reg

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "docs/data/structure_lab.json"
OUT_PATH = ROOT / "docs/data/spx_divergence_final_validation.json"
SYMBOL = "^GSPC"
START = "1992-01-02"
THRESHOLD = 1.5
BOOT_N = 20000
SEED = 2601002
HORIZONS = [5, 10, 20, 40]


def pct(v):
    return round(v * 100, 3)


def percentile(xs, q):
    if not xs:
        return None
    s = sorted(xs)
    if len(s) == 1:
        return s[0]
    p = (len(s) - 1) * q
    lo = int(math.floor(p)); hi = int(math.ceil(p))
    if lo == hi:
        return s[lo]
    w = p - lo
    return s[lo] * (1 - w) + s[hi] * w


def stats(vals):
    if not vals:
        return {"n": 0}
    s = sorted(vals)
    trim = max(0, int(len(s) * 0.1))
    tv = s[trim:len(s)-trim] if trim and len(s) > 2 * trim else s
    return {
        "n": len(vals),
        "avg_return_pct": pct(mean(vals)),
        "median_return_pct": pct(median(vals)),
        "trimmed_mean_10pct_pct": pct(mean(tv)),
        "up_rate_pct": round(sum(v > 0 for v in vals) / len(vals) * 100, 2),
        "p25_pct": pct(percentile(vals, .25)),
        "p75_pct": pct(percentile(vals, .75)),
        "min_pct": pct(min(vals)),
        "max_pct": pct(max(vals)),
    }


def bootstrap_event_mean(event_vals, baseline_mean, n=BOOT_N):
    rng = random.Random(SEED)
    if not event_vals:
        return {"n": 0}
    means, medians, uprates, excess = [], [], [], []
    m = len(event_vals)
    for _ in range(n):
        sample = [event_vals[rng.randrange(m)] for __ in range(m)]
        av = mean(sample)
        means.append(av)
        medians.append(median(sample))
        uprates.append(sum(v > 0 for v in sample) / m)
        excess.append(av - baseline_mean)
    return {
        "n_events": m,
        "bootstrap_reps": n,
        "mean_return_95ci_pct": [pct(percentile(means, .025)), pct(percentile(means, .975))],
        "median_return_95ci_pct": [pct(percentile(medians, .025)), pct(percentile(medians, .975))],
        "up_rate_95ci_pct": [round(percentile(uprates, .025) * 100, 2), round(percentile(uprates, .975) * 100, 2)],
        "excess_mean_95ci_pct": [pct(percentile(excess, .025)), pct(percentile(excess, .975))],
        "bootstrap_prob_mean_gt_0_pct": round(sum(v > 0 for v in means) / n * 100, 2),
        "bootstrap_prob_excess_gt_0_pct": round(sum(v > 0 for v in excess) / n * 100, 2),
    }


def future_return(bars, i, h):
    if i + h >= len(bars):
        return None
    return bars[i+h]["close"] / bars[i]["close"] - 1


def signal_indices(bars, feat, labels):
    idx = base.extract_events(
        bars, feat, side="bull", threshold=THRESHOLD,
        require_corr=True, require_lead=True, start_date=START,
    )
    # Frozen robust gate: exclude high-volatility states; require a valid vol regime.
    return [i for i in idx if labels["vol"][i] in ("LOW_LE_30PCT", "MID_30_TO_70PCT")]


def baseline_indices(bars, labels, start=START, end=None):
    return [
        i for i, b in enumerate(bars)
        if b["date"] >= start
        and (end is None or b["date"] <= end)
        and labels["vol"][i] in ("LOW_LE_30PCT", "MID_30_TO_70PCT")
    ]


def subset_by_dates(indices, bars, start, end=None):
    return [i for i in indices if bars[i]["date"] >= start and (end is None or bars[i]["date"] <= end)]


def summarize_period(bars, sig_idx, base_idx):
    out = {"signal_events": len(sig_idx), "baseline_days": len(base_idx), "forward": {}}
    for h in HORIZONS:
        sv = [future_return(bars, i, h) for i in sig_idx]
        bv = [future_return(bars, i, h) for i in base_idx]
        sv = [v for v in sv if v is not None]
        bv = [v for v in bv if v is not None]
        ss, bs = stats(sv), stats(bv)
        row = {"signal": ss, "baseline_not_high_vol": bs}
        if sv and bv:
            row["excess_avg_return_pct"] = round(ss["avg_return_pct"] - bs["avg_return_pct"], 3)
            row["excess_up_rate_pp"] = round(ss["up_rate_pct"] - bs["up_rate_pct"], 2)
        out["forward"][str(h)] = row
    return out


def event_rows(bars, feat, labels, indices):
    rows = []
    for i in indices:
        lag, lc = base.ensure_best_lead(feat, i)
        basepx = bars[i]["close"]
        path = []
        for k in range(0, 41):
            if i + k >= len(bars):
                break
            path.append({"day": k, "return_pct": round((bars[i+k]["close"] / basepx - 1) * 100, 4)})
        fwd = {str(h): (pct(future_return(bars, i, h)) if future_return(bars, i, h) is not None else None) for h in HORIZONS}
        path20 = bars[i+1:i+21] if i + 20 < len(bars) else []
        rows.append({
            "date": bars[i]["date"],
            "close": round(basepx, 4),
            "divergence_z": round(feat["div"][i], 3),
            "ret20_pct": round(feat["ret20"][i] * 100, 3),
            "updown_ratio": ("inf" if feat["ratio"][i] is not None and math.isinf(feat["ratio"][i]) else round(feat["ratio"][i], 4)),
            "rolling_corr": round(feat["corr"][i], 3),
            "best_ratio_lead_days": lag,
            "best_ratio_lead_corr": round(lc, 3) if lc is not None else None,
            "vol_percentile": round(labels["vol_pct"][i] * 100, 2) if labels["vol_pct"][i] is not None else None,
            "vol_regime": labels["vol"][i],
            "trend": labels["trend"][i],
            "drawdown60_pct": round(labels["dd60"][i] * 100, 3) if labels["dd60"][i] is not None else None,
            "forward_return_pct": fwd,
            "mae20_pct": round((min(b["low"] for b in path20) / basepx - 1) * 100, 3) if path20 else None,
            "mfe20_pct": round((max(b["high"] for b in path20) / basepx - 1) * 100, 3) if path20 else None,
            "path_0_40": path,
        })
    return rows


def path_summary(rows):
    out = []
    for day in range(0, 41):
        vals = []
        for r in rows:
            hit = next((p["return_pct"] / 100 for p in r["path_0_40"] if p["day"] == day), None)
            if hit is not None:
                vals.append(hit)
        if not vals:
            continue
        out.append({
            "day": day,
            "n": len(vals),
            "mean_pct": pct(mean(vals)),
            "median_pct": pct(median(vals)),
            "p25_pct": pct(percentile(vals, .25)),
            "p75_pct": pct(percentile(vals, .75)),
            "positive_rate_pct": round(sum(v > 0 for v in vals) / len(vals) * 100, 2) if day else 0.0,
        })
    return out


def leave_one_out(bars, sig_idx, base_idx, h=20):
    vals = [(i, future_return(bars, i, h)) for i in sig_idx]
    vals = [(i, v) for i, v in vals if v is not None]
    basevals = [future_return(bars, i, h) for i in base_idx]
    basevals = [v for v in basevals if v is not None]
    bmean = mean(basevals) if basevals else 0.0
    rows = []
    for drop_i, _ in vals:
        kept = [v for i, v in vals if i != drop_i]
        if not kept:
            continue
        rows.append({
            "dropped_event": bars[drop_i]["date"],
            "mean20_pct": pct(mean(kept)),
            "excess20_pct": pct(mean(kept) - bmean),
        })
    return {
        "n_leave_one_out_runs": len(rows),
        "min_mean20_pct": min((r["mean20_pct"] for r in rows), default=None),
        "max_mean20_pct": max((r["mean20_pct"] for r in rows), default=None),
        "min_excess20_pct": min((r["excess20_pct"] for r in rows), default=None),
        "max_excess20_pct": max((r["excess20_pct"] for r in rows), default=None),
        "runs": rows,
    }


def main():
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    inst = raw["instruments"][SYMBOL]
    bars = base.load_bars(inst)
    feat = base.features(bars)
    labels = reg.compute_regimes(bars)
    sig = signal_indices(bars, feat, labels)
    bidx = baseline_indices(bars, labels)
    rows = event_rows(bars, feat, labels, sig)

    full = summarize_period(bars, sig, bidx)
    hold_sig = subset_by_dates(sig, bars, "2020-01-01")
    hold_base = baseline_indices(bars, labels, "2020-01-01")
    holdout = summarize_period(bars, hold_sig, hold_base)

    sig20 = [future_return(bars, i, 20) for i in sig]
    sig20 = [v for v in sig20 if v is not None]
    base20 = [future_return(bars, i, 20) for i in bidx]
    base20 = [v for v in base20 if v is not None]
    hold20 = [future_return(bars, i, 20) for i in hold_sig]
    hold20 = [v for v in hold20 if v is not None]
    holdbase20 = [future_return(bars, i, 20) for i in hold_base]
    holdbase20 = [v for v in holdbase20 if v is not None]

    rolling_windows = [
        ("1992_2001", "1992-01-02", "2001-12-31"),
        ("1997_2006", "1997-01-01", "2006-12-31"),
        ("2002_2011", "2002-01-01", "2011-12-31"),
        ("2007_2016", "2007-01-01", "2016-12-31"),
        ("2012_2021", "2012-01-01", "2021-12-31"),
        ("2017_latest", "2017-01-01", None),
    ]
    rolling = {}
    for name, start, end in rolling_windows:
        s = subset_by_dates(sig, bars, start, end)
        b = baseline_indices(bars, labels, start, end)
        rolling[name] = summarize_period(bars, s, b)

    blocks = [
        ("1992_1996", "1992-01-02", "1996-12-31"),
        ("1997_2001", "1997-01-01", "2001-12-31"),
        ("2002_2006", "2002-01-01", "2006-12-31"),
        ("2007_2011", "2007-01-01", "2011-12-31"),
        ("2012_2016", "2012-01-01", "2016-12-31"),
        ("2017_2021", "2017-01-01", "2021-12-31"),
        ("2022_latest", "2022-01-01", None),
    ]
    nonoverlap = {}
    for name, start, end in blocks:
        s = subset_by_dates(sig, bars, start, end)
        b = baseline_indices(bars, labels, start, end)
        nonoverlap[name] = summarize_period(bars, s, b)

    out = {
        "schema": "SPX-UPDOWN-DIVERGENCE-FINAL-VALIDATION-V1",
        "method": {
            "symbol": SYMBOL,
            "signal": "bull/negative divergence <= -1.5 sigma + corr>=0.25 + positive ratio-leading corr>=0.25",
            "regime_gate": "NOT_HIGH_VOL: trailing 20d realized-vol percentile <70% using trailing 252 sessions",
            "cooldown_trading_days": base.COOLDOWN,
            "parameters_frozen": True,
            "no_re_tuning_in_this_study": True,
            "bootstrap": f"event-level bootstrap, {BOOT_N} resamples, fixed seed; baseline mean treated as reference population",
            "rolling_windows": "fixed-rule stability diagnostics only; overlapping windows are not independent OOS folds",
            "holdout_2020_plus": "same frozen rule evaluated from 2020-01-01 onward",
        },
        "event_count": len(sig),
        "events": rows,
        "path_summary_0_40": path_summary(rows),
        "full_1992_plus": full,
        "holdout_2020_plus": holdout,
        "bootstrap_20d_full": bootstrap_event_mean(sig20, mean(base20), BOOT_N),
        "bootstrap_20d_2020_plus": bootstrap_event_mean(hold20, mean(holdbase20), BOOT_N) if hold20 else {"n": 0},
        "leave_one_out_20d": leave_one_out(bars, sig, bidx, 20),
        "rolling_10y_step5_stability": rolling,
        "nonoverlap_5y_blocks": nonoverlap,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print("SPX frozen signal events", len(sig), flush=True)
    print("Full 20d", full["forward"]["20"], flush=True)
    print("Bootstrap full", out["bootstrap_20d_full"], flush=True)
    print("2020+ 20d", holdout["forward"]["20"], flush=True)
    print("Bootstrap 2020+", out["bootstrap_20d_2020_plus"], flush=True)
    print("LOO", {k:v for k,v in out["leave_one_out_20d"].items() if k != "runs"}, flush=True)
    for name, r in rolling.items():
        h = r["forward"]["20"]
        print("ROLL", name, "n", r["signal_events"], "avg", h["signal"].get("avg_return_pct"), "excess", h.get("excess_avg_return_pct"), "up", h["signal"].get("up_rate_pct"), flush=True)
    print("Wrote", OUT_PATH, flush=True)


if __name__ == "__main__":
    main()
