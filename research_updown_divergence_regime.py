"""Post-2020 regime decomposition for the locked bullish up/down-divergence signal.

This study does NOT re-tune the signal. It loads the threshold selected strictly from
1992-2009 in updown_divergence_oos.json and asks where the signal has or has not
worked since 2020.

Regimes are computed using only information available at each date:
- Trend: close above/below SMA200.
- Volatility: 20d realized vol percentile versus trailing 252 sessions
  (LOW <=30%, MID 30-70%, HIGH >=70%).
- Drawdown: close versus trailing 60d high
  (SHALLOW > -5%, MEDIUM -5% to -10%, DEEP <= -10%).

Each signal bucket is compared with the unconditional set of all 2020+ market days
in the SAME regime, so excess return is regime-adjusted rather than compared with
an overall market average.
"""
from __future__ import annotations

import json, math
from pathlib import Path
from statistics import mean, median, pstdev

import research_updown_divergence_events as base

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "docs/data/structure_lab.json"
OOS_PATH = ROOT / "docs/data/updown_divergence_oos.json"
OUT_PATH = ROOT / "docs/data/updown_divergence_regime.json"
START = "2020-01-01"
HORIZONS = base.HORIZONS


def finite(x):
    try:
        return x is not None and math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def quantile_rank(values, x):
    vals = [float(v) for v in values if finite(v)]
    if not vals:
        return None
    return sum(v <= x for v in vals) / len(vals)


def compute_regimes(bars):
    n = len(bars)
    close = [b["close"] for b in bars]
    logret = [None] * n
    rv20 = [None] * n
    vol_pct = [None] * n
    sma200 = [None] * n
    dd60 = [None] * n
    trend = [None] * n
    vol_regime = [None] * n
    dd_regime = [None] * n

    for i in range(1, n):
        if close[i] > 0 and close[i - 1] > 0:
            logret[i] = math.log(close[i] / close[i - 1])

    for i in range(n):
        if i >= 19:
            w = [x for x in logret[i - 19 : i + 1] if finite(x)]
            if len(w) >= 15:
                rv20[i] = pstdev(w) * math.sqrt(252)
        if i >= 199:
            sma200[i] = mean(close[i - 199 : i + 1])
            trend[i] = "ABOVE_MA200" if close[i] >= sma200[i] else "BELOW_MA200"
        if i >= 59:
            hi = max(close[i - 59 : i + 1])
            dd60[i] = close[i] / hi - 1 if hi > 0 else None
            if finite(dd60[i]):
                if dd60[i] > -0.05:
                    dd_regime[i] = "SHALLOW_GT_-5PCT"
                elif dd60[i] > -0.10:
                    dd_regime[i] = "MEDIUM_-5_TO_-10PCT"
                else:
                    dd_regime[i] = "DEEP_LE_-10PCT"

        if finite(rv20[i]):
            a = max(0, i - 251)
            hist = [v for v in rv20[a : i + 1] if finite(v)]
            if len(hist) >= 60:
                vol_pct[i] = quantile_rank(hist, rv20[i])
                if vol_pct[i] <= 0.30:
                    vol_regime[i] = "LOW_LE_30PCT"
                elif vol_pct[i] >= 0.70:
                    vol_regime[i] = "HIGH_GE_70PCT"
                else:
                    vol_regime[i] = "MID_30_TO_70PCT"

    return {
        "sma200": sma200,
        "rv20": rv20,
        "vol_pct": vol_pct,
        "dd60": dd60,
        "trend": trend,
        "vol": vol_regime,
        "drawdown": dd_regime,
    }


def stats_for_indices(bars, indices, h):
    vals = []
    adverse = []
    favorable = []
    for i in indices:
        if i + h >= len(bars):
            continue
        base_px = bars[i]["close"]
        path = bars[i + 1 : i + h + 1]
        vals.append(bars[i + h]["close"] / base_px - 1)
        adverse.append(min(b["low"] for b in path) / base_px - 1)
        favorable.append(max(b["high"] for b in path) / base_px - 1)
    if not vals:
        return {"n": 0}
    return {
        "n": len(vals),
        "avg_return_pct": round(mean(vals) * 100, 3),
        "median_return_pct": round(median(vals) * 100, 3),
        "up_rate_pct": round(sum(v > 0 for v in vals) / len(vals) * 100, 2),
        "avg_adverse_excursion_pct": round(mean(adverse) * 100, 3),
        "avg_favorable_excursion_pct": round(mean(favorable) * 100, 3),
    }


def summarize_bucket(bars, signal_idx, baseline_idx):
    out = {}
    for h in HORIZONS:
        s = stats_for_indices(bars, signal_idx, h)
        b = stats_for_indices(bars, baseline_idx, h)
        row = {"signal": s, "regime_baseline": b}
        if s.get("n", 0) and b.get("n", 0):
            row["excess_avg_return_pct"] = round(s["avg_return_pct"] - b["avg_return_pct"], 3)
            row["excess_up_rate_pp"] = round(s["up_rate_pct"] - b["up_rate_pct"], 2)
        out[str(h)] = row
    return out


def group_indices(indices, labels, key_fn):
    out = {}
    for i in indices:
        key = key_fn(i, labels)
        if key is None or "None" in key:
            continue
        out.setdefault(key, []).append(i)
    return out


def eligible_market_indices(bars, labels):
    return [
        i for i, b in enumerate(bars)
        if b["date"] >= START
        and labels["trend"][i] is not None
        and labels["vol"][i] is not None
        and labels["drawdown"][i] is not None
    ]


def bucket_study(bars, signal_idx, market_idx, labels, key_fn):
    sg = group_indices(signal_idx, labels, key_fn)
    bg = group_indices(market_idx, labels, key_fn)
    keys = sorted(set(sg) | set(bg))
    return {
        k: {
            "signal_events": len(sg.get(k, [])),
            "baseline_days": len(bg.get(k, [])),
            "forward": summarize_bucket(bars, sg.get(k, []), bg.get(k, [])),
        }
        for k in keys
    }


def main():
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    oos = json.loads(OOS_PATH.read_text(encoding="utf-8"))
    out = {
        "schema": "UPDOWN-DIVERGENCE-REGIME-V1",
        "method": {
            "start": START,
            "signal": "locked bullish divergence signal from strict OOS V2; no re-tuning",
            "trend": "close >= SMA200 vs below SMA200",
            "volatility": "20d realized-vol percentile using trailing 252 sessions: low<=30%, mid 30-70%, high>=70%",
            "drawdown": "close vs trailing 60d high: shallow>-5%, medium -5% to -10%, deep<=-10%",
            "baseline": "all 2020+ days in the same regime bucket",
            "lookahead": "none in signal or regime construction; future returns only for evaluation",
        },
        "results": {},
    }

    for sym in base.SYMBOLS:
        inst = raw.get("instruments", {}).get(sym)
        if not inst:
            out["results"][sym] = {"error": "missing instrument"}
            continue
        selected = oos.get("results", {}).get(sym, {}).get("selected_threshold_from_IS")
        bars = base.load_bars(inst)
        feat = base.features(bars)
        labels = compute_regimes(bars)
        market_idx = eligible_market_indices(bars, labels)

        if selected is None:
            out["results"][sym] = {
                "name": inst.get("name", sym),
                "selected_threshold_from_pre2020": None,
                "formal_regime_test": False,
                "reason": "No positive edge survived the 1992-2009 training selection rule, so no threshold was locked for formal OOS regime testing.",
            }
            print(sym, "SKIP formal regime test: no locked threshold", flush=True)
            continue

        signal_idx = base.extract_events(
            bars,
            feat,
            side="bull",
            threshold=float(selected),
            require_corr=True,
            require_lead=True,
            start_date=START,
        )
        signal_idx = [i for i in signal_idx if i in set(market_idx)]

        result = {
            "name": inst.get("name", sym),
            "selected_threshold_from_pre2020": selected,
            "formal_regime_test": True,
            "post2020_signal_events": len(signal_idx),
            "post2020_eligible_market_days": len(market_idx),
            "overall": summarize_bucket(bars, signal_idx, market_idx),
            "trend": bucket_study(bars, signal_idx, market_idx, labels, lambda i, L: L["trend"][i]),
            "volatility": bucket_study(bars, signal_idx, market_idx, labels, lambda i, L: L["vol"][i]),
            "drawdown": bucket_study(bars, signal_idx, market_idx, labels, lambda i, L: L["drawdown"][i]),
            "trend_x_volatility": bucket_study(bars, signal_idx, market_idx, labels, lambda i, L: f'{L["trend"][i]}|{L["vol"][i]}'),
            "trend_x_drawdown": bucket_study(bars, signal_idx, market_idx, labels, lambda i, L: f'{L["trend"][i]}|{L["drawdown"][i]}'),
            "volatility_x_drawdown": bucket_study(bars, signal_idx, market_idx, labels, lambda i, L: f'{L["vol"][i]}|{L["drawdown"][i]}'),
            "triple": bucket_study(bars, signal_idx, market_idx, labels, lambda i, L: f'{L["trend"][i]}|{L["vol"][i]}|{L["drawdown"][i]}'),
        }
        out["results"][sym] = result

        print("\n", sym, result["name"], "threshold", selected, "events", len(signal_idx), flush=True)
        for section in ("trend", "volatility", "drawdown"):
            print(" ", section, flush=True)
            for k, v in result[section].items():
                h20 = v["forward"]["20"]
                s = h20["signal"]
                print("   ", k, "n", v["signal_events"], "20d", s.get("avg_return_pct"), "excess", h20.get("excess_avg_return_pct"), "up", s.get("up_rate_pct"), flush=True)

    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Wrote", OUT_PATH, flush=True)


if __name__ == "__main__":
    main()
