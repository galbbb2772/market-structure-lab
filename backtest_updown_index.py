"""Backtest a simple long-only index strategy driven only by each index's own up/down K-line ratio.

V1 rules (deliberately fixed before looking at results):
- Universe: ^GSPC, ^IXIC, ^DJI only.
- Indicator: last 20 close-to-close daily directions, up_count / down_count.
- Entry: ratio <= 2/3 at today's close.
- Exit: ratio >= 1.00 at today's close.
- Signal is executed at the NEXT trading day's open (no same-close lookahead).
- Long or cash only, 1x notional, no fees/slippage in V1.
- Benchmark: buy at the same backtest start open and hold to final close.
"""
from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path
from statistics import mean, pstdev

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "docs/data/structure_lab.json"
OUT_PATH = ROOT / "docs/data/updown_index_backtest.json"

SYMBOLS = ["^GSPC", "^IXIC", "^DJI"]
WINDOW = 20
ENTRY_RATIO = 2 / 3
EXIT_RATIO = 1.0


def _finite(x):
    try:
        return x is not None and math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def load_bars(obj):
    out = []
    for b in obj.get("bars", []):
        if len(b) < 5 or not (_finite(b[1]) and _finite(b[4])):
            continue
        out.append({
            "date": str(b[0]),
            "open": float(b[1]),
            "close": float(b[4]),
        })
    out.sort(key=lambda x: x["date"])
    return out


def rolling_ratio(bars, window=WINDOW):
    # ratio[i] is known only after close of bars[i]. It uses the previous
    # `window` close-to-close return signs ending at i.
    dirs = [None]
    for i in range(1, len(bars)):
        c0, c1 = bars[i - 1]["close"], bars[i]["close"]
        dirs.append(1 if c1 > c0 else -1 if c1 < c0 else 0)
    ratios = [None] * len(bars)
    for i in range(window, len(bars)):
        w = dirs[i - window + 1 : i + 1]
        up = sum(1 for x in w if x == 1)
        down = sum(1 for x in w if x == -1)
        ratios[i] = math.inf if down == 0 and up else (up / down if down else None)
    return ratios


def max_drawdown(equity):
    peak = 0.0
    worst = 0.0
    for v in equity:
        peak = max(peak, v)
        if peak > 0:
            worst = min(worst, v / peak - 1.0)
    return worst


def years_between(a: str, b: str) -> float:
    d0 = date.fromisoformat(a)
    d1 = date.fromisoformat(b)
    return max((d1 - d0).days / 365.2425, 1 / 365.2425)


def metrics(equity, dates, daily_returns, trades, exposure_days, total_days):
    total = equity[-1] / equity[0] - 1.0 if equity else 0.0
    years = years_between(dates[0], dates[-1]) if len(dates) >= 2 else 0.0
    cagr = (equity[-1] / equity[0]) ** (1 / years) - 1.0 if equity and years > 0 else 0.0
    dd = max_drawdown(equity)
    sd = pstdev(daily_returns) if len(daily_returns) > 1 else 0.0
    sharpe = mean(daily_returns) / sd * math.sqrt(252) if sd > 0 else None
    closed = [t for t in trades if t.get("exit_date")]
    trade_rets = [t["return_pct"] / 100 for t in closed]
    wins = [x for x in trade_rets if x > 0]
    return {
        "total_return_pct": round(total * 100, 3),
        "cagr_pct": round(cagr * 100, 3),
        "max_drawdown_pct": round(dd * 100, 3),
        "sharpe": round(sharpe, 3) if sharpe is not None else None,
        "trades": len(closed),
        "win_rate_pct": round(len(wins) / len(closed) * 100, 2) if closed else None,
        "avg_trade_pct": round(mean(trade_rets) * 100, 3) if trade_rets else None,
        "median_holding_days": sorted([t["holding_days"] for t in closed])[len(closed)//2] if closed else None,
        "exposure_pct": round(exposure_days / total_days * 100, 2) if total_days else 0.0,
    }


def backtest(bars):
    if len(bars) < WINDOW + 3:
        raise ValueError("not enough bars")
    ratios = rolling_ratio(bars)
    first_signal_idx = next(i for i, x in enumerate(ratios) if x is not None)
    start_idx = first_signal_idx + 1  # first possible execution day

    # Build close-state signal with hysteresis. State[t] is decided at close t
    # and is only executable at open t+1.
    close_state = [0] * len(bars)
    state = 0
    for i in range(first_signal_idx, len(bars)):
        r = ratios[i]
        if r is None:
            close_state[i] = state
            continue
        if state == 0 and r <= ENTRY_RATIO:
            state = 1
        elif state == 1 and r >= EXIT_RATIO:
            state = 0
        close_state[i] = state

    cash = 1.0
    units = 0.0
    pos = 0
    entry_price = None
    entry_date = None
    entry_idx = None
    equity = []
    eq_dates = []
    daily_returns = []
    trades = []
    exposure_days = 0
    prev_equity = 1.0

    for i in range(start_idx, len(bars)):
        desired = close_state[i - 1]
        op = bars[i]["open"]
        cl = bars[i]["close"]

        if desired != pos:
            if desired == 1:
                units = cash / op
                cash = 0.0
                pos = 1
                entry_price = op
                entry_date = bars[i]["date"]
                entry_idx = i
            else:
                cash = units * op
                ret = op / entry_price - 1.0
                trades.append({
                    "entry_date": entry_date,
                    "exit_date": bars[i]["date"],
                    "entry_price": round(entry_price, 6),
                    "exit_price": round(op, 6),
                    "return_pct": round(ret * 100, 4),
                    "holding_days": i - entry_idx,
                })
                units = 0.0
                pos = 0
                entry_price = entry_date = entry_idx = None

        value = cash if pos == 0 else units * cl
        if pos == 1:
            exposure_days += 1
        equity.append(value)
        eq_dates.append(bars[i]["date"])
        daily_returns.append(value / prev_equity - 1.0)
        prev_equity = value

    # Close any still-open trade at final close for trade statistics only.
    if pos == 1:
        final = bars[-1]
        ret = final["close"] / entry_price - 1.0
        trades.append({
            "entry_date": entry_date,
            "exit_date": final["date"],
            "entry_price": round(entry_price, 6),
            "exit_price": round(final["close"], 6),
            "return_pct": round(ret * 100, 4),
            "holding_days": len(bars) - 1 - entry_idx,
            "forced_end": True,
        })

    # Benchmark on exactly the same start/end period.
    bench_entry = bars[start_idx]["open"]
    bench_equity = [b["close"] / bench_entry for b in bars[start_idx:]]
    bench_daily = [bench_equity[0] - 1.0]
    bench_daily += [bench_equity[i] / bench_equity[i - 1] - 1.0 for i in range(1, len(bench_equity))]
    bench_total = bench_equity[-1] - 1.0
    yrs = years_between(bars[start_idx]["date"], bars[-1]["date"])
    bench_cagr = bench_equity[-1] ** (1 / yrs) - 1.0
    bsd = pstdev(bench_daily) if len(bench_daily) > 1 else 0.0
    bench_sharpe = mean(bench_daily) / bsd * math.sqrt(252) if bsd > 0 else None

    strat_metrics = metrics(
        equity, eq_dates, daily_returns, trades, exposure_days, len(eq_dates)
    )
    benchmark = {
        "total_return_pct": round(bench_total * 100, 3),
        "cagr_pct": round(bench_cagr * 100, 3),
        "max_drawdown_pct": round(max_drawdown(bench_equity) * 100, 3),
        "sharpe": round(bench_sharpe, 3) if bench_sharpe is not None else None,
        "exposure_pct": 100.0,
    }

    last_ratio = ratios[-1]
    return {
        "start": bars[start_idx]["date"],
        "end": bars[-1]["date"],
        "bars": len(eq_dates),
        "last_ratio": None if last_ratio is None else ("inf" if math.isinf(last_ratio) else round(last_ratio, 4)),
        "current_close_signal": "LONG" if close_state[-1] else "CASH",
        "strategy": strat_metrics,
        "benchmark": benchmark,
        "recent_trades": trades[-20:],
    }


def main():
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    out = {
        "schema": "UPDOWN-INDEX-BACKTEST-V1",
        "rules": {
            "universe": SYMBOLS,
            "window": WINDOW,
            "entry_ratio_lte": round(ENTRY_RATIO, 6),
            "exit_ratio_gte": EXIT_RATIO,
            "execution": "signal at close t; execute at open t+1",
            "side": "long_or_cash_only",
            "leverage": 1.0,
            "fees_slippage": 0.0,
            "note": "Fixed V1 before reviewing results; index-only, no stock selection.",
        },
        "results": {},
    }
    for sym in SYMBOLS:
        inst = raw.get("instruments", {}).get(sym)
        if not inst:
            out["results"][sym] = {"error": "missing instrument"}
            continue
        bars = load_bars(inst)
        res = backtest(bars)
        res["name"] = inst.get("name", sym)
        out["results"][sym] = res
        print(sym, res["start"], res["end"], res["strategy"], res["benchmark"], flush=True)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Wrote", OUT_PATH)


if __name__ == "__main__":
    main()
