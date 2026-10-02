"""Index-only Up/Down Ratio strategy V2.

Rules fixed before reviewing V2 results:
- Universe: ^GSPC, ^IXIC, ^DJI only.
- Indicator: last 20 close-to-close daily directions, up_count / down_count.
- Entry signal at close t when ratio <= 2/3 AND close >= 200-day SMA.
- Entry executes at open t+1.
- Exit signal at close t when ratio >= 1.00; executes at open t+1.
- Maximum holding period: 10 trading sessions; exit at next eligible session open.
- Stop loss: 5% below entry price. If a session opens below stop, exit at that open;
  otherwise if the session low touches stop, exit at the stop price intraday.
- Long or cash only, 1x notional, no fees/slippage.
- Benchmark: buy at the same backtest start open and hold to final close.
"""
from __future__ import annotations

import json
import math
from collections import Counter
from datetime import date
from pathlib import Path
from statistics import mean, pstdev

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "docs/data/structure_lab.json"
OUT_PATH = ROOT / "docs/data/updown_index_backtest_v2.json"

SYMBOLS = ["^GSPC", "^IXIC", "^DJI"]
WINDOW = 20
MA_WINDOW = 200
ENTRY_RATIO = 2 / 3
EXIT_RATIO = 1.0
MAX_HOLD = 10
STOP_LOSS = 0.05


def _finite(x):
    try:
        return x is not None and math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def load_bars(obj):
    out = []
    for b in obj.get("bars", []):
        if len(b) < 5 or not all(_finite(b[j]) for j in (1, 2, 3, 4)):
            continue
        out.append({
            "date": str(b[0]),
            "open": float(b[1]),
            "high": float(b[2]),
            "low": float(b[3]),
            "close": float(b[4]),
        })
    out.sort(key=lambda x: x["date"])
    return out


def rolling_ratio(bars, window=WINDOW):
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


def rolling_sma(bars, window=MA_WINDOW):
    out = [None] * len(bars)
    acc = 0.0
    closes = [b["close"] for b in bars]
    for i, c in enumerate(closes):
        acc += c
        if i >= window:
            acc -= closes[i - window]
        if i >= window - 1:
            out[i] = acc / window
    return out


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
    holds = sorted(t["holding_days"] for t in closed)
    reasons = Counter(t.get("exit_reason", "unknown") for t in closed)
    return {
        "total_return_pct": round(total * 100, 3),
        "cagr_pct": round(cagr * 100, 3),
        "max_drawdown_pct": round(dd * 100, 3),
        "sharpe": round(sharpe, 3) if sharpe is not None else None,
        "trades": len(closed),
        "win_rate_pct": round(len(wins) / len(closed) * 100, 2) if closed else None,
        "avg_trade_pct": round(mean(trade_rets) * 100, 3) if trade_rets else None,
        "median_holding_days": holds[len(holds)//2] if holds else None,
        "exposure_pct": round(exposure_days / total_days * 100, 2) if total_days else 0.0,
        "exit_reasons": dict(reasons),
    }


def close_trade(trades, entry_date, entry_price, entry_idx, exit_date, exit_price, exit_idx, reason):
    trades.append({
        "entry_date": entry_date,
        "exit_date": exit_date,
        "entry_price": round(entry_price, 6),
        "exit_price": round(exit_price, 6),
        "return_pct": round((exit_price / entry_price - 1.0) * 100, 4),
        "holding_days": max(0, exit_idx - entry_idx),
        "exit_reason": reason,
    })


def backtest(bars):
    if len(bars) < MA_WINDOW + 3:
        raise ValueError("not enough bars")

    ratios = rolling_ratio(bars)
    ma200 = rolling_sma(bars)
    first_signal_idx = MA_WINDOW - 1
    start_idx = first_signal_idx + 1

    cash = 1.0
    units = 0.0
    pos = 0
    entry_price = None
    entry_date = None
    entry_idx = None
    pending_entry = False
    pending_exit = False

    equity = []
    eq_dates = []
    daily_returns = []
    trades = []
    exposure_days = 0
    prev_equity = 1.0

    for i in range(start_idx, len(bars)):
        bar = bars[i]
        op, lo, cl = bar["open"], bar["low"], bar["close"]

        # Execute prior close's standard exit at today's open.
        if pos == 1 and pending_exit:
            cash = units * op
            close_trade(trades, entry_date, entry_price, entry_idx, bar["date"], op, i, "ratio_or_time")
            units = 0.0
            pos = 0
            entry_price = entry_date = entry_idx = None
            pending_exit = False

        # Execute prior close's entry at today's open.
        if pos == 0 and pending_entry:
            units = cash / op
            cash = 0.0
            pos = 1
            entry_price = op
            entry_date = bar["date"]
            entry_idx = i
            pending_entry = False

        # Intraday stop, using only today's observed OHLC.
        stopped_today = False
        if pos == 1:
            stop_price = entry_price * (1.0 - STOP_LOSS)
            if op <= stop_price:
                exit_price = op
                reason = "stop_gap"
            elif lo <= stop_price:
                exit_price = stop_price
                reason = "stop_intraday"
            else:
                exit_price = None
                reason = None
            if exit_price is not None:
                cash = units * exit_price
                close_trade(trades, entry_date, entry_price, entry_idx, bar["date"], exit_price, i, reason)
                units = 0.0
                pos = 0
                entry_price = entry_date = entry_idx = None
                pending_exit = False
                stopped_today = True

        # Mark end-of-day equity. If stopped intraday, cash remains flat after exit.
        value = cash if pos == 0 else units * cl
        if pos == 1:
            exposure_days += 1
        equity.append(value)
        eq_dates.append(bar["date"])
        daily_returns.append(value / prev_equity - 1.0)
        prev_equity = value

        # Generate signals only after today's close for next session.
        r = ratios[i]
        ma = ma200[i]
        if pos == 0:
            if not stopped_today and r is not None and ma is not None and r <= ENTRY_RATIO and cl >= ma:
                pending_entry = True
        else:
            held = i - entry_idx + 1
            ratio_exit = r is not None and r >= EXIT_RATIO
            time_exit = held >= MAX_HOLD
            if ratio_exit or time_exit:
                pending_exit = True

    # Final forced close for trade statistics and terminal equity consistency.
    if pos == 1:
        final = bars[-1]
        final_value = units * final["close"]
        cash = final_value
        close_trade(trades, entry_date, entry_price, entry_idx, final["date"], final["close"], len(bars)-1, "forced_end")
        if equity:
            equity[-1] = final_value

    # Benchmark on the exact same start/end period.
    bench_entry = bars[start_idx]["open"]
    bench_equity = [b["close"] / bench_entry for b in bars[start_idx:]]
    bench_daily = [bench_equity[0] - 1.0]
    bench_daily += [bench_equity[i] / bench_equity[i - 1] - 1.0 for i in range(1, len(bench_equity))]
    bench_total = bench_equity[-1] - 1.0
    yrs = years_between(bars[start_idx]["date"], bars[-1]["date"])
    bench_cagr = bench_equity[-1] ** (1 / yrs) - 1.0
    bsd = pstdev(bench_daily) if len(bench_daily) > 1 else 0.0
    bench_sharpe = mean(bench_daily) / bsd * math.sqrt(252) if bsd > 0 else None

    benchmark = {
        "total_return_pct": round(bench_total * 100, 3),
        "cagr_pct": round(bench_cagr * 100, 3),
        "max_drawdown_pct": round(max_drawdown(bench_equity) * 100, 3),
        "sharpe": round(bench_sharpe, 3) if bench_sharpe is not None else None,
        "exposure_pct": 100.0,
    }

    last_ratio = ratios[-1]
    last_ma = ma200[-1]
    last_close = bars[-1]["close"]
    close_entry_condition = (
        last_ratio is not None and last_ma is not None and
        last_ratio <= ENTRY_RATIO and last_close >= last_ma
    )

    return {
        "start": bars[start_idx]["date"],
        "end": bars[-1]["date"],
        "bars": len(eq_dates),
        "last_ratio": None if last_ratio is None else ("inf" if math.isinf(last_ratio) else round(last_ratio, 4)),
        "last_close": round(last_close, 4),
        "last_ma200": round(last_ma, 4) if last_ma is not None else None,
        "current_close_entry_condition": bool(close_entry_condition),
        "strategy": metrics(equity, eq_dates, daily_returns, trades, exposure_days, len(eq_dates)),
        "benchmark": benchmark,
        "recent_trades": trades[-20:],
    }


def main():
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    out = {
        "schema": "UPDOWN-INDEX-BACKTEST-V2",
        "rules": {
            "universe": SYMBOLS,
            "window": WINDOW,
            "entry_ratio_lte": round(ENTRY_RATIO, 6),
            "ma_filter": f"close >= SMA{MA_WINDOW}",
            "exit_ratio_gte": EXIT_RATIO,
            "max_holding_sessions": MAX_HOLD,
            "stop_loss_pct": STOP_LOSS * 100,
            "execution": "entry/ratio/time signals at close t execute at open t+1; stop uses next-session OHLC with gap-aware fill",
            "side": "long_or_cash_only",
            "leverage": 1.0,
            "fees_slippage": 0.0,
            "note": "V2 fixed before reviewing results; index-only, no stock selection.",
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
