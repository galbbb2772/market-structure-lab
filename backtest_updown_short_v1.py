"""Index-only short strategy driven by the 20-session up/down K-line ratio.

Short V1 rules fixed before results:
- Universe: ^GSPC, ^IXIC, ^DJI only.
- Indicator: last 20 close-to-close daily directions, up_count / down_count.
- Entry: ratio >= 3.0 at close t -> short at open t+1.
- Exit: ratio <= 1.2 at close t -> cover at open t+1.
- No stop loss, no MA filter, no max holding period.
- Short or cash only, 1x notional at entry, no fees/borrow/slippage.
- Each trade records maximum adverse excursion (MAE) against the short.
"""
from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path
from statistics import mean, pstdev

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "docs/data/structure_lab.json"
OUT_PATH = ROOT / "docs/data/updown_short_v1.json"

SYMBOLS = ["^GSPC", "^IXIC", "^DJI"]
WINDOW = 20
ENTRY_RATIO = 3.0
EXIT_RATIO = 1.2


def finite(x):
    try:
        return x is not None and math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def load_bars(obj):
    out = []
    for b in obj.get("bars", []):
        if len(b) < 5 or not all(finite(b[j]) for j in (1, 2, 3, 4)):
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


def rolling_ratio(bars):
    dirs = [None]
    for i in range(1, len(bars)):
        a, b = bars[i - 1]["close"], bars[i]["close"]
        dirs.append(1 if b > a else -1 if b < a else 0)
    ratios = [None] * len(bars)
    for i in range(WINDOW, len(bars)):
        w = dirs[i - WINDOW + 1 : i + 1]
        up = sum(x == 1 for x in w)
        down = sum(x == -1 for x in w)
        ratios[i] = math.inf if down == 0 and up else (up / down if down else None)
    return ratios


def years_between(a: str, b: str) -> float:
    return max((date.fromisoformat(b) - date.fromisoformat(a)).days / 365.2425, 1 / 365.2425)


def max_drawdown(eq):
    peak = 0.0
    worst = 0.0
    for v in eq:
        peak = max(peak, v)
        if peak > 0:
            worst = min(worst, v / peak - 1.0)
    return worst


def summarize(eq, dates, daily, trades, exposure):
    if not eq:
        return {}
    total = eq[-1] / eq[0] - 1.0
    yrs = years_between(dates[0], dates[-1]) if len(dates) > 1 else 0.0
    cagr = None
    if yrs > 0 and eq[-1] > 0 and eq[0] > 0:
        cagr = (eq[-1] / eq[0]) ** (1 / yrs) - 1.0
    sd = pstdev(daily) if len(daily) > 1 else 0.0
    sh = mean(daily) / sd * math.sqrt(252) if sd > 0 else None
    rets = [t["return_pct"] / 100 for t in trades]
    maes = [t["mae_pct"] for t in trades]
    wins = sum(r > 0 for r in rets)
    holds = sorted(t["holding_days"] for t in trades)
    return {
        "total_return_pct": round(total * 100, 3),
        "cagr_pct": round(cagr * 100, 3) if cagr is not None else None,
        "max_drawdown_pct": round(max_drawdown(eq) * 100, 3),
        "sharpe": round(sh, 3) if sh is not None else None,
        "trades": len(trades),
        "win_rate_pct": round(wins / len(trades) * 100, 2) if trades else None,
        "avg_trade_pct": round(mean(rets) * 100, 3) if rets else None,
        "median_holding_days": holds[len(holds)//2] if holds else None,
        "exposure_pct": round(exposure / len(dates) * 100, 2) if dates else 0.0,
        "avg_mae_pct": round(mean(maes), 3) if maes else None,
        "worst_mae_pct": round(max(maes), 3) if maes else None,
        "terminal_equity": round(eq[-1], 6),
        "blown_up": any(v <= 0 for v in eq),
    }


def backtest(bars):
    if len(bars) < WINDOW + 3:
        raise ValueError("not enough bars")
    ratios = rolling_ratio(bars)
    start = WINDOW + 1

    equity_cash = 1.0
    pos = False
    short_units = 0.0
    entry_price = None
    entry_equity = None
    entry_date = None
    entry_idx = None
    max_high = None
    pending_entry = False
    pending_exit = False

    eq = []
    dates = []
    daily = []
    trades = []
    exposure = 0
    prev_eq = 1.0

    for i in range(start, len(bars)):
        bar = bars[i]
        op, hi, cl = bar["open"], bar["high"], bar["close"]

        if pos and pending_exit:
            exit_equity = entry_equity + short_units * (entry_price - op)
            trade_ret = exit_equity / entry_equity - 1.0
            mae = max_high / entry_price - 1.0
            trades.append({
                "entry_date": entry_date,
                "exit_date": bar["date"],
                "entry_price": round(entry_price, 6),
                "exit_price": round(op, 6),
                "return_pct": round(trade_ret * 100, 4),
                "holding_days": i - entry_idx,
                "mae_pct": round(mae * 100, 4),
                "exit_reason": "ratio",
            })
            equity_cash = exit_equity
            pos = False
            short_units = 0.0
            entry_price = entry_equity = entry_date = entry_idx = max_high = None
            pending_exit = False

        if (not pos) and pending_entry:
            entry_equity = equity_cash
            entry_price = op
            short_units = entry_equity / entry_price
            entry_date = bar["date"]
            entry_idx = i
            max_high = hi
            pos = True
            pending_entry = False

        if pos:
            max_high = max(max_high, hi)
            value = entry_equity + short_units * (entry_price - cl)
            exposure += 1
        else:
            value = equity_cash

        eq.append(value)
        dates.append(bar["date"])
        daily.append(value / prev_eq - 1.0 if prev_eq != 0 else 0.0)
        prev_eq = value

        r = ratios[i]
        if pos:
            if r is not None and r <= EXIT_RATIO:
                pending_exit = True
        else:
            if r is not None and r >= ENTRY_RATIO:
                pending_entry = True

    if pos:
        final = bars[-1]
        exit_equity = entry_equity + short_units * (entry_price - final["close"])
        trade_ret = exit_equity / entry_equity - 1.0
        mae = max_high / entry_price - 1.0
        trades.append({
            "entry_date": entry_date,
            "exit_date": final["date"],
            "entry_price": round(entry_price, 6),
            "exit_price": round(final["close"], 6),
            "return_pct": round(trade_ret * 100, 4),
            "holding_days": len(bars) - 1 - entry_idx,
            "mae_pct": round(mae * 100, 4),
            "exit_reason": "forced_end",
        })
        eq[-1] = exit_equity
        equity_cash = exit_equity

    last_ratio = ratios[-1]
    return {
        "start": bars[start]["date"],
        "end": bars[-1]["date"],
        "bars": len(eq),
        "last_ratio": None if last_ratio is None else ("inf" if math.isinf(last_ratio) else round(last_ratio, 4)),
        "current_close_signal": "SHORT" if pos or pending_entry else "CASH",
        "strategy": summarize(eq, dates, daily, trades, exposure),
        "recent_trades": trades[-20:],
    }


def main():
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    out = {
        "schema": "UPDOWN-SHORT-V1",
        "rules": {
            "universe": SYMBOLS,
            "window": WINDOW,
            "entry_ratio_gte": ENTRY_RATIO,
            "exit_ratio_lte": EXIT_RATIO,
            "execution": "signal at close t; execute at open t+1",
            "side": "short_or_cash_only",
            "notional": "1x equity at entry",
            "stop_loss": None,
            "max_holding": None,
            "fees_borrow_slippage": 0.0,
            "note": "Fixed Short V1 before reviewing results. No stock selection.",
        },
        "results": {},
    }
    for sym in SYMBOLS:
        inst = raw.get("instruments", {}).get(sym)
        if not inst:
            out["results"][sym] = {"error": "missing instrument"}
            continue
        res = backtest(load_bars(inst))
        res["name"] = inst.get("name", sym)
        out["results"][sym] = res
        print(sym, res["strategy"], flush=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Wrote", OUT_PATH)


if __name__ == "__main__":
    main()
