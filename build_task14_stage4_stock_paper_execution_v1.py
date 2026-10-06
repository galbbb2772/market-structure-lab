from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

import research_task14_stage4_multiasset_v1 as market

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "docs/data/task14_stage4_stock_candidate_adapter_v1.json"
OUT = ROOT / "docs/data/task14_stage4_stock_paper_execution_v1.json"
SPEC = "research/task14_stage4_stock_paper_execution_v1/STUDY_SPEC.md"

SCHEMA = "TASK14-PAPER-STOCK-EXECUTION-V1"
FROZEN_THROUGH = "2026-10-02"
START_CAPITAL = 100_000.0
EVENT_SLEEVE_TARGET = 0.25
SINGLE_NAME_CAP = 0.10
GROSS_CAP = 1.00
HOLD_SIGNAL_SESSIONS = 10
COST_MODELS = {
    "fixed_25bps_rt": 25.0,
    "fixed_50bps_rt": 50.0,
}

BASE_IMMUTABLE = (
    "candidate_id",
    "symbol",
    "signal_date",
    "candidate_first_seen_at",
    "upstream_rank",
    "target_portfolio_weight",
    "accepted",
    "skip_reason",
)
ENTRY_IMMUTABLE = (
    "entry_date",
    "entry_open",
    "entry_notional_usd",
    "adv20_usd",
    "adv_participation_pct",
    "beta60",
)


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_existing():
    if not OUT.exists():
        return None
    obj = load_json(OUT)
    if obj.get("schema") != SCHEMA:
        raise RuntimeError("existing stock paper ledger schema mismatch")
    if obj.get("frozen_through_market_date") != FROZEN_THROUGH:
        raise RuntimeError("existing stock paper ledger freeze boundary mismatch")
    return obj


def existing_decision_map(existing):
    out = {}
    if not existing:
        return out
    for cost_model, portfolio in (existing.get("portfolios") or {}).items():
        for d in portfolio.get("candidate_decisions") or []:
            out[f"{cost_model}|{d['candidate_id']}"] = d
    return out


def drop_current_utc_session(rows):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return [r for r in rows if r["date"] < today]


def candidate_rank(c):
    value = c.get("selection_rank")
    if value is None:
        value = c.get("rank")
    try:
        return int(value) if value is not None else None
    except Exception:
        return None


def collect_trade_pool(adapter):
    a = adapter.get("adapter") or {}
    rows = []
    for c in a.get("candidates") or []:
        if not c.get("adapter_trade_pool_eligible"):
            continue
        d = str(c.get("as_of_market_date") or "")
        if not d or d <= FROZEN_THROUGH:
            continue
        cid = str(c.get("candidate_id") or "").strip()
        symbol = str(c.get("symbol") or "").strip().upper()
        first_seen = str(c.get("first_seen_at") or "").strip()
        adv = c.get("adv20_usd")
        if not cid or not symbol or not first_seen:
            raise RuntimeError(f"trade-pool candidate missing immutable identity: {c}")
        try:
            adv = float(adv)
        except Exception:
            raise RuntimeError(f"trade-pool candidate missing ADV20: {cid}")
        if not math.isfinite(adv) or adv <= 0:
            raise RuntimeError(f"invalid ADV20 for {cid}: {adv}")
        rows.append({
            "candidate_id": cid,
            "symbol": symbol,
            "signal_date": d,
            "candidate_first_seen_at": first_seen,
            "upstream_rank": candidate_rank(c),
            "upstream_entry_date": c.get("entry_date"),
            "adv20_usd": adv,
            "trigger_reasons": c.get("trigger_reasons") or [],
            "security_id": c.get("security_id"),
            "continuous_segment_id": c.get("continuous_segment_id"),
        })
    rows.sort(key=lambda x: (x["signal_date"], x["upstream_rank"] or 10**9, x["candidate_id"]))

    seen = set()
    for x in rows:
        if x["candidate_id"] in seen:
            raise RuntimeError(f"duplicate candidate_id in adapter trade pool: {x['candidate_id']}")
        seen.add(x["candidate_id"])
    return rows


def beta60(asset_rows, spy_rows, signal_date):
    ar = market.returns_map(asset_rows)
    sr = market.returns_map(spy_rows)
    dates = sorted(d for d in ar if d <= signal_date and d in sr)[-60:]
    if len(dates) < 40:
        return None
    a = [ar[d] for d in dates]
    b = [sr[d] for d in dates]
    ma = sum(a) / len(a)
    mb = sum(b) / len(b)
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b)) / max(1, len(a) - 1)
    varb = sum((y - mb) ** 2 for y in b) / max(1, len(b) - 1)
    if varb <= 0:
        return None
    v = cov / varb
    return v if math.isfinite(v) else None


def prepare_events(candidates, data):
    spy = data["SPY"]
    spy_index = {r["date"]: i for i, r in enumerate(spy)}
    by_day = defaultdict(list)
    for c in candidates:
        by_day[c["signal_date"]].append(c)

    events = []
    for signal_date in sorted(by_day):
        si = spy_index.get(signal_date)
        if si is None:
            raise RuntimeError(f"SPY missing exact signal date: {signal_date}")
        if si + 1 >= len(spy):
            # A signal can be observed before its next open exists. Keep it pending.
            entry_date = None
        else:
            entry_date = spy[si + 1]["date"]
        exit_date = spy[si + HOLD_SIGNAL_SESSIONS]["date"] if si + HOLD_SIGNAL_SESSIONS < len(spy) else None

        group = sorted(by_day[signal_date], key=lambda x: (x["upstream_rank"] or 10**9, x["candidate_id"]))
        n = len(group)
        target_weight = min(SINGLE_NAME_CAP, EVENT_SLEEVE_TARGET / n)
        prepared = []
        for c in group:
            upstream_entry = c.get("upstream_entry_date")
            if upstream_entry and entry_date and upstream_entry != entry_date:
                raise RuntimeError(
                    f"upstream entry date mismatch for {c['candidate_id']}: upstream={upstream_entry} next_spy={entry_date}"
                )
            asset_rows = data[c["symbol"]]
            if market.exact_bar(asset_rows, signal_date) is None:
                raise RuntimeError(f"{c['symbol']} missing exact signal-date bar {signal_date}")
            prepared.append({
                **c,
                "signal_spy_index": si,
                "entry_spy_index": si + 1,
                "entry_date": entry_date,
                "exit_spy_index": si + HOLD_SIGNAL_SESSIONS,
                "exit_date": exit_date,
                "target_portfolio_weight": target_weight,
                "beta60": beta60(asset_rows, spy, signal_date),
            })
        events.append({
            "signal_date": signal_date,
            "signal_spy_index": si,
            "entry_spy_index": si + 1,
            "entry_date": entry_date,
            "exit_spy_index": si + HOLD_SIGNAL_SESSIONS,
            "exit_date": exit_date,
            "candidate_count": n,
            "event_target_weight": target_weight * n,
            "candidates": prepared,
        })
    return events


def asof_close(rows, date, cache):
    if date in cache:
        return cache[date]
    value = None
    for r in rows:
        if r["date"] > date:
            break
        value = r["close"]
    cache[date] = value
    return value


def simulate(data, events, cost_model, old_map, now):
    spy = data["SPY"]
    rt_bps = COST_MODELS[cost_model]
    half_cost_rate = rt_bps / 20000.0

    by_signal = {e["signal_spy_index"]: e for e in events}
    pending = []
    positions = []
    decisions = []
    realized = []
    curve = []
    cash = START_CAPITAL
    total_cost = 0.0
    turnover = 0.0
    max_participation = 0.0
    caches = {s: {} for s in data if s != "SPY"}

    for i, bar in enumerate(spy):
        date = bar["date"]

        entrants = [x for x in pending if x["entry_spy_index"] == i]
        pending = [x for x in pending if x["entry_spy_index"] != i]

        for event in entrants:
            equity_open = cash
            gross_open = 0.0
            for pos in positions:
                b = market.exact_bar(data[pos["symbol"]], date)
                px = b["open"] if b else asof_close(data[pos["symbol"]], date, caches[pos["symbol"]])
                if px is not None:
                    value = pos["shares"] * px
                    equity_open += value
                    gross_open += abs(value)

            eligible = []
            for c in event["candidates"]:
                d = c["decision"]
                b = market.exact_bar(data[c["symbol"]], date)
                if b is None:
                    d["execution_status"] = "entry_data_missing"
                    d["skip_reason"] = "entry_data_missing"
                    continue
                eligible.append((c, b))

            total_target = sum(c["target_portfolio_weight"] * equity_open for c, _ in eligible)
            available_gross = max(0.0, GROSS_CAP * equity_open - gross_open)
            if total_target <= 0 or available_gross <= 0 or cash <= 0:
                for c, _ in eligible:
                    c["decision"]["execution_status"] = "gross_cap_or_cash_blocked"
                    c["decision"]["skip_reason"] = "gross_cap_or_cash_blocked"
                continue

            scale = min(
                1.0,
                available_gross / total_target,
                cash / (total_target * (1.0 + half_cost_rate)),
            )

            for c, b in eligible:
                d = c["decision"]
                notional = c["target_portfolio_weight"] * equity_open * scale
                if notional <= max(1.0, equity_open * 1e-8):
                    d["execution_status"] = "gross_cap_or_cash_blocked"
                    d["skip_reason"] = "gross_cap_or_cash_blocked"
                    continue
                entry_cost = notional * half_cost_rate
                shares = notional / b["open"]
                cash -= notional + entry_cost
                total_cost += entry_cost
                turnover += notional
                participation = notional / c["adv20_usd"]
                max_participation = max(max_participation, participation)

                d.update({
                    "accepted": True,
                    "skip_reason": None,
                    "execution_status": "entered",
                    "entry_date": date,
                    "entry_open": round(b["open"], 8),
                    "entry_notional_usd": round(notional, 2),
                    "adv20_usd": round(c["adv20_usd"], 2),
                    "adv_participation_pct": round(participation * 100.0, 8),
                    "beta60": None if c["beta60"] is None else round(c["beta60"], 8),
                })
                positions.append({
                    "candidate_id": c["candidate_id"],
                    "symbol": c["symbol"],
                    "signal_date": c["signal_date"],
                    "entry_date": date,
                    "entry_open": b["open"],
                    "entry_notional": notional,
                    "entry_cost": entry_cost,
                    "shares": shares,
                    "exit_spy_index": c["exit_spy_index"],
                    "exit_date": c["exit_date"],
                    "beta60": c["beta60"],
                })

        survivors = []
        for pos in positions:
            if pos["exit_spy_index"] < i:
                raise RuntimeError(f"missed exact +10D stock exit: {pos['candidate_id']}")
            if pos["exit_spy_index"] == i:
                b = market.exact_bar(data[pos["symbol"]], date)
                if b is None:
                    raise RuntimeError(f"missing exact exit bar {pos['symbol']} {date}")
                exit_value = pos["shares"] * b["close"]
                exit_cost = exit_value * half_cost_rate
                cash += exit_value - exit_cost
                total_cost += exit_cost
                turnover += exit_value
                pnl = (exit_value - exit_cost) - (pos["entry_notional"] + pos["entry_cost"])
                realized.append({
                    "candidate_id": pos["candidate_id"],
                    "symbol": pos["symbol"],
                    "signal_date": pos["signal_date"],
                    "entry_date": pos["entry_date"],
                    "exit_date": date,
                    "entry_notional_usd": round(pos["entry_notional"], 2),
                    "net_pnl_usd": round(pnl, 2),
                    "net_return_pct_on_entry_notional": round(100.0 * pnl / pos["entry_notional"], 6),
                })
            else:
                survivors.append(pos)
        positions = survivors

        equity = cash
        gross = 0.0
        beta_dollar = 0.0
        beta_known_gross = 0.0
        max_name = 0.0
        for pos in positions:
            px = asof_close(data[pos["symbol"]], date, caches[pos["symbol"]])
            if px is None:
                continue
            value = pos["shares"] * px
            equity += value
            gross += abs(value)
            max_name = max(max_name, abs(value))
            if pos["beta60"] is not None:
                beta_dollar += value * pos["beta60"]
                beta_known_gross += abs(value)

        curve.append({
            "date": date,
            "equity": round(equity, 4),
            "gross_exposure": 0.0 if equity == 0 else round(gross / equity, 8),
            "beta_exposure": 0.0 if equity == 0 else round(beta_dollar / equity, 8),
            "beta_coverage_of_gross": 0.0 if gross == 0 else round(beta_known_gross / gross, 8),
            "max_single_name_weight": 0.0 if equity == 0 else round(max_name / equity, 8),
        })

        event = by_signal.get(i)
        if event:
            event_copy = {
                **event,
                "candidates": [],
            }
            for c in event["candidates"]:
                rank = c["upstream_rank"]
                d = {
                    "candidate_id": c["candidate_id"],
                    "symbol": c["symbol"],
                    "signal_date": c["signal_date"],
                    "candidate_first_seen_at": c["candidate_first_seen_at"],
                    "upstream_rank": rank,
                    "target_portfolio_weight": round(c["target_portfolio_weight"], 10),
                    "accepted": True,
                    "skip_reason": None,
                    "paper_first_seen_at": now,
                    "execution_status": "pending_entry",
                    "entry_date": None,
                    "entry_open": None,
                    "entry_notional_usd": None,
                    "adv20_usd": round(c["adv20_usd"], 2),
                    "adv_participation_pct": None,
                    "beta60": None if c["beta60"] is None else round(c["beta60"], 8),
                    "trigger_reasons": c["trigger_reasons"],
                    "security_id": c["security_id"],
                    "continuous_segment_id": c["continuous_segment_id"],
                }
                key = f"{cost_model}|{c['candidate_id']}"
                old = old_map.get(key)
                if old and old.get("paper_first_seen_at"):
                    d["paper_first_seen_at"] = old["paper_first_seen_at"]
                c2 = dict(c)
                c2["decision"] = d
                event_copy["candidates"].append(c2)
                decisions.append(d)
            pending.append(event_copy)

    if pending:
        # Pending next-open decisions are valid near the current market edge.
        pass

    latest_date = spy[-1]["date"] if spy else None
    latest_equity = curve[-1]["equity"] if curve else START_CAPITAL

    peak = -float("inf")
    max_dd = 0.0
    for x in curve:
        peak = max(peak, x["equity"])
        if peak > 0:
            max_dd = min(max_dd, x["equity"] / peak - 1.0)

    open_positions = []
    for pos in positions:
        px = asof_close(data[pos["symbol"]], latest_date, caches[pos["symbol"]])
        open_positions.append({
            "candidate_id": pos["candidate_id"],
            "symbol": pos["symbol"],
            "signal_date": pos["signal_date"],
            "entry_date": pos["entry_date"],
            "scheduled_exit_date": pos["exit_date"],
            "marked_date": latest_date,
            "marked_value_usd": None if px is None else round(pos["shares"] * px, 2),
        })

    return {
        "cost_model": cost_model,
        "round_trip_cost_bps": rt_bps,
        "start_capital_usd": START_CAPITAL,
        "latest_market_date": latest_date,
        "latest_equity_usd": round(latest_equity, 2),
        "return_to_date_pct": round(100.0 * (latest_equity / START_CAPITAL - 1.0), 6),
        "max_drawdown_to_date_pct": round(100.0 * max_dd, 6),
        "candidate_decisions": decisions,
        "realized_positions": realized,
        "open_positions": open_positions,
        "pending_event_count": len(pending),
        "total_modeled_cost_to_date_usd": round(total_cost, 2),
        "turnover_multiple_start_capital": round(turnover / START_CAPITAL, 6),
        "max_adv_participation_pct": round(max_participation * 100.0, 8),
        "max_gross_exposure": round(max((x["gross_exposure"] for x in curve), default=0.0), 8),
        "max_beta_exposure": round(max((abs(x["beta_exposure"]) for x in curve), default=0.0), 8),
        "max_single_name_weight": round(max((x["max_single_name_weight"] for x in curve), default=0.0), 8),
        "equity_curve": curve,
    }


def compare_existing(existing, portfolios):
    if not existing:
        return []
    old = existing_decision_map(existing)
    new = {}
    for cost_model, portfolio in portfolios.items():
        for d in portfolio.get("candidate_decisions") or []:
            new[f"{cost_model}|{d['candidate_id']}"] = d

    discrepancies = []
    for key, a in old.items():
        b = new.get(key)
        if b is None:
            discrepancies.append({"key": key, "field": "decision_missing_on_recompute"})
            continue
        for field in BASE_IMMUTABLE:
            if a.get(field) != b.get(field):
                discrepancies.append({
                    "key": key,
                    "field": field,
                    "stored": a.get(field),
                    "recompute": b.get(field),
                })
        if a.get("entry_date") is not None:
            for field in ENTRY_IMMUTABLE:
                if a.get(field) != b.get(field):
                    discrepancies.append({
                        "key": key,
                        "field": field,
                        "stored": a.get(field),
                        "recompute": b.get(field),
                    })
    return discrepancies


def empty_portfolios(latest_market_date):
    return {
        name: {
            "cost_model": name,
            "round_trip_cost_bps": bps,
            "start_capital_usd": START_CAPITAL,
            "latest_market_date": latest_market_date,
            "latest_equity_usd": START_CAPITAL,
            "return_to_date_pct": 0.0,
            "max_drawdown_to_date_pct": 0.0,
            "candidate_decisions": [],
            "realized_positions": [],
            "open_positions": [],
            "pending_event_count": 0,
            "total_modeled_cost_to_date_usd": 0.0,
            "turnover_multiple_start_capital": 0.0,
            "max_adv_participation_pct": 0.0,
            "max_gross_exposure": 0.0,
            "max_beta_exposure": 0.0,
            "max_single_name_weight": 0.0,
            "equity_curve": [],
        }
        for name, bps in COST_MODELS.items()
    }


def write_output(adapter, candidates, portfolios, discrepancies, market_sources, latest_market_date, now):
    a = adapter.get("adapter") or {}
    out = {
        "schema": SCHEMA,
        "generated_at": now,
        "research_only": True,
        "paper_only": True,
        "diagnostic_only": True,
        "production_effect": "none",
        "broker_orders_enabled": False,
        "frozen_through_market_date": FROZEN_THROUGH,
        "study_spec": SPEC,
        "upstream_adapter_status": a.get("status"),
        "upstream_feed_fetch_status": a.get("feed_fetch_status"),
        "upstream_feed_latest_as_of_market_date": a.get("feed_latest_as_of_market_date"),
        "upstream_trade_pool_eligible_count": int(a.get("trade_pool_eligible_count") or 0),
        "reconstructed_trade_pool_count": len(candidates),
        "latest_complete_market_date": latest_market_date,
        "portfolio_rule": {
            "long_only": True,
            "signal_decision_time": "signal_date_close",
            "entry": "next_regular_SPY_session_open",
            "exit": "close_at_signal_plus_10_SPY_sessions",
            "event_sleeve_target": EVENT_SLEEVE_TARGET,
            "single_name_cap": SINGLE_NAME_CAP,
            "gross_cap": GROSS_CAP,
            "within_event_allocation": "equal_before_single_name_cap",
            "unallocated_sleeve_stays_cash": True,
            "upstream_rank_changes_weight": False,
        },
        "cost_models": COST_MODELS,
        "sector_classification_status": "NOT_IN_FROZEN_CANDIDATE_CONTRACT",
        "market_data_sources": market_sources,
        "portfolios": portfolios,
        "immutable_recompute_discrepancies": discrepancies,
        "guardrails": {
            "may_change_production": False,
            "automatic_stock_selection": False,
            "rank_recomputed": False,
            "historical_results_count_as_forward_oos": False,
            "historical_candidate_backfill_allowed": False,
            "automatic_promotion": False,
            "broker_orders_enabled": False,
            "nearest_date_alignment_allowed": False,
        },
        "warnings": [
            "This is a prospective individual-stock paper ledger; no brokerage orders are enabled.",
            "Candidates are accepted only from the exact-date Frozen V4 x Task 1/4 adapter trade pool.",
            "Insufficient candidate count leaves sleeve capital in cash; weights are never expanded to fill 25%.",
            "25bp round-trip is the primary paper execution assumption and 50bp is a stress case; neither is a calibrated broker fill model.",
            "Point-in-time sector classification is not inferred in V1.",
        ],
    }
    atomic_write_json(OUT, out)
    return out


def main():
    adapter = load_json(SOURCE)
    if adapter.get("schema") != "TASK14-STAGE4-STOCK-CANDIDATE-ADAPTER-V1":
        raise RuntimeError("unexpected stock candidate adapter schema")
    if adapter.get("frozen_through_market_date") != FROZEN_THROUGH:
        raise RuntimeError("stock candidate adapter freeze boundary mismatch")

    existing = load_existing()
    old_map = existing_decision_map(existing)
    now = now_utc()
    candidates = collect_trade_pool(adapter)

    upstream_count = int((adapter.get("adapter") or {}).get("trade_pool_eligible_count") or 0)
    if len(candidates) != upstream_count:
        raise RuntimeError(f"adapter trade-pool count mismatch: adapter={upstream_count} rebuilt={len(candidates)}")

    if not candidates:
        if old_map:
            raise RuntimeError("upstream trade-pool candidates disappeared while immutable paper decisions already exist")
        latest = adapter.get("latest_upstream_market_date")
        portfolios = empty_portfolios(latest)
        out = write_output(
            adapter,
            [],
            portfolios,
            [],
            {"market_data_fetch": "skipped_zero_trade_pool_candidates"},
            latest,
            now,
        )
        print(json.dumps({
            "status": "EMPTY_FORWARD_LEDGER",
            "trade_pool_candidates": 0,
            "latest_complete_market_date": latest,
            "market_data_fetch": "skipped_zero_trade_pool_candidates",
            "discrepancies": 0,
        }, ensure_ascii=False, indent=2))
        return

    symbols = sorted({c["symbol"] for c in candidates})
    data = {}
    sources = {}
    spy_rows, spy_source = market.fetch_symbol("SPY")
    data["SPY"] = drop_current_utc_session(spy_rows)
    sources["SPY"] = spy_source
    for symbol in symbols:
        rows, src = market.fetch_symbol(symbol)
        data[symbol] = drop_current_utc_session(rows)
        sources[symbol] = src

    if not data["SPY"]:
        raise RuntimeError("no complete SPY sessions available")

    events = prepare_events(candidates, data)
    portfolios = {
        name: simulate(data, events, name, old_map, now)
        for name in COST_MODELS
    }
    discrepancies = compare_existing(existing, portfolios)
    if discrepancies:
        raise RuntimeError(f"immutable stock paper discrepancy: {discrepancies[:5]}")

    latest = data["SPY"][-1]["date"]
    out = write_output(adapter, candidates, portfolios, discrepancies, sources, latest, now)
    print(json.dumps({
        "status": "READY",
        "trade_pool_candidates": len(candidates),
        "event_dates": len(events),
        "latest_complete_market_date": latest,
        "portfolios": {
            name: {
                "decisions": len(p["candidate_decisions"]),
                "realized": len(p["realized_positions"]),
                "open": len(p["open_positions"]),
                "pending_events": p["pending_event_count"],
                "equity": p["latest_equity_usd"],
                "max_adv_participation_pct": p["max_adv_participation_pct"],
            }
            for name, p in portfolios.items()
        },
        "discrepancies": len(discrepancies),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
