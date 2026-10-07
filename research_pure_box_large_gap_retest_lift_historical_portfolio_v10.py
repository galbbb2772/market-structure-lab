#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ENTRY_COST = 0.0005
EXIT_COST = 0.0005
ALLOC = 0.10
MAX_HOLD = 20
TARGETS = (0.60, 0.80)
CAPS = (300, 500)
METHODS = ("EXPANDING", "FIXED_-1PCT")
STATES = ("RETEST_LIFT", "NO_RETEST_LIFT", "EXTREME_ALL")
FRESH = {300: 23, 500: 24}
START = "2021-01-01"
END = "2026-03-31"
KEYS = ["year", "rank_cap", "symbol", "signal_date", "confirmation_date", "entry_date"]

def pf(vals):
    vals = [float(v) for v in vals if pd.notna(v)]
    w = sum(v for v in vals if v > 0)
    l = -sum(v for v in vals if v < 0)
    if l > 0:
        return w / l
    return float("inf") if w > 0 else None

def max_drawdown(vals):
    if not vals:
        return None
    peak = vals[0]
    out = 0.0
    for v in vals:
        peak = max(peak, v)
        if peak > 0:
            out = min(out, v / peak - 1)
    return out

def sharpe(vals):
    if len(vals) < 3:
        return None
    r = [vals[i] / vals[i-1] - 1 for i in range(1, len(vals)) if vals[i-1] > 0]
    if len(r) < 2:
        return None
    sd = statistics.stdev(r)
    return None if sd == 0 else statistics.mean(r) / sd * math.sqrt(252)

def merge_labels(anatomy_path, resilience_path):
    ga = pd.read_csv(anatomy_path, compression="infer")
    rr = pd.read_csv(resilience_path, compression="infer")
    for x in (ga, rr):
        x["year"] = x.year.astype(int)
        x["rank_cap"] = x.rank_cap.astype(int)
        for c in ["symbol", "signal_date", "confirmation_date", "entry_date"]:
            x[c] = x[c].astype(str)
    keep = KEYS + ["rebound_from_low_box", "low_progress_box"]
    m = ga.merge(rr[keep], on=KEYS, how="inner", validate="one_to_one")
    m["close_lift_box"] = m.rebound_from_low_box.astype(float) - m.low_progress_box.astype(float)
    return m

def load_thresholds(path):
    t = pd.read_csv(path)
    out = {}
    for r in t.itertuples(index=False):
        out[(int(r.rank_cap), int(r.year), str(r.gap_method))] = {
            "gap": float(r.gap_threshold),
            "lowprog": float(r.lowprog_median),
            "lift": float(r.close_lift_median),
        }
    return out

def classify_candidates(m, thresholds):
    rows = []
    for r in m.to_dict("records"):
        year = int(r["year"])
        if year < 2021 or year > 2026:
            continue
        if str(r.get("scale", "large")) != "large":
            continue
        cap = int(r["rank_cap"])
        if cap not in CAPS:
            continue
        if float(r["box_age_sessions"]) > FRESH[cap]:
            continue
        for method in METHODS:
            t = thresholds[(cap, year, method)]
            if float(r["gap_component"]) > t["gap"]:
                continue
            retest = float(r["low_progress_box"]) <= t["lowprog"]
            lift = float(r["close_lift_box"]) > t["lift"]
            if retest and lift:
                state = "RETEST_LIFT"
            elif retest:
                state = "RETEST_WEAK_LIFT"
            elif lift:
                state = "NO_RETEST_LIFT"
            else:
                state = "NO_RETEST_WEAK_LIFT"
            rows.append({**r, "gap_method": method, "state": state})
    return pd.DataFrame(rows)

def load_bars(source_dir, symbols):
    pieces = []
    market_dates = set()
    p = Path(source_dir)
    files = sorted(p.glob("**/bars_*.csv.gz"))
    if not files:
        raise RuntimeError("no bars_*.csv.gz files found")
    for fp in files:
        for ch in pd.read_csv(fp, chunksize=250000):
            ch["date"] = ch.date.astype(str)
            ch["ticker"] = ch.ticker.astype(str)
            market_dates.update(ch.loc[ch.ticker.eq("SPY"), "date"].tolist())
            z = ch[ch.ticker.isin(symbols)].copy()
            if len(z):
                pieces.append(z)
    if not pieces:
        raise RuntimeError("no needed bars loaded")
    bars = pd.concat(pieces, ignore_index=True)
    bars = bars.sort_values(["ticker", "date"]).drop_duplicates(["ticker", "date"], keep="last")
    calendar = sorted(d for d in market_dates if START <= d <= END)
    return bars, calendar

def run_portfolio(cands, bars, calendar, target_fraction):
    cidx = {d: i for i, d in enumerate(calendar)}
    bybar = {
        str(s): {str(r["date"]): r for r in g.to_dict("records")}
        for s, g in bars.groupby("ticker", sort=False)
    }
    byday = defaultdict(list)
    for r in cands.to_dict("records"):
        d = str(r["entry_date"])
        if d in cidx:
            byday[d].append(r)

    cash = 1.0
    pos = {}
    equity = []
    exposure = []
    trades = []

    for d in calendar:
        # 1) carried positions: opening gap exits.
        for sym in list(pos):
            b = bybar.get(sym, {}).get(d)
            if b is None:
                continue
            p = pos[sym]
            op = float(b["open"])
            px = None
            reason = None
            if op <= p["lower"]:
                px = op; reason = "stop_gap"
            elif op >= p["target"]:
                px = op; reason = "target_gap"
            if px is not None:
                proceeds = p["shares"] * px * (1 - EXIT_COST)
                cash += proceeds
                trades.append({
                    **p,
                    "exit_date": d,
                    "exit_price": px,
                    "exit_reason": reason,
                    "net_return": proceeds / p["cost_basis"] - 1,
                    "holding_sessions": cidx[d] - p["entry_i"] + 1,
                })
                del pos[sym]

        # 2) entries, deduplicated by symbol. 10% requested per event; scale to cash only.
        candidates = [x for x in byday.get(d, []) if str(x["symbol"]) not in pos]
        candidates.sort(key=lambda x: (str(x["symbol"]), str(x["signal_date"])))
        dedup = []
        seen = set()
        for x in candidates:
            sym = str(x["symbol"])
            if sym in seen:
                continue
            seen.add(sym)
            dedup.append(x)
        candidates = dedup

        eq_open = cash
        for sym, p in pos.items():
            b = bybar.get(sym, {}).get(d)
            px = float(b["open"]) if b is not None else float(p["last"])
            eq_open += p["shares"] * px

        valid = []
        for c in candidates:
            sym = str(c["symbol"])
            b = bybar.get(sym, {}).get(d)
            if b is None:
                continue
            op = float(b["open"])
            lower = float(c["lower"])
            upper = float(c["upper"])
            target = lower + target_fraction * (upper - lower)
            if not (lower < op < target):
                continue
            valid.append((c, op, lower, upper, target))

        if valid:
            requested = [ALLOC * eq_open] * len(valid)
            budget = min(cash, sum(requested))
            scale = budget / sum(requested) if requested else 0.0
            for (c, op, lower, upper, target), req in zip(valid, requested):
                a = req * scale
                if a <= 1e-12 or a > cash + 1e-10:
                    continue
                invest = a * (1 - ENTRY_COST)
                cash -= a
                sym = str(c["symbol"])
                pos[sym] = {
                    "symbol": sym,
                    "signal_date": str(c["signal_date"]),
                    "confirmation_date": str(c["confirmation_date"]),
                    "entry_date": d,
                    "entry_price": op,
                    "lower": lower,
                    "upper": upper,
                    "target": target,
                    "shares": invest / op,
                    "cost_basis": a,
                    "entry_i": cidx[d],
                    "last": op,
                }

        # 3) same-day / intraday lifecycle. Stop first if both touched.
        for sym in list(pos):
            p = pos[sym]
            b = bybar.get(sym, {}).get(d)
            hold = cidx[d] - p["entry_i"] + 1
            if b is None:
                if hold >= MAX_HOLD:
                    px = float(p["last"])
                    proceeds = p["shares"] * px * (1 - EXIT_COST)
                    cash += proceeds
                    trades.append({
                        **p, "exit_date": d, "exit_price": px,
                        "exit_reason": "max_hold_stale",
                        "net_return": proceeds / p["cost_basis"] - 1,
                        "holding_sessions": hold,
                    })
                    del pos[sym]
                continue
            lo = float(b["low"])
            hi = float(b["high"])
            cl = float(b["close"])
            px = None
            reason = None
            if lo <= p["lower"]:
                px = p["lower"]; reason = "stop"
            elif hi >= p["target"]:
                px = p["target"]; reason = "target"
            elif hold >= MAX_HOLD:
                px = cl; reason = "max_hold"
            if px is not None:
                proceeds = p["shares"] * px * (1 - EXIT_COST)
                cash += proceeds
                trades.append({
                    **p, "exit_date": d, "exit_price": px,
                    "exit_reason": reason,
                    "net_return": proceeds / p["cost_basis"] - 1,
                    "holding_sessions": hold,
                })
                del pos[sym]
            else:
                p["last"] = cl

        # 4) EOD mark.
        val = cash
        invested = 0.0
        for sym, p in pos.items():
            b = bybar.get(sym, {}).get(d)
            px = float(b["close"]) if b is not None else float(p["last"])
            p["last"] = px
            v = p["shares"] * px
            val += v
            invested += v
        equity.append({"date": d, "equity": val})
        exposure.append(invested / val if val > 0 else 0.0)

    # Mark open positions at end without forcing a synthetic realized trade.
    vals = [x["equity"] for x in equity]
    rs = [float(t["net_return"]) for t in trades]
    years = {}
    eq = pd.DataFrame(equity)
    if len(eq):
        eq["year"] = eq.date.str[:4]
        for y, g in eq.groupby("year"):
            first = float(g.equity.iloc[0])
            last = float(g.equity.iloc[-1])
            years[str(y)] = last / first - 1 if first else None

    return {
        "window": [calendar[0], calendar[-1]] if calendar else [None, None],
        "start_equity": 1.0,
        "end_equity": vals[-1] if vals else 1.0,
        "total_return": vals[-1] - 1 if vals else 0.0,
        "max_drawdown": max_drawdown(vals),
        "daily_sharpe": sharpe(vals),
        "avg_exposure": statistics.mean(exposure) if exposure else 0.0,
        "completed_trades": len(trades),
        "open_positions_at_end": len(pos),
        "profit_factor": pf(rs),
        "mean_trade": statistics.mean(rs) if rs else None,
        "win_rate": (sum(v > 0 for v in rs) / len(rs)) if rs else None,
        "yearly_returns": years,
        "trade_rows": trades,
        "equity_rows": equity,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--anatomy-labels", required=True)
    ap.add_argument("--resilience-labels", required=True)
    ap.add_argument("--thresholds", required=True)
    ap.add_argument("--source-dir", required=True)
    ap.add_argument("--outdir", required=True)
    a = ap.parse_args()

    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)

    merged = merge_labels(a.anatomy_labels, a.resilience_labels)
    thresholds = load_thresholds(a.thresholds)
    classified = classify_candidates(merged, thresholds)
    if classified.empty:
        raise RuntimeError("no classified candidates")

    symbols = set(classified.symbol.astype(str))
    symbols.add("SPY")
    bars, calendar = load_bars(a.source_dir, symbols)
    if not calendar:
        raise RuntimeError("empty 2021-2026Q1 calendar")

    summary = {
        "schema": "LARGE-GAP-RETEST-LIFT-HISTORICAL-PORTFOLIO-V10",
        "research_only": True,
        "window": [calendar[0], calendar[-1]],
        "portfolio_contract": {
            "initial_equity": 1.0,
            "allocation_per_event": ALLOC,
            "max_gross_exposure": 1.0,
            "duplicate_symbol_policy": "one_open_position_per_symbol",
            "entry_cost": ENTRY_COST,
            "exit_cost": EXIT_COST,
            "max_hold_sessions": MAX_HOLD,
            "same_day_both_barriers": "stop_first",
            "year_boundary": "continuous_no_forced_reset",
        },
        "lanes": {},
    }

    result_rows = []
    for cap in CAPS:
        for method in METHODS:
            z0 = classified[(classified.rank_cap == cap) & (classified.gap_method == method)].copy()
            for state in STATES:
                if state == "EXTREME_ALL":
                    z = z0
                else:
                    z = z0[z0.state == state]
                for target in TARGETS:
                    res = run_portfolio(z, bars, calendar, target)
                    key = f"top{cap}__{method}__{state}__t{int(target*100)}"
                    summary["lanes"][key] = {k: v for k, v in res.items() if k not in ("trade_rows", "equity_rows")}
                    result_rows.append({
                        "rank_cap": cap,
                        "gap_method": method,
                        "state": state,
                        "target_fraction": target,
                        "candidate_n": int(len(z)),
                        **summary["lanes"][key],
                    })
                    if cap == 500 and method == "EXPANDING" and state in ("RETEST_LIFT", "NO_RETEST_LIFT"):
                        pd.DataFrame(res["trade_rows"]).to_csv(out / f"top500_expanding_{state.lower()}_t{int(target*100)}_trades.csv", index=False)
                        pd.DataFrame(res["equity_rows"]).to_csv(out / f"top500_expanding_{state.lower()}_t{int(target*100)}_equity.csv", index=False)

    pd.DataFrame(result_rows).to_csv(out / "portfolio_results.csv", index=False)
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    primary = {
        k: v for k, v in summary["lanes"].items()
        if k in (
            "top500__EXPANDING__RETEST_LIFT__t60",
            "top500__EXPANDING__RETEST_LIFT__t80",
            "top500__FIXED_-1PCT__RETEST_LIFT__t60",
            "top500__FIXED_-1PCT__RETEST_LIFT__t80",
        )
    }
    print(json.dumps({"schema": summary["schema"], "window": summary["window"], "primary": primary}, indent=2))

if __name__ == "__main__":
    main()
