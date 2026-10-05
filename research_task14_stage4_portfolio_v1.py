from __future__ import annotations

import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median, stdev

import requests

import build_market_state_sequence_v1 as seq
import build_task14_challenger_forward_oos_v1 as ch

ROOT = Path(__file__).resolve().parent
STATE = ROOT / 'docs/data/market_state_box_v1.json'
EVENT_AUDIT = ROOT / 'docs/data/market_state_sequence_event_audit_v1.json'
OUT = ROOT / 'docs/data/task14_stage4_portfolio_v1.json'
SPEC = 'research/task14_stage4_portfolio_v1/STUDY_SPEC.md'
FROZEN_THROUGH = '2026-10-02'
FULL_FLAG = 'D_TO_BOTH_REBOUND_SCORE'
HOLD_SIGNAL_SESSIONS = 10
START_CAPITAL = 100_000.0
CAPITAL_SWEEP = (100_000.0, 1_000_000.0, 10_000_000.0, 100_000_000.0)
SQRT252 = math.sqrt(252.0)

POLICIES = {
    'full_only_100_dedup': {
        'families': {'full_sequence'}, 'dedup': True, 'sizing': 'full', 'gross_cap': 1.0,
    },
    'early_full_100_dedup': {
        'families': {'early_sequence', 'full_sequence'}, 'dedup': True, 'sizing': 'full', 'gross_cap': 1.0,
    },
    'early_full_vol10_dedup': {
        'families': {'early_sequence', 'full_sequence'}, 'dedup': True, 'sizing': 'vol10', 'gross_cap': 1.0,
    },
    'early_full_stack25_cap100': {
        'families': {'early_sequence', 'full_sequence'}, 'dedup': False, 'sizing': 'sleeve25', 'gross_cap': 1.0,
    },
}
COST_MODELS = ('fixed_10bps_rt', 'square_root_impact')


def num(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def fetch_spy():
    headers = {'User-Agent': 'Mozilla/5.0 Market-Structure-Lab/Stage4-Portfolio-V1'}
    errors = []
    for host in ('query1.finance.yahoo.com', 'query2.finance.yahoo.com'):
        url = f'https://{host}/v8/finance/chart/SPY?range=10y&interval=1d&events=history&includeAdjustedClose=true'
        for attempt in range(2):
            try:
                r = requests.get(url, headers=headers, timeout=20)
                r.raise_for_status()
                obj = r.json()['chart']['result'][0]
                ts = obj.get('timestamp') or []
                q = ((obj.get('indicators') or {}).get('quote') or [{}])[0]
                rows = []
                for t, o, c, v in zip(ts, q.get('open') or [], q.get('close') or [], q.get('volume') or []):
                    o, c, v = num(o), num(c), num(v)
                    if o is None or c is None or v is None:
                        continue
                    rows.append({
                        'date': datetime.fromtimestamp(int(t), tz=timezone.utc).strftime('%Y-%m-%d'),
                        'open': o, 'close': c, 'volume': v,
                    })
                if len(rows) < 2000:
                    raise RuntimeError(f'short SPY history: {len(rows)}')
                return rows, {'host': host, 'rows': len(rows), 'transport': 'yahoo_chart_range_10y'}
            except Exception as exc:
                errors.append(f'{host}:{type(exc).__name__}:{exc}')
                time.sleep(1 + attempt)
    raise RuntimeError(' | '.join(errors))


def build_state_rows():
    src = json.loads(STATE.read_text(encoding='utf-8'))
    rows = [dict(r) for r in (src.get('daily') or [])]
    if len(rows) < 2000:
        raise RuntimeError('Market State Box V1 daily history missing/too short')
    rows = seq.add_dual(rows)
    rows, _ = seq.enrich_sequence(rows)
    return rows


def trailing_context(spy, i):
    dv = [r['close'] * r['volume'] for r in spy[max(0, i - 19):i + 1] if r.get('volume') is not None]
    adv20 = mean(dv) if dv else None
    rets = []
    for j in range(max(1, i - 19), i + 1):
        c0, c1 = spy[j - 1]['close'], spy[j]['close']
        if c0:
            rets.append(c1 / c0 - 1.0)
    sigma = stdev(rets) if len(rets) >= 10 else None
    return adv20, None if sigma is None else sigma * 10000.0, None if sigma is None else sigma * SQRT252


def build_historical_signals(rows, spy):
    sidx = {r['date']: i for i, r in enumerate(spy)}
    early_pred = lambda r: bool(r.get('D_TO_BREADTH_LOW')) and bool(r.get('box_bottom_since_dual')) and bool(r.get('breadth_rebound_since_dual'))
    early_ix = ch.event_onsets_predicate(rows, early_pred)
    full_onsets = seq.event_onsets(rows, FULL_FLAG)
    full_ix = [r.get('_i') for r in full_onsets if isinstance(r.get('_i'), int)]
    if len(early_ix) != 15:
        raise RuntimeError(f'expected 15 historical Early Sequence events, got {len(early_ix)}')
    if len(full_ix) != 12:
        raise RuntimeError(f'expected 12 historical Full Sequence events, got {len(full_ix)}')
    frozen_audit = json.loads(EVENT_AUDIT.read_text(encoding='utf-8'))
    frozen_dates = [e['date'] for e in (frozen_audit.get('events') or [])]
    rebuilt_dates = [rows[i]['date'] for i in full_ix]
    if rebuilt_dates != frozen_dates:
        raise RuntimeError(f'Full Sequence deterministic replay mismatch rebuilt={rebuilt_dates} frozen={frozen_dates}')

    raw = []
    for family, idxs in (('early_sequence', early_ix), ('full_sequence', full_ix)):
        for i in idxs:
            d = rows[i]['date']
            si = sidx.get(d)
            if si is None or si + HOLD_SIGNAL_SESSIONS >= len(spy) or si + 1 >= len(spy):
                raise RuntimeError(f'SPY execution history missing/not mature for {family} {d}')
            adv20, sigma_bps, ann_vol = trailing_context(spy, si)
            if adv20 in (None, 0) or sigma_bps in (None, 0) or ann_vol in (None, 0):
                raise RuntimeError(f'missing execution context for {family} {d}')
            raw.append({
                'family': family,
                'signal_date': d,
                'signal_spy_index': si,
                'entry_spy_index': si + 1,
                'entry_date': spy[si + 1]['date'],
                'exit_spy_index': si + HOLD_SIGNAL_SESSIONS,
                'exit_date': spy[si + HOLD_SIGNAL_SESSIONS]['date'],
                'signal_close': round(spy[si]['close'], 6),
                'entry_open': round(spy[si + 1]['open'], 6),
                'exit_close': round(spy[si + HOLD_SIGNAL_SESSIONS]['close'], 6),
                'adv20_usd': round(adv20, 2),
                'sigma20_daily_bps': round(sigma_bps, 6),
                'annualized_vol20': round(ann_vol, 8),
            })
    priority = {'full_sequence': 0, 'early_sequence': 1}
    raw.sort(key=lambda x: (x['signal_spy_index'], priority[x['family']]))
    return raw


def dynamic_rt_cost_bps(signal, notional):
    adv = float(signal['adv20_usd'])
    sigma = float(signal['sigma20_daily_bps'])
    participation = 0.0 if notional <= 0 else notional / adv
    return 1.0 + sigma * math.sqrt(max(0.0, participation)), participation


def rt_cost(signal, notional, model):
    if model == 'fixed_10bps_rt':
        return 10.0, notional / float(signal['adv20_usd'])
    if model == 'square_root_impact':
        return dynamic_rt_cost_bps(signal, notional)
    raise ValueError(model)


def capacity_thresholds(signal):
    sigma = float(signal['sigma20_daily_bps'])
    adv = float(signal['adv20_usd'])
    out = {}
    for bps in (10, 25, 50):
        participation = ((bps - 1.0) / sigma) ** 2 if sigma > 0 and bps > 1 else 0.0
        out[str(bps)] = {
            'participation_pct_adv': round(participation * 100.0, 6),
            'notional_usd': round(participation * adv, 2),
            'within_10pct_adv_model_domain': participation <= 0.10,
        }
    return out


def desired_fraction(policy, signal):
    if policy['sizing'] == 'full':
        return 1.0
    if policy['sizing'] == 'sleeve25':
        return 0.25
    if policy['sizing'] == 'vol10':
        av = float(signal['annualized_vol20'])
        return min(1.0, 0.10 / av) if av > 0 else 0.0
    raise ValueError(policy['sizing'])


def select_signals_for_policy(signals, policy):
    eligible = [s for s in signals if s['family'] in policy['families']]
    if not policy['dedup']:
        return eligible, []
    accepted, skipped = [], []
    active_until = -1
    for s in eligible:
        # Signal is observed at the close. A position exiting at that same close is no longer active for the next-open decision.
        if s['signal_spy_index'] < active_until:
            skipped.append({'signal_date': s['signal_date'], 'family': s['family'], 'reason': 'active_same_instrument_position_at_signal_close'})
            continue
        accepted.append(s)
        active_until = s['exit_spy_index']
    return accepted, skipped


def solve_entry_notional(cash, equity_open, gross_open, desired_frac, gross_cap, signal, cost_model):
    if equity_open <= 0 or desired_frac <= 0:
        return 0.0, 0.0, 0.0
    n = min(desired_frac * equity_open, max(0.0, gross_cap * equity_open - gross_open), max(0.0, cash))
    cost_bps = 0.0
    participation = 0.0
    for _ in range(6):
        if n <= 0:
            return 0.0, 0.0, 0.0
        cost_bps, participation = rt_cost(signal, n, cost_model)
        half = cost_bps / 20000.0
        # Desired fraction and gross cap are enforced after charging the entry half-cost.
        target_limit = desired_frac * equity_open / (1.0 + desired_frac * half)
        cap_room_numerator = max(0.0, gross_cap * equity_open - gross_open)
        cap_limit = cap_room_numerator / (1.0 + gross_cap * half)
        cash_limit = max(0.0, cash) / (1.0 + half)
        n2 = min(target_limit, cap_limit, cash_limit)
        if abs(n2 - n) <= max(0.01, n * 1e-10):
            n = n2
            break
        n = n2
    cost_bps, participation = rt_cost(signal, n, cost_model) if n > 0 else (0.0, 0.0)
    return n, cost_bps, participation


def simulate(spy, signals, policy_name, cost_model, start_capital=START_CAPITAL, keep_curve=True):
    policy = POLICIES[policy_name]
    selected, prereg_skipped = select_signals_for_policy(signals, policy)
    by_entry = {}
    for s in selected:
        by_entry.setdefault(s['entry_spy_index'], []).append(s)

    cash = float(start_capital)
    lots, trades = [], []
    skipped = list(prereg_skipped)
    curve, total_cost, turnover = [], 0.0, 0.0
    exposure_days, daily_gross = 0, []

    for i, bar in enumerate(spy):
        open_px, close_px = bar['open'], bar['close']
        for sig in by_entry.get(i, []):
            equity_open = cash + sum(x['shares'] * open_px for x in lots)
            gross_open = sum(abs(x['shares'] * open_px) for x in lots)
            frac = desired_fraction(policy, sig)
            notional, cost_bps, participation = solve_entry_notional(
                cash, equity_open, gross_open, frac, policy['gross_cap'], sig, cost_model
            )
            if notional <= max(1.0, equity_open * 1e-8):
                skipped.append({'signal_date': sig['signal_date'], 'family': sig['family'], 'reason': 'gross_cap_cash_or_zero_target_at_entry'})
                continue
            half_rate = cost_bps / 20000.0
            entry_cost = notional * half_rate
            shares = notional / open_px
            cash -= notional + entry_cost
            total_cost += entry_cost
            turnover += notional
            lots.append({
                'family': sig['family'], 'signal_date': sig['signal_date'], 'entry_date': bar['date'],
                'entry_idx': i, 'exit_idx': sig['exit_spy_index'], 'entry_open': open_px,
                'shares': shares, 'entry_notional': notional, 'estimated_rt_cost_bps': cost_bps,
                'adv_participation': participation, 'entry_cost_usd': entry_cost,
            })

        if lots:
            exposure_days += 1

        survivors = []
        for lot in lots:
            if lot['exit_idx'] == i:
                exit_value = lot['shares'] * close_px
                exit_cost = exit_value * lot['estimated_rt_cost_bps'] / 20000.0
                cash += exit_value - exit_cost
                total_cost += exit_cost
                turnover += exit_value
                pnl = (exit_value - exit_cost) - (lot['entry_notional'] + lot['entry_cost_usd'])
                trades.append({
                    'family': lot['family'], 'signal_date': lot['signal_date'], 'entry_date': lot['entry_date'],
                    'exit_date': bar['date'], 'entry_open': round(lot['entry_open'], 6), 'exit_close': round(close_px, 6),
                    'entry_notional_usd': round(lot['entry_notional'], 2),
                    'estimated_rt_cost_bps': round(lot['estimated_rt_cost_bps'], 6),
                    'adv_participation_pct': round(lot['adv_participation'] * 100.0, 8),
                    'net_pnl_usd': round(pnl, 2),
                    'net_return_pct_on_entry_notional': round(100.0 * pnl / lot['entry_notional'], 6),
                })
            else:
                survivors.append(lot)
        lots = survivors

        equity_close = cash + sum(x['shares'] * close_px for x in lots)
        gross_close = sum(abs(x['shares'] * close_px) for x in lots)
        gross_frac = 0.0 if equity_close == 0 else gross_close / equity_close
        if gross_frac > policy['gross_cap'] + 1e-6:
            raise RuntimeError(f'gross cap violation {policy_name} {bar["date"]}: {gross_frac}')
        daily_gross.append(gross_frac)
        curve.append({'date': bar['date'], 'equity': round(equity_close, 4), 'gross_exposure': round(gross_frac, 8)})

    if lots:
        raise RuntimeError(f'unclosed lots remain for {policy_name}/{cost_model}: {len(lots)}')
    final_equity = cash
    peak, max_dd = -float('inf'), 0.0
    for r in curve:
        peak = max(peak, r['equity'])
        if peak > 0:
            max_dd = min(max_dd, r['equity'] / peak - 1.0)
    costs_bps = [t['estimated_rt_cost_bps'] for t in trades]
    parts = [t['adv_participation_pct'] for t in trades]
    wins = [t['net_pnl_usd'] > 0 for t in trades]
    return {
        'policy': policy_name,
        'cost_model': cost_model,
        'start_capital_usd': start_capital,
        'final_equity_usd': round(final_equity, 2),
        'total_return_pct': round(100.0 * (final_equity / start_capital - 1.0), 6),
        'max_drawdown_pct': round(100.0 * max_dd, 6),
        'eligible_signal_count': len([s for s in signals if s['family'] in policy['families']]),
        'preregistered_selected_signal_count': len(selected),
        'trade_count': len(trades),
        'skipped_signal_count': len(skipped),
        'skipped_overlap_count': sum(x['reason'] == 'active_same_instrument_position_at_signal_close' for x in skipped),
        'skipped_signals': skipped,
        'exposure_day_pct': round(100.0 * exposure_days / len(spy), 4),
        'average_gross_exposure': round(mean(daily_gross), 6),
        'max_gross_exposure': round(max(daily_gross), 6),
        'market_beta_proxy_average_exposure': round(mean(daily_gross), 6),
        'turnover_multiple_start_capital': round(turnover / start_capital, 6),
        'total_modeled_cost_usd': round(total_cost, 2),
        'total_modeled_cost_bps_start_capital': round(10000.0 * total_cost / start_capital, 6),
        'average_modeled_rt_cost_bps': None if not costs_bps else round(mean(costs_bps), 6),
        'max_adv_participation_pct': None if not parts else round(max(parts), 8),
        'trade_win_rate_pct': None if not wins else round(100.0 * sum(wins) / len(wins), 2),
        'sector_exposure_classification': 'broad_market_spy_only',
        'trades': trades,
        'equity_curve': curve if keep_curve else None,
    }


def summarize_capacity(signals):
    rows = [{
        'family': s['family'], 'signal_date': s['signal_date'], 'adv20_usd': s['adv20_usd'],
        'sigma20_daily_bps': s['sigma20_daily_bps'], 'thresholds': capacity_thresholds(s),
    } for s in signals]
    summary = {}
    for bps in (10, 25, 50):
        vals = [r['thresholds'][str(bps)]['notional_usd'] for r in rows]
        parts = [r['thresholds'][str(bps)]['participation_pct_adv'] for r in rows]
        summary[str(bps)] = {
            'median_notional_usd': round(median(vals), 2), 'min_notional_usd': round(min(vals), 2),
            'max_notional_usd': round(max(vals), 2), 'median_participation_pct_adv': round(median(parts), 6),
        }
    return rows, summary


def main():
    rows = build_state_rows()
    spy, source = fetch_spy()
    signals = build_historical_signals(rows, spy)
    cap_rows, cap_summary = summarize_capacity(signals)

    primary = {}
    for policy_name in POLICIES:
        primary[policy_name] = {}
        for cost_model in COST_MODELS:
            primary[policy_name][cost_model] = simulate(spy, signals, policy_name, cost_model, START_CAPITAL, keep_curve=True)

    sweep = {}
    for capital in CAPITAL_SWEEP:
        sweep[str(int(capital))] = simulate(spy, signals, 'early_full_vol10_dedup', 'square_root_impact', capital, keep_curve=False)

    out = {
        'schema': 'TASK14-STAGE4-PORTFOLIO-V1',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'research_only': True, 'diagnostic_only': True, 'production_effect': 'none',
        'thresholds_changed': False, 'broker_orders_enabled': False,
        'frozen_through_market_date': FROZEN_THROUGH, 'study_spec': SPEC,
        'instrument': 'SPY', 'source': source,
        'historical_signal_counts': {
            'early_sequence': sum(s['family'] == 'early_sequence' for s in signals),
            'full_sequence': sum(s['family'] == 'full_sequence' for s in signals),
            'combined_records': len(signals),
        },
        'execution_convention': {
            'entry': 'next_regular_session_open',
            'primary_exit': 'close_at_signal_plus_10_trading_sessions',
            'same_day_priority': ['full_sequence', 'early_sequence'],
            'dedup_decision_time': 'signal_close',
        },
        'cost_models': {
            'fixed_10bps_rt': '10 bp round trip; half at entry and half at exit',
            'square_root_impact': '1 bp round-trip floor + sigma20_daily_bps * sqrt(notional/ADV20); half charged each side',
        },
        'policies': POLICIES, 'signals': signals,
        'capacity_thresholds_by_signal': cap_rows, 'capacity_threshold_summary': cap_summary,
        'primary_start_capital_usd': START_CAPITAL, 'portfolio_results': primary,
        'capital_scale_sweep': sweep,
        'exposure_interpretation': {
            'market_beta_proxy': 'gross SPY exposure fraction by construction',
            'sector_exposure': 'broad-market SPY only; historical sector decomposition intentionally not inferred',
        },
        'guardrails': {
            'may_change_production': False, 'may_change_signal_definition': False,
            'historical_results_count_as_forward_oos': False, 'automatic_promotion': False,
            'broker_orders_enabled': False,
        },
        'warnings': [
            'Early Sequence and Full Sequence historical portfolio tests are post-discovery diagnostics, not independent OOS evidence.',
            'The square-root impact model is a stress envelope, not a calibrated broker fill model.',
            'SPY-only V1 cannot estimate true stock-level sector concentration or stock-specific capacity.',
            'Portfolio-policy comparisons are not a parameter search and do not select a production winner.',
        ],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({
        'source': source, 'signal_counts': out['historical_signal_counts'], 'capacity': cap_summary,
        'results': {p: {c: {
            'return_pct': primary[p][c]['total_return_pct'], 'max_dd_pct': primary[p][c]['max_drawdown_pct'],
            'trades': primary[p][c]['trade_count'], 'skipped_overlap': primary[p][c]['skipped_overlap_count'],
            'avg_exposure': primary[p][c]['average_gross_exposure'],
            'avg_cost_bps': primary[p][c]['average_modeled_rt_cost_bps'],
        } for c in COST_MODELS} for p in POLICIES},
        'capital_sweep': {k: {
            'return_pct': v['total_return_pct'], 'avg_cost_bps': v['average_modeled_rt_cost_bps'],
            'max_participation_pct': v['max_adv_participation_pct'],
        } for k, v in sweep.items()},
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
