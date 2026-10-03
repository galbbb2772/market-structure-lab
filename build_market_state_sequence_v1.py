"""Market State Sequence V1.

Research-only ordered-state study:
DUAL_DRAIN -> weak breadth -> box-bottom -> breadth rebound -> Market Score recovery.

No production strategy is changed. Thresholds reused here were preregistered in
research/market_state_sequence_v1/PREREGISTRATION.md before this builder.
"""
from __future__ import annotations

import json
import math
import time
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from statistics import mean, median

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "docs/data/market_state_box_v1.json"
OUT = ROOT / "docs/data/market_state_sequence_v1.json"

HORIZONS = (1, 3, 5, 10)
BREADTH_LOW = 20.0
BOX_BOTTOM = 0.25
RECENT_DUAL = 10
PATH_WINDOW = 20
DECLUSTER = 5

FRED = {
    "walcl": ("WALCL", 1),
    "tga": ("WTREGEN", 1),
    "rrp": ("RRPONTSYD", 0),
    "reserves": ("WRESBAL", 1),
}

SEQUENCE_FLAGS = (
    "D_TO_BREADTH_LOW",
    "D_TO_BREADTH_REBOUND",
    "D_TO_BOX_BOTTOM",
    "D_TO_REBOUND_SCORE",
    "D_TO_BOTH_REBOUND_SCORE",
)


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def quantile(values, p):
    a = sorted(v for v in (num(x) for x in values) if v is not None)
    if not a:
        return None
    z = (len(a) - 1) * p
    i = int(z)
    j = min(i + 1, len(a) - 1)
    f = z - i
    return a[i] + (a[j] - a[i]) * f


def fetch_fred(series_id: str, name: str, lag_days: int) -> pd.DataFrame:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    err = None
    for attempt in range(5):
        try:
            r = requests.get(url, timeout=45)
            r.raise_for_status()
            x = pd.read_csv(StringIO(r.text))
            x.columns = ["observation_date", name]
            x["observation_date"] = pd.to_datetime(x["observation_date"], errors="coerce").astype("datetime64[ns]")
            x[name] = pd.to_numeric(x[name], errors="coerce")
            x = x.dropna().sort_values("observation_date").reset_index(drop=True)
            x["available_date"] = (x["observation_date"] + pd.to_timedelta(lag_days, unit="D")).astype("datetime64[ns]")
            return x[["available_date", name]]
        except Exception as e:  # pragma: no cover - network retry
            err = e
            time.sleep(2**attempt)
    raise RuntimeError(f"FRED fetch failed for {series_id}: {err}")


def build_dual_panel(start: str, end: str) -> pd.DataFrame:
    raw = {k: fetch_fred(v[0], k, v[1]) for k, v in FRED.items()}
    cal = pd.DataFrame({"date": pd.date_range(pd.Timestamp(start) - pd.Timedelta(days=90), pd.Timestamp(end), freq="D")})
    cal["date"] = cal["date"].astype("datetime64[ns]")
    for name, df in raw.items():
        cal = pd.merge_asof(
            cal.sort_values("date"),
            df.sort_values("available_date"),
            left_on="date",
            right_on="available_date",
            direction="backward",
        ).drop(columns=["available_date"])
    # FRED units: WALCL/WTREGEN/WRESBAL are millions USD; RRPONTSYD is billions USD.
    cal["rrp_m"] = cal["rrp"] * 1000.0
    cal["net_liq_m"] = cal["walcl"] - cal["tga"] - cal["rrp_m"]
    cal["net_liq_4w_pct"] = cal["net_liq_m"] / cal["net_liq_m"].shift(28) - 1.0
    cal["reserves_4w_pct"] = cal["reserves"] / cal["reserves"].shift(28) - 1.0
    cal["dual_drain"] = (cal["net_liq_4w_pct"] <= -0.02) & (cal["reserves_4w_pct"] <= -0.02)
    # Conservative timing: state observed on calendar date d may affect market date d+1 only.
    cal["market_date"] = (cal["date"] + pd.Timedelta(days=1)).astype("datetime64[ns]")
    return cal[["market_date", "net_liq_4w_pct", "reserves_4w_pct", "dual_drain"]]


def add_dual(rows: list[dict]) -> list[dict]:
    dates = pd.DataFrame({"market_date": pd.to_datetime([r["date"] for r in rows]).astype("datetime64[ns]")})
    panel = build_dual_panel(rows[0]["date"], rows[-1]["date"])
    z = pd.merge_asof(
        dates.sort_values("market_date"),
        panel.sort_values("market_date"),
        on="market_date",
        direction="backward",
        allow_exact_matches=True,
    )
    out = []
    for i, r in enumerate(rows):
        q = dict(r)
        q["_i"] = i
        q["dual_drain"] = bool(z.iloc[i]["dual_drain"]) if pd.notna(z.iloc[i]["dual_drain"]) else False
        q["net_liq_4w_pct"] = None if pd.isna(z.iloc[i]["net_liq_4w_pct"]) else round(float(z.iloc[i]["net_liq_4w_pct"]) * 100.0, 3)
        q["reserves_4w_pct"] = None if pd.isna(z.iloc[i]["reserves_4w_pct"]) else round(float(z.iloc[i]["reserves_4w_pct"]) * 100.0, 3)
        out.append(q)
    return out


def enrich_sequence(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    episode_id = 0
    active_start = None
    active_day = 0
    last_dual_idx = None
    last_episode_start = None
    episodes = []
    current_episode = None

    for i, r in enumerate(rows):
        dual = bool(r.get("dual_drain"))
        if dual:
            if i == 0 or not bool(rows[i - 1].get("dual_drain")):
                episode_id += 1
                active_start = i
                active_day = 1
                last_episode_start = i
                current_episode = {"episode_id": episode_id, "start_i": i, "end_i": i}
                episodes.append(current_episode)
            else:
                active_day += 1
                current_episode["end_i"] = i
            last_dual_idx = i
            r["dual_episode_id"] = episode_id
            r["dual_episode_day"] = active_day
            r["days_since_dual"] = 0
            if active_day == 1:
                phase = "active_d1"
            elif active_day <= 3:
                phase = "active_d2_3"
            elif active_day <= 10:
                phase = "active_d4_10"
            else:
                phase = "active_d11plus"
        else:
            r["dual_episode_id"] = None
            r["dual_episode_day"] = None
            ds = None if last_dual_idx is None else i - last_dual_idx
            r["days_since_dual"] = ds
            if ds is None or ds > 20:
                phase = "no_recent_dual"
            elif ds <= 3:
                phase = "post_d1_3"
            elif ds <= 10:
                phase = "post_d4_10"
            else:
                phase = "post_d11_20"
        r["dual_phase"] = phase

        # Anchor is the start of the current / most recent DUAL episode, while <=20 sessions away.
        anchor = None
        if dual:
            anchor = active_start
        elif last_dual_idx is not None and i - last_dual_idx <= PATH_WINDOW:
            anchor = last_episode_start
        r["dual_anchor_i"] = anchor
        r["recent_dual_10d"] = bool(dual or (last_dual_idx is not None and i - last_dual_idx <= RECENT_DUAL))

        br = num(r.get("breadth_20d_pct"))
        prev_br = num(rows[i - 1].get("breadth_20d_pct")) if i else None
        box = num(r.get("box_position"))
        score_d1 = num(r.get("market_score_d1"))
        score_d3 = num(r.get("market_score_d3"))
        score_recovery = score_d1 is not None and score_d3 is not None and score_d1 > 0 and score_d3 > 0
        r["score_recovery_confirmed"] = score_recovery

        if anchor is None:
            low_idx = None
            low_val = None
            box_idx = None
        else:
            span = rows[anchor : i + 1]
            br_pairs = [(anchor + j, num(x.get("breadth_20d_pct"))) for j, x in enumerate(span)]
            br_pairs = [(j, v) for j, v in br_pairs if v is not None]
            low_idx, low_val = min(br_pairs, key=lambda x: x[1]) if br_pairs else (None, None)
            box_idx = next((anchor + j for j, x in enumerate(span) if num(x.get("box_position")) is not None and num(x.get("box_position")) <= BOX_BOTTOM), None)

        r["breadth_trough_since_dual"] = None if low_val is None else round(low_val, 3)
        r["breadth_trough_i"] = low_idx
        r["box_bottom_i_since_dual"] = box_idx
        r["breadth_low_since_dual"] = bool(low_val is not None and low_val <= BREADTH_LOW)
        r["box_bottom_since_dual"] = box_idx is not None
        r["breadth_improving"] = bool(br is not None and prev_br is not None and br > prev_br)
        r["breadth_rebound_since_dual"] = bool(
            br is not None and low_val is not None and low_idx is not None and i > low_idx and br > low_val and r["breadth_improving"]
        )

        recent = r["recent_dual_10d"]
        r["D_TO_BREADTH_LOW"] = bool(recent and r["breadth_low_since_dual"])
        r["D_TO_BREADTH_REBOUND"] = bool(r["D_TO_BREADTH_LOW"] and r["breadth_rebound_since_dual"])
        r["D_TO_BOX_BOTTOM"] = bool(recent and r["box_bottom_since_dual"])
        r["D_TO_REBOUND_SCORE"] = bool(r["D_TO_BREADTH_REBOUND"] and score_recovery)
        r["D_TO_BOTH_REBOUND_SCORE"] = bool(r["D_TO_REBOUND_SCORE"] and r["box_bottom_since_dual"])

    # Descriptive episode-path diagnostics; these are not predictive labels.
    diag = []
    for ep in episodes:
        s, e = ep["start_i"], ep["end_i"]
        stop = min(len(rows) - 1, e + PATH_WINDOW)
        window = rows[s : stop + 1]
        first_low = next((s + j for j, r in enumerate(window) if num(r.get("breadth_20d_pct")) is not None and num(r.get("breadth_20d_pct")) <= BREADTH_LOW), None)
        first_box = next((s + j for j, r in enumerate(window) if num(r.get("box_position")) is not None and num(r.get("box_position")) <= BOX_BOTTOM), None)
        first_rebound = None
        if first_low is not None:
            low_val = num(rows[first_low].get("breadth_20d_pct"))
            for j in range(first_low + 1, stop + 1):
                b = num(rows[j].get("breadth_20d_pct")); p = num(rows[j - 1].get("breadth_20d_pct"))
                if b is not None and p is not None and low_val is not None and b > low_val and b > p:
                    first_rebound = j; break
        first_score = None
        if first_rebound is not None:
            for j in range(first_rebound, stop + 1):
                d1 = num(rows[j].get("market_score_d1")); d3 = num(rows[j].get("market_score_d3"))
                if d1 is not None and d3 is not None and d1 > 0 and d3 > 0:
                    first_score = j; break
        diag.append({
            "episode_id": ep["episode_id"],
            "start": rows[s]["date"],
            "end": rows[e]["date"],
            "trading_days": e - s + 1,
            "first_breadth_low": None if first_low is None else rows[first_low]["date"],
            "breadth_low_lag_from_start": None if first_low is None else first_low - s,
            "first_box_bottom": None if first_box is None else rows[first_box]["date"],
            "box_bottom_lag_from_start": None if first_box is None else first_box - s,
            "first_breadth_rebound": None if first_rebound is None else rows[first_rebound]["date"],
            "rebound_lag_from_start": None if first_rebound is None else first_rebound - s,
            "first_score_recovery_after_rebound": None if first_score is None else rows[first_score]["date"],
            "score_recovery_lag_from_start": None if first_score is None else first_score - s,
        })
    return rows, diag


def outcome_stats(sample: list[dict], baseline: list[dict]) -> dict:
    out = {"n_dates": len(sample)}
    for h in HORIZONS:
        key = f"fwd_{h}d"
        a = [num(r.get(key)) for r in sample]
        a = [x for x in a if x is not None]
        b = [num(r.get(key)) for r in baseline]
        b = [x for x in b if x is not None]
        if not a:
            out[f"{h}d"] = {"n": 0}
            continue
        base_mean = mean(b) if b else None
        out[f"{h}d"] = {
            "n": len(a),
            "mean_pct": round(mean(a), 4),
            "median_pct": round(median(a), 4),
            "positive_pct": round(100.0 * sum(x > 0 for x in a) / len(a), 2),
            "p10_pct": round(quantile(a, 0.10), 4),
            "p90_pct": round(quantile(a, 0.90), 4),
            "baseline_mean_pct": None if base_mean is None else round(base_mean, 4),
            "mean_lift_vs_baseline_pp": None if base_mean is None else round(mean(a) - base_mean, 4),
        }
    mfe = [num(r.get("mfe_10d")) for r in sample]; mfe = [x for x in mfe if x is not None]
    mae = [num(r.get("mae_10d")) for r in sample]; mae = [x for x in mae if x is not None]
    out["mfe_10d_mean_pct"] = None if not mfe else round(mean(mfe), 4)
    out["mae_10d_mean_pct"] = None if not mae else round(mean(mae), 4)
    return out


def event_onsets(rows: list[dict], flag: str) -> list[dict]:
    candidates = []
    prev = False
    for i, r in enumerate(rows):
        cur = bool(r.get(flag))
        if cur and not prev:
            candidates.append(i)
        prev = cur
    keep = []
    last = -10_000
    for i in candidates:
        if i - last >= DECLUSTER:
            keep.append(rows[i]); last = i
    return keep


def segment(rows: list[dict], name: str) -> list[dict]:
    if name == "full": return rows
    if name == "pre_2022": return [r for r in rows if r["date"] < "2022-01-01"]
    if name == "post_2022": return [r for r in rows if r["date"] >= "2022-01-01"]
    if name == "recent_2024": return [r for r in rows if r["date"] >= "2024-01-01"]
    raise KeyError(name)


def lag_summary(diag: list[dict], key: str) -> dict:
    a = [d.get(key) for d in diag if d.get(key) is not None]
    return {
        "n": len(a),
        "share_of_episodes_pct": round(100.0 * len(a) / len(diag), 2) if diag else None,
        "median_trading_days": None if not a else round(median(a), 2),
        "p25_trading_days": None if not a else round(quantile(a, 0.25), 2),
        "p75_trading_days": None if not a else round(quantile(a, 0.75), 2),
    }


def main():
    src = json.loads(SRC.read_text(encoding="utf-8"))
    rows = [dict(r) for r in (src.get("daily") or [])]
    if len(rows) < 1000:
        raise RuntimeError("Market State Box V1 daily table is missing or too short")
    rows = add_dual(rows)
    rows, episodes = enrich_sequence(rows)

    usable = [r for r in rows if num(r.get("fwd_10d")) is not None]
    segments = ("full", "pre_2022", "post_2022", "recent_2024")
    phase_names = (
        "active_d1", "active_d2_3", "active_d4_10", "active_d11plus",
        "post_d1_3", "post_d4_10", "post_d11_20", "no_recent_dual",
    )

    phase_stats = {}
    sequence_stats = {}
    for seg_name in segments:
        base = segment(usable, seg_name)
        phase_stats[seg_name] = {
            p: outcome_stats([r for r in base if r.get("dual_phase") == p], base)
            for p in phase_names
        }
        sequence_stats[seg_name] = {}
        for flag in SEQUENCE_FLAGS:
            onsets = [r for r in event_onsets(rows, flag) if r in segment(rows, seg_name) and num(r.get("fwd_10d")) is not None]
            sequence_stats[seg_name][flag] = outcome_stats(onsets, base)

    latest = rows[-1]
    recent = []
    for r in rows[-160:]:
        recent.append({
            "date": r["date"],
            "dual_drain": r.get("dual_drain"),
            "dual_phase": r.get("dual_phase"),
            "days_since_dual": r.get("days_since_dual"),
            "breadth_20d_pct": r.get("breadth_20d_pct"),
            "box_position": r.get("box_position"),
            "market_score": r.get("market_score"),
            "market_score_d1": r.get("market_score_d1"),
            "market_score_d3": r.get("market_score_d3"),
            **{f: bool(r.get(f)) for f in SEQUENCE_FLAGS},
        })

    out = {
        "schema": "MARKET-STATE-SEQUENCE-V1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "preregistered": True,
        "coverage": {"start": rows[0]["date"], "end": rows[-1]["date"], "observations": len(rows), "usable_10d": len(usable)},
        "frozen_definitions": {
            "dual_drain": "net liquidity 4w <= -2% AND reserve balances 4w <= -2%",
            "breadth_low_pct": BREADTH_LOW,
            "box_bottom_position": BOX_BOTTOM,
            "score_recovery": "market_score_d1 > 0 AND market_score_d3 > 0",
            "recent_dual_sessions": RECENT_DUAL,
            "path_window_sessions": PATH_WINDOW,
            "event_decluster_sessions": DECLUSTER,
        },
        "warnings": [
            "FRED current-history retrieval may contain revisions; this is not ALFRED vintage macro data.",
            "Sentiment / Market Score source history inherits Market State Box V1 reconstruction caveats.",
            "Episode milestone lags are descriptive path diagnostics and must not be treated as ex-ante prediction labels.",
            "No threshold or weight optimization is performed in V1.",
        ],
        "latest": {
            "date": latest["date"],
            "dual_drain": latest.get("dual_drain"),
            "dual_phase": latest.get("dual_phase"),
            "dual_episode_day": latest.get("dual_episode_day"),
            "days_since_dual": latest.get("days_since_dual"),
            "net_liq_4w_pct": latest.get("net_liq_4w_pct"),
            "reserves_4w_pct": latest.get("reserves_4w_pct"),
            "breadth_20d_pct": latest.get("breadth_20d_pct"),
            "breadth_trough_since_dual": latest.get("breadth_trough_since_dual"),
            "breadth_improving": latest.get("breadth_improving"),
            "box_position": latest.get("box_position"),
            "market_score": latest.get("market_score"),
            "market_score_d1": latest.get("market_score_d1"),
            "market_score_d3": latest.get("market_score_d3"),
            **{f: bool(latest.get(f)) for f in SEQUENCE_FLAGS},
        },
        "dual_episode_path_summary": {
            "episodes": len(episodes),
            "episode_length_median_sessions": None if not episodes else round(median([x["trading_days"] for x in episodes]), 2),
            "breadth_low": lag_summary(episodes, "breadth_low_lag_from_start"),
            "box_bottom": lag_summary(episodes, "box_bottom_lag_from_start"),
            "breadth_rebound": lag_summary(episodes, "rebound_lag_from_start"),
            "score_recovery_after_rebound": lag_summary(episodes, "score_recovery_lag_from_start"),
        },
        "phase_stats": phase_stats,
        "sequence_onset_stats": sequence_stats,
        "episode_examples_tail": episodes[-20:],
        "recent_daily": recent,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Wrote", OUT)
    print(json.dumps({"coverage": out["coverage"], "latest": out["latest"], "episode_summary": out["dual_episode_path_summary"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
