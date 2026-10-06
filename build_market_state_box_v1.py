"""Build the joint Market State x Box mean-reversion research dataset.

Inputs:
- local Market Structure Lab OHLCV + point-in-time box detections
- Market Regime Lab reconstructed sentiment history
- Market Regime Lab reconstructed composite score history

The output is research-only. Historical sentiment/model scores are reconstructed
from currently available series and are not publication-time archives.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Iterable

import requests

ROOT = Path(__file__).resolve().parent
STRUCTURE = ROOT / "docs" / "data" / "structure_lab.json"
OUT = ROOT / "docs" / "data" / "market_state_box_v1.json"

SENTIMENT_URL = (
    "https://raw.githubusercontent.com/galbbb2772/market-indicators-v1/"
    "main/docs/data/sentiment_history.json"
)
REGIME_URL = (
    "https://raw.githubusercontent.com/galbbb2772/market-indicators-v1/"
    "main/docs/data/current.json"
)

INDEXES = {
    "^GSPC": "sp500",
    "^IXIC": "nasdaq",
    "^DJI": "dow",
}
LOOKBACKS = (5, 10, 20, 60)
HORIZONS = (1, 3, 5, 10)


def fetch_json(url: str) -> dict:
    r = requests.get(url, timeout=30, headers={"User-Agent": "Market-State-Box-V1/1.0"})
    r.raise_for_status()
    return r.json()


def percentile_to_date(values: Iterable[float | None], min_n: int = 60) -> list[float | None]:
    """Expanding percentile using only values observed on/before each row."""
    seen: list[float] = []
    out: list[float | None] = []
    for value in values:
        if value is None or not math.isfinite(float(value)):
            out.append(None)
            continue
        v = float(value)
        seen.append(v)
        if len(seen) < min_n:
            out.append(None)
        else:
            out.append(round(100.0 * sum(x <= v for x in seen) / len(seen), 2))
    return out


def safe_mean(values: Iterable[float | None]) -> float | None:
    vals = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    return sum(vals) / len(vals) if vals else None


def zone(score: float | None) -> str | None:
    if score is None:
        return None
    if score < 45:
        return "red"
    if score < 55:
        return "yellow"
    if score < 65:
        return "blue"
    return "green"


def parse_bars(obj: dict) -> list[dict]:
    out = []
    for row in obj.get("bars") or []:
        if len(row) != 6:
            continue
        date, op, hi, lo, close, volume = row
        try:
            out.append({
                "date": str(date)[:10],
                "open": float(op),
                "high": float(hi),
                "low": float(lo),
                "close": float(close),
                "volume": float(volume or 0),
            })
        except (TypeError, ValueError):
            continue
    out.sort(key=lambda x: x["date"])
    return out


def updown_series(bars: list[dict], lookback: int) -> dict[str, dict]:
    """Rolling close-to-close up/down ratio and bounded balance."""
    signs: list[int] = [0]
    for i in range(1, len(bars)):
        d = bars[i]["close"] - bars[i - 1]["close"]
        signs.append(1 if d > 0 else -1 if d < 0 else 0)
    out = {}
    for i in range(len(bars)):
        if i < lookback:
            continue
        window = signs[i - lookback + 1:i + 1]
        up = sum(x > 0 for x in window)
        down = sum(x < 0 for x in window)
        denom = up + down
        ratio = (up / down) if down else None
        balance = ((up - down) / denom) if denom else None
        out[bars[i]["date"]] = {
            "up": up,
            "down": down,
            "ratio": round(ratio, 4) if ratio is not None else None,
            "balance": round(balance, 4) if balance is not None else None,
        }
    return out


def active_box_map(bars: list[dict], boxes: list[dict], scale: str) -> dict[str, dict]:
    """Map each date to the box known before that session; breakout day is excluded."""
    chosen = [b for b in boxes if b.get("scale") == scale and b.get("detected_at")]
    chosen.sort(key=lambda b: b["detected_at"])
    out = {}
    for bar in bars:
        date = bar["date"]
        eligible = []
        for box in chosen:
            detected = str(box.get("detected_at"))[:10]
            break_at = str(box.get("break_at"))[:10] if box.get("break_at") else None
            if date <= detected:
                continue
            if break_at and date >= break_at:
                continue
            try:
                lower = float(box["lower"])
                upper = float(box["upper"])
            except (KeyError, TypeError, ValueError):
                continue
            if upper <= lower:
                continue
            eligible.append((detected, box, lower, upper))
        if not eligible:
            continue
        _, box, lower, upper = eligible[-1]
        pos = (bar["close"] - lower) / (upper - lower)
        out[date] = {
            "id": box.get("id"),
            "detected_at": box.get("detected_at"),
            "lower": round(lower, 4),
            "upper": round(upper, 4),
            "position": round(pos, 4),
            "width_pct": box.get("width_pct"),
        }
    return out


def decluster(rows: list[dict], min_gap: int = 5) -> list[dict]:
    if not rows:
        return []
    out = []
    last_i = -10**9
    for row in rows:
        i = int(row["_i"])
        if i - last_i >= min_gap:
            out.append(row)
            last_i = i
    return out


def event_summary(rows: list[dict]) -> dict:
    rows = decluster(rows, 5)
    result = {"n": len(rows)}
    for h in HORIZONS:
        vals = [r.get(f"fwd_{h}d") for r in rows]
        vals = [float(v) for v in vals if v is not None]
        result[f"fwd_{h}d_avg_pct"] = round(mean(vals), 3) if vals else None
        result[f"fwd_{h}d_median_pct"] = round(median(vals), 3) if vals else None
        result[f"fwd_{h}d_positive_pct"] = round(100 * sum(v > 0 for v in vals) / len(vals), 1) if vals else None
    mfe = [float(r["mfe_10d"]) for r in rows if r.get("mfe_10d") is not None]
    mae = [float(r["mae_10d"]) for r in rows if r.get("mae_10d") is not None]
    result["mfe_10d_avg_pct"] = round(mean(mfe), 3) if mfe else None
    result["mae_10d_avg_pct"] = round(mean(mae), 3) if mae else None
    return result


def closest_analogs(rows: list[dict], latest: dict, limit: int = 20) -> list[dict]:
    features = (
        "box_position",
        "sentiment_stress_pct",
        "breadth_20d_pct",
        "market_score_pct",
        "market_score_d3",
    )
    scored = []
    latest_i = int(latest["_i"])
    for row in rows:
        if int(row["_i"]) >= latest_i - 10:
            continue
        diffs = []
        used = []
        for f in features:
            a, b = row.get(f), latest.get(f)
            if a is None or b is None:
                continue
            scale = 100.0 if f != "market_score_d3" else 20.0
            diffs.append(((float(a) - float(b)) / scale) ** 2)
            used.append(f)
        if len(diffs) < 4:
            continue
        dist = math.sqrt(sum(diffs) / len(diffs))
        scored.append((dist, row, used))
    scored.sort(key=lambda x: x[0])
    picked = []
    picked_i: list[int] = []
    for dist, row, used in scored:
        i = int(row["_i"])
        if any(abs(i - j) < 10 for j in picked_i):
            continue
        picked_i.append(i)
        picked.append({
            "date": row["date"],
            "distance": round(dist, 4),
            "features_used": used,
            "box_position": row.get("box_position"),
            "sentiment_stress_pct": row.get("sentiment_stress_pct"),
            "breadth_20d_pct": row.get("breadth_20d_pct"),
            "market_score": row.get("market_score"),
            "market_regime": row.get("market_regime"),
            **{f"fwd_{h}d": row.get(f"fwd_{h}d") for h in HORIZONS},
            "mfe_10d": row.get("mfe_10d"),
            "mae_10d": row.get("mae_10d"),
        })
        if len(picked) >= limit:
            break
    return picked


def main() -> None:
    structure = json.loads(STRUCTURE.read_text(encoding="utf-8"))
    sentiment = fetch_json(SENTIMENT_URL)
    regime = fetch_json(REGIME_URL)

    inst = structure.get("instruments") or {}
    if "^GSPC" not in inst:
        raise RuntimeError("S&P 500 history missing from structure_lab.json")

    bars_by_sym = {sym: parse_bars(inst.get(sym) or {}) for sym in INDEXES}
    spx = bars_by_sym["^GSPC"]
    if len(spx) < 300:
        raise RuntimeError("insufficient S&P 500 history")

    dates = [b["date"] for b in spx]
    close = {b["date"]: b["close"] for b in spx}

    box_maps = {
        "small": active_box_map(spx, inst["^GSPC"].get("boxes") or [], "small"),
        "large": active_box_map(spx, inst["^GSPC"].get("boxes") or [], "large"),
    }

    ud = {}
    for sym, bars in bars_by_sym.items():
        ud[sym] = {n: updown_series(bars, n) for n in LOOKBACKS}

    sentiment_map = {str(r.get("date"))[:10]: r for r in sentiment.get("daily") or [] if r.get("date")}
    score_history = ((regime.get("regime_backtest") or {}).get("history") or [])
    score_map = {
        str(r.get("date"))[:10]: float(r["score"])
        for r in score_history
        if r.get("date") and r.get("score") is not None
    }

    rows = []
    for i, date in enumerate(dates):
        row = {"_i": i, "date": date, "sp500_close": round(close[date], 4)}
        sb, lb = box_maps["small"].get(date), box_maps["large"].get(date)
        if sb:
            row["box_small"] = sb
            row["box_small_position"] = sb["position"]
        if lb:
            row["box_large"] = lb
            row["box_large_position"] = lb["position"]
        positions = [x for x in (row.get("box_small_position"), row.get("box_large_position")) if x is not None]
        row["box_position"] = round(min(positions), 4) if positions else None
        row["box_bottom"] = bool(positions and min(positions) <= 0.25)

        s = sentiment_map.get(date) or {}
        for k in ("optimism", "pessimism", "total_negative", "euphoria"):
            row[k] = float(s[k]) if s.get(k) is not None else None
        stress = safe_mean((row.get("pessimism"), row.get("total_negative"),
                            100.0 - row["euphoria"] if row.get("euphoria") is not None else None))
        row["sentiment_stress"] = round(stress, 3) if stress is not None else None

        for sym, key in INDEXES.items():
            point = ud.get(sym, {}).get(20, {}).get(date)
            if point:
                row[f"{key}_ud20_ratio"] = point["ratio"]
                row[f"{key}_ud20_balance"] = point["balance"]
        row["market_score"] = score_map.get(date)
        rows.append(row)

    # Point-in-time historical percentiles.
    for field, out_field in (
        ("sentiment_stress", "sentiment_stress_pct"),
        ("market_score", "market_score_pct"),
    ):
        p = percentile_to_date([r.get(field) for r in rows])
        for r, v in zip(rows, p):
            r[out_field] = v

    for sym, key in INDEXES.items():
        vals = [r.get(f"{key}_ud20_balance") for r in rows]
        p = percentile_to_date(vals)
        for r, v in zip(rows, p):
            r[f"{key}_ud20_pct"] = v

    for r in rows:
        breadth_pcts = [r.get(f"{key}_ud20_pct") for key in INDEXES.values()]
        breadth_mean = safe_mean(breadth_pcts)
        r["breadth_20d_pct"] = round(breadth_mean, 2) if breadth_mean is not None else None
        r["breadth_extreme_low"] = sum(
            1 for v in breadth_pcts if v is not None and float(v) <= 20
        ) >= 2
        r["sentiment_extreme"] = (
            r.get("sentiment_stress_pct") is not None and r["sentiment_stress_pct"] >= 80
        )
        r["market_regime"] = zone(r.get("market_score"))

    # Score deltas, forward returns, MFE / MAE.
    for i, r in enumerate(rows):
        score_now = r.get("market_score")
        for lag in (1, 3, 5):
            prev = rows[i - lag].get("market_score") if i >= lag else None
            r[f"market_score_d{lag}"] = (
                round(float(score_now) - float(prev), 3)
                if score_now is not None and prev is not None else None
            )
        r["score_recovering"] = bool(
            r.get("market_score_d1") is not None
            and r.get("market_score_d3") is not None
            and r["market_score_d1"] > 0
            and r["market_score_d3"] > 0
        )
        c0 = r["sp500_close"]
        for h in HORIZONS:
            if i + h < len(rows):
                r[f"fwd_{h}d"] = round((rows[i + h]["sp500_close"] / c0 - 1) * 100, 4)
            else:
                r[f"fwd_{h}d"] = None
        tail = rows[i + 1:min(len(rows), i + 11)]
        if tail:
            closes = [x["sp500_close"] for x in tail]
            r["mfe_10d"] = round((max(closes) / c0 - 1) * 100, 4)
            r["mae_10d"] = round((min(closes) / c0 - 1) * 100, 4)
        else:
            r["mfe_10d"] = r["mae_10d"] = None
        r["joint_4way"] = bool(
            r["box_bottom"] and r["sentiment_extreme"]
            and r["breadth_extreme_low"] and r["score_recovering"]
        )

    valid_rows = [
        r for r in rows
        if r.get("sentiment_stress_pct") is not None
        and r.get("breadth_20d_pct") is not None
        and r.get("market_score") is not None
    ]
    if not valid_rows:
        raise RuntimeError("no overlapping market-state observations")

    definitions = {
        "baseline": lambda r: True,
        "box_only": lambda r: r["box_bottom"],
        "box_sentiment": lambda r: r["box_bottom"] and r["sentiment_extreme"],
        "box_breadth": lambda r: r["box_bottom"] and r["breadth_extreme_low"],
        "box_score_recovery": lambda r: r["box_bottom"] and r["score_recovering"],
        "box_sentiment_breadth": lambda r: r["box_bottom"] and r["sentiment_extreme"] and r["breadth_extreme_low"],
        "box_sentiment_score": lambda r: r["box_bottom"] and r["sentiment_extreme"] and r["score_recovering"],
        "box_breadth_score": lambda r: r["box_bottom"] and r["breadth_extreme_low"] and r["score_recovering"],
        "all_four": lambda r: r["box_bottom"] and r["sentiment_extreme"] and r["breadth_extreme_low"] and r["score_recovering"],
    }
    ablation = {
        name: event_summary([r for r in valid_rows if fn(r)])
        for name, fn in definitions.items()
    }

    # Heatmap: x=breadth percentile decile, y=sentiment stress percentile decile.
    heatmap = {}
    for box_filter in ("all", "box_bottom"):
        for reg_filter in ("all", "red", "yellow", "blue", "green"):
            cells = {}
            subset = valid_rows
            if box_filter == "box_bottom":
                subset = [r for r in subset if r["box_bottom"]]
            if reg_filter != "all":
                subset = [r for r in subset if r.get("market_regime") == reg_filter]
            for r in subset:
                if r.get("fwd_5d") is None:
                    continue
                x = min(9, max(0, int(float(r["breadth_20d_pct"]) // 10)))
                y = min(9, max(0, int(float(r["sentiment_stress_pct"]) // 10)))
                cells.setdefault(f"{x},{y}", []).append(float(r["fwd_5d"]))
            heatmap[f"{box_filter}|{reg_filter}"] = {
                k: {
                    "n": len(v),
                    "avg_fwd_5d_pct": round(mean(v), 3),
                    "median_fwd_5d_pct": round(median(v), 3),
                    "positive_pct": round(100 * sum(x > 0 for x in v) / len(v), 1),
                }
                for k, v in cells.items()
            }

    latest_candidates = [
        r for r in valid_rows
        if r.get("box_position") is not None and r.get("market_score_d3") is not None
    ]
    latest = latest_candidates[-1] if latest_candidates else valid_rows[-1]
    analogs = closest_analogs(valid_rows, latest)

    public_rows = []
    for r in valid_rows:
        x = dict(r)
        x.pop("_i", None)
        public_rows.append(x)

    structure_latest = dates[-1] if dates else None
    sentiment_latest = max(sentiment_map) if sentiment_map else None
    market_score_latest = max(score_map) if score_map else None
    output_latest = public_rows[-1]["date"] if public_rows else None
    source_latest = {
        "structure_sp500": structure_latest,
        "sentiment_history": sentiment_latest,
        "market_score_history": market_score_latest,
    }
    blockers = [
        name for name, d in source_latest.items()
        if d is not None and structure_latest is not None and d < structure_latest
    ]

    payload = {
        "schema": "MARKET-STATE-BOX-V1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "upstream_freshness": {
            "source_latest_dates": source_latest,
            "joint_output_latest_date": output_latest,
            "blocked_by": blockers,
            "all_sources_at_structure_latest": not blockers and output_latest == structure_latest,
        },
        "warnings": [
            "Sentiment and composite market-score history are reconstructed and are not fully publication-time point-in-time archives.",
            "Box eligibility is next-session-only after detected_at; breakout day is excluded.",
            "Ablation event samples are de-clustered by at least 5 trading sessions; results are descriptive, not forecasts.",
        ],
        "definitions": {
            "box_bottom": "minimum eligible S&P 500 20D/60D box position <= 0.25",
            "sentiment_extreme": "expanding historical percentile of sentiment_stress >= 80",
            "breadth_extreme_low": "at least 2 of S&P 500/Nasdaq/Dow 20D up-down balance percentiles <= 20",
            "score_recovering": "Market Model V2 score D1 > 0 and D3 > 0",
            "sentiment_stress": "mean(pessimism, total_negative, 100-euphoria)",
            "breadth_20d_pct": "mean of the three indexes' point-in-time expanding percentiles of 20D up-down balance",
            "market_score_regime": {"red": "<45", "yellow": "45-54.99", "blue": "55-64.99", "green": ">=65"},
        },
        "coverage": {
            "start": public_rows[0]["date"] if public_rows else None,
            "end": public_rows[-1]["date"] if public_rows else None,
            "observations": len(public_rows),
        },
        "latest": {k: v for k, v in latest.items() if k != "_i"},
        "ablation": ablation,
        "similar_days": analogs,
        "heatmap": heatmap,
        "daily": public_rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(
        "wrote", OUT,
        "rows", len(public_rows),
        "latest", payload["latest"].get("date"),
        "all_four_n", ablation["all_four"]["n"],
    )


if __name__ == "__main__":
    main()

# CI trigger: refresh latest market state for Task 1/4 stock bridge
