from __future__ import annotations

import csv
import io
import json
import math
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median, stdev

import requests

import build_market_state_sequence_v1 as seq
import build_task14_challenger_forward_oos_v1 as ch

ROOT = Path(__file__).resolve().parent
STATE = ROOT / 'docs/data/market_state_box_v1.json'
OUT = ROOT / 'docs/data/task14_stage4_multiasset_v1.json'
SPEC = 'research/task14_stage4_multiasset_v1/STUDY_SPEC.md'
FROZEN_THROUGH = '2026-10-02'
HOLD_SIGNAL_SESSIONS = 10
START_CAPITAL = 100_000.0
CAPITAL_SWEEP = (100_000.0, 1_000_000.0, 10_000_000.0, 100_000_000.0)
SQRT252 = math.sqrt(252.0)

ASSETS = {
    'XLC': 'Communication Services',
    'XLY': 'Consumer Discretionary',
    'XLP': 'Consumer Staples',
    'XLE': 'Energy',
    'XLF': 'Financials',
    'XLV': 'Health Care',
    'XLI': 'Industrials',
    'XLB': 'Materials',
    'XLRE': 'Real Estate',
    'XLK': 'Technology',
    'XLU': 'Utilities',
}
BENCHMARK = 'SPY'
ALL_SYMBOLS = (BENCHMARK, *ASSETS.keys())

POLICIES = {
    'full_eq_sector_100_dedup': {
        'families': {'full_sequence'}, 'dedup': True, 'sleeve_fraction': 1.0, 'allocation': 'equal', 'gross_cap': 1.0,
    },
    'full_invvol_sector_100_dedup': {
        'families': {'full_sequence'}, 'dedup': True, 'sleeve_fraction': 1.0, 'allocation': 'invvol', 'gross_cap': 1.0,
    },
    'early_full_stack25_invvol_cap100': {
        'families': {'early_sequence', 'full_sequence'}, 'dedup': False, 'sleeve_fraction': 0.25, 'allocation': 'invvol', 'gross_cap': 1.0,
    },
    'early_full_stack25_beta100_cap100': {
        'families': {'early_sequence', 'full_sequence'}, 'dedup': False, 'sleeve_fraction': 0.25, 'allocation': 'invvol_beta100', 'gross_cap': 1.0,
    },
}
COST_MODELS = ('fixed_10bps_rt', 'square_root_impact')


def num(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def fetch_yahoo(symbol):
    headers = {'User-Agent': 'Mozilla/5.0 Market-Structure-Lab/Task14-MultiAsset-V1'}
    errors = []
    for host in ('query1.finance.yahoo.com', 'query2.finance.yahoo.com'):
        url = f'https://{host}/v8/finance/chart/{symbol}?range=10y&interval=1d&events=history&includeAdjustedClose=true'
        for attempt in range(2):
            try:
                r = requests.get(url, headers=headers, timeout=25)
                r.raise_for_status()
                result = (r.json().get('chart') or {}).get('result') or []
                if not result:
                    raise RuntimeError('empty chart result')
                obj = result[0]
                ts = obj.get('timestamp') or []
                q = ((obj.get('indicators') or {}).get('quote') or [{}])[0]
                rows = []
                for t, o, h, l, c, v in zip(ts, q.get('open') or [], q.get('high') or [], q.get('low') or [], q.get('close') or [], q.get('volume') or []):
                    o, h, l, c, v = num(o), num(h), num(l), num(c), num(v)
                    if o is None or c is None:
                        continue
                    rows.append({'date': datetime.fromtimestamp(int(t), tz=timezone.utc).strftime('%Y-%m-%d'), 'open': o, 'high': h, 'low': l, 'close': c, 'volume': v})
                if len(rows) < 1500:
                    raise RuntimeError(f'short history: {len(rows)}')
                return rows, {'provider': 'yahoo_chart', 'host': host, 'rows': len(rows)}
            except Exception as exc:
                errors.append(f'{host}:{type(exc).__name__}:{exc}')
                time.sleep(0.7 + attempt)
    raise RuntimeError(' | '.join(errors))


def fetch_stooq(symbol):
    url = f'https://stooq.com/q/d/l/?s={symbol.lower()}.us&d1=20160101&d2=20261231&i=d'
    r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 Market-Structure-Lab/Task14-MultiAsset-V1'}, timeout=30)
    r.raise_for_status()
    rows = []
    for x in csv.DictReader(io.StringIO(r.text)):
        d = x.get('Date')
        o, h, l, c, v = (num(x.get(k)) for k in ('Open', 'High', 'Low', 'Close', 'Volume'))
        if not d or o is None or c is None:
            continue
        rows.append({'date': d, 'open': o, 'high': h, 'low': l, 'close': c, 'volume': v})
    if len(rows) < 1500:
        raise RuntimeError(f'short Stooq history for {symbol}: {len(rows)}')
    rows.sort(key=lambda z: z['date'])
    return rows, {'provider': 'stooq_csv', 'host': 'stooq.com', 'rows': len(rows)}


def fetch_symbol(symbol):
    errors = []
    try:
        return fetch_yahoo(symbol)
    except Exception as exc:
        errors.append(f'yahoo:{exc}')
    try:
        return fetch_stooq(symbol)
    except Exception as exc:
        errors.append(f'stooq:{exc}')
    raise RuntimeError(f"unable to fetch {symbol}: {' | '.join(errors)}")


def fetch_universe():
    data, sources = {}, {}
    for symbol in ALL_SYMBOLS:
        rows, src = fetch_symbol(symbol)
        data[symbol] = rows
        sources[symbol] = src
        time.sleep(0.25)
    return data, sources


def build_state_rows():
    src = json.loads(STATE.read_text(encoding='utf-8'))
    rows = [dict(r) for r in (src.get('daily') or [])]
    if len(rows) < 2000:
        raise RuntimeError('Market State Box V1 daily history missing/too short')
    rows = seq.add_dual(rows)
    rows, _ = seq.enrich_sequence(rows)
    return rows


def returns_map(rows):
    out = {}
    for i in range(1, len(rows)):
        c0, c1 = rows[i - 1]['close'], rows[i]['close']
        if c0 not in (None, 0) and c1 is not None:
            out[rows[i]['date']] = c1 / c0 - 1.0
    return out


def trailing_asset_context(symbol, data, benchmark, signal_date):
    rows = data[symbol]
    idx = {r['date']: i for i, r in enumerate(rows)}
    i = idx.get(signal_date)
    if i is None or i < 60:
        return None
    win = rows[max(0, i - 19):i + 1]
    dvs = [r['close'] * r['volume'] for r in win if r.get('volume') not in (None, 0)]
    rets = []
    for j in range(max(1, i - 19), i + 1):
        c0, c1 = rows[j - 1]['close'], rows[j]['close']
        if c0:
            rets.append(c1 / c0 - 1.0)
    if len(rets) < 10 or not dvs:
        return None
    sigma = stdev(rets)
    if sigma <= 0:
        return None
    asset_r = returns_map(rows)
    spy_r = returns_map(benchmark)
    dates = sorted(d for d in asset_r if d <= signal_date and d in spy_r)[-60:]
    if len(dates) < 40:
        return None
    a = [asset_r[d] for d in dates]
    b = [spy_r[d] for d in dates]
    ma, mb = mean(a), mean(b)
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b)) / max(1, len(a) - 1)
    varb = sum((y - mb) ** 2 for y in b) / max(1, len(b) - 1)
    beta = None if varb <= 0 else cov / varb
    if beta is None or not math.isfinite(beta):
        return None
    return {'adv20_usd': mean(dvs), 'sigma20_daily_bps': sigma * 10000.0, 'annualized_vol20': sigma * SQRT252, 'beta60': beta}


def capped_weights(raw, cap=0.20):
    raw = {k: max(0.0, float(v)) for k, v in raw.items() if num(v) is not None and float(v) > 0}
    if not raw:
        return {}
    remaining = set(raw)
    weights = {k: 0.0 for k in raw}
    left = 1.0
    while remaining and left > 1e-12:
        total = sum(raw[k] for k in remaining)
        if total <= 0:
            share = left / len(remaining)
            for k in remaining:
                weights[k] += min(cap - weights[k], share)
            break
        capped = []
        for k in list(remaining):
            target = left * raw[k] / total
            room = cap - weights[k]
            if target >= room - 1e-12:
                weights[k] += max(0.0, room)
                left -= max(0.0, room)
                capped.append(k)
        if capped:
            for k in capped:
                remaining.discard(k)
            continue
        for k in remaining:
            weights[k] += left * raw[k] / total
        left = 0.0
    s = sum(weights.values())
    return {} if s <= 0 else {k: v / s for k, v in weights.items()}


def allocation_from_context(context, mode):
    eligible = {s: c for s, c in context.items() if c}
    if len(eligible) < 8:
        return None
    raw = {s: 1.0 for s in eligible} if mode == 'equal' else {s: 1.0 / c['annualized_vol20'] for s, c in eligible.items() if c['annualized_vol20'] > 0}
    weights = capped_weights(raw, 0.20)
    beta = sum(weights[s] * eligible[s]['beta60'] for s in weights)
    gross_scale = 1.0
    if mode == 'invvol_beta100' and beta > 1.0:
        gross_scale = 1.0 / beta
    return {'weights': weights, 'portfolio_beta_pre_scale': beta, 'gross_scale': gross_scale, 'portfolio_beta_post_scale': beta * gross_scale}


def exact_bar(rows, date):
    for r in rows:
        if r['date'] == date:
            return r
    return None


def build_historical_signals(state_rows, data):
    spy = data[BENCHMARK]
    sidx = {r['date']: i for i, r in enumerate(spy)}
    early_pred = lambda r: bool(r.get('D_TO_BREADTH_LOW')) and bool(r.get('box_bottom_since_dual')) and bool(r.get('breadth_rebound_since_dual'))
    early_ix = ch.event_onsets_predicate(state_rows, early_pred)
    full_onsets = seq.event_onsets(state_rows, 'D_TO_BOTH_REBOUND_SCORE')
    full_ix = [r.get('_i') for r in full_onsets if isinstance(r.get('_i'), int)]
    if len(early_ix) != 15:
        raise RuntimeError(f'expected 15 Early Sequence events, got {len(early_ix)}')
    if len(full_ix) != 12:
        raise RuntimeError(f'expected 12 Full Sequence events, got {len(full_ix)}')
    out = []
    for family, idxs in (('early_sequence', early_ix), ('full_sequence', full_ix)):
        for ri in idxs:
            d = state_rows[ri]['date']
            si = sidx.get(d)
            if si is None or si + 1 >= len(spy) or si + HOLD_SIGNAL_SESSIONS >= len(spy):
                raise RuntimeError(f'SPY not mature for {family} {d}')
            entry_date = spy[si + 1]['date']
            exit_date = spy[si + HOLD_SIGNAL_SESSIONS]['date']
            context, prices = {}, {}
            for symbol in ASSETS:
                c = trailing_asset_context(symbol, data, spy, d)
                b0 = exact_bar(data[symbol], d)
                b1 = exact_bar(data[symbol], entry_date)
                bx = exact_bar(data[symbol], exit_date)
                if c and b0 and b1 and bx:
                    context[symbol] = c
                    prices[symbol] = {'signal_close': b0['close'], 'entry_open': b1['open'], 'exit_close': bx['close']}
            if len(context) < 8:
                raise RuntimeError(f'insufficient eligible sector ETFs for {family} {d}: {len(context)}')
            out.append({
                'family': family, 'signal_date': d, 'signal_spy_index': si, 'entry_spy_index': si + 1, 'entry_date': entry_date,
                'exit_spy_index': si + HOLD_SIGNAL_SESSIONS, 'exit_date': exit_date, 'context': context, 'prices': prices,
                'allocations': {
                    'equal': allocation_from_context(context, 'equal'),
                    'invvol': allocation_from_context(context, 'invvol'),
                    'invvol_beta100': allocation_from_context(context, 'invvol_beta100'),
                },
            })
    priority = {'full_sequence': 0, 'early_sequence': 1}
    out.sort(key=lambda x: (x['signal_date'], priority[x['family']]))
    return out


def rt_cost_bps(context, notional, model):
    if model == 'fixed_10bps_rt':
        return 10.0, notional / context['adv20_usd']
    participation = 0.0 if notional <= 0 else notional / context['adv20_usd']
    return 1.0 + context['sigma20_daily_bps'] * math.sqrt(max(0.0, participation)), participation


def sleeve_cost_for_gross(sig, alloc, gross, model):
    total, details = 0.0, {}
    for symbol, w in alloc['weights'].items():
        n = gross * w
        bps, part = rt_cost_bps(sig['context'][symbol], n, model)
        entry_cost = n * (bps / 20000.0)
        total += entry_cost
        details[symbol] = {'weight': w, 'notional': n, 'rt_cost_bps': bps, 'participation': part, 'entry_cost': entry_cost}
    return total, details


def fit_gross_to_cash(sig, alloc, gross_target, cash_available, model):
    hi, lo = max(0.0, min(gross_target, cash_available)), 0.0
    for _ in range(28):
        mid = (lo + hi) / 2.0
        cost, _ = sleeve_cost_for_gross(sig, alloc, mid, model)
        if mid + cost <= cash_available:
            lo = mid
        else:
            hi = mid
    cost, details = sleeve_cost_for_gross(sig, alloc, lo, model)
    return lo, cost, details


def asof_close(data, symbol, date, caches):
    cache = caches[symbol]
    if date in cache:
        return cache[date]
    value = None
    for r in data[symbol]:
        if r['date'] > date:
            break
        value = r['close']
    cache[date] = value
    return value


def simulate(data, signals, policy_name, cost_model, start_capital=START_CAPITAL, keep_curve=True):
    spy = data[BENCHMARK]
    policy = POLICIES[policy_name]
    signals = [s for s in signals if s['family'] in policy['families']]
    by_signal = defaultdict(list)
    for s in signals:
        by_signal[s['signal_spy_index']].append(s)
    priority = {'full_sequence': 0, 'early_sequence': 1}
    for k in by_signal:
        by_signal[k].sort(key=lambda x: priority[x['family']])
    cash = float(start_capital)
    pending, sleeves, closed_sleeves, skipped, curve = [], [], [], [], []
    caches = {s: {} for s in ASSETS}
    exposure_days = 0
    gross_series, beta_series, max_sector_series, hhi_series = [], [], [], []
    turnover, total_cost, max_participation = 0.0, 0.0, 0.0
    all_cost_bps = []

    def active_or_pending_after_close(signal_idx):
        return any(x['exit_idx'] > signal_idx for x in sleeves) or any(x['signal_idx'] >= signal_idx for x in pending)

    for i, bar in enumerate(spy):
        date = bar['date']
        entrants = [x for x in pending if x['entry_idx'] == i]
        pending = [x for x in pending if x['entry_idx'] != i]
        for item in entrants:
            sig = item['signal']
            alloc = sig['allocations'][policy['allocation']]
            equity_open, gross_open = cash, 0.0
            for sl in sleeves:
                for leg in sl['legs'].values():
                    b = exact_bar(data[leg['symbol']], date)
                    px = b['open'] if b else asof_close(data, leg['symbol'], date, caches)
                    equity_open += leg['shares'] * px
                    gross_open += abs(leg['shares'] * px)
            target = policy['sleeve_fraction'] * alloc['gross_scale'] * equity_open
            available_gross = max(0.0, policy['gross_cap'] * equity_open - gross_open)
            gross_target = min(target, available_gross)
            if gross_target <= max(1.0, equity_open * 1e-8):
                skipped.append({'signal_date': sig['signal_date'], 'family': sig['family'], 'reason': 'gross_cap_or_zero_target'})
                continue
            gross, _, details = fit_gross_to_cash(sig, alloc, gross_target, cash, cost_model)
            if gross <= max(1.0, equity_open * 1e-8):
                skipped.append({'signal_date': sig['signal_date'], 'family': sig['family'], 'reason': 'insufficient_cash_after_cost'})
                continue
            legs, entry_cost_total = {}, 0.0
            for symbol, d in details.items():
                entry_bar = exact_bar(data[symbol], date)
                if not entry_bar:
                    continue
                n, cost = d['notional'], d['entry_cost']
                shares = n / entry_bar['open']
                cash -= n + cost
                turnover += n
                total_cost += cost
                entry_cost_total += cost
                max_participation = max(max_participation, d['participation'])
                all_cost_bps.append(d['rt_cost_bps'])
                legs[symbol] = {
                    'symbol': symbol, 'sector': ASSETS[symbol], 'shares': shares, 'entry_open': entry_bar['open'], 'entry_notional': n,
                    'entry_cost': cost, 'rt_cost_bps': d['rt_cost_bps'], 'participation': d['participation'], 'beta60': sig['context'][symbol]['beta60'], 'weight': d['weight'],
                }
            if not legs:
                skipped.append({'signal_date': sig['signal_date'], 'family': sig['family'], 'reason': 'no_executable_asset_legs'})
                continue
            sleeves.append({
                'sleeve_id': f"{sig['family']}|{sig['signal_date']}", 'family': sig['family'], 'signal_date': sig['signal_date'], 'signal_idx': sig['signal_spy_index'],
                'entry_date': date, 'entry_idx': i, 'exit_date': sig['exit_date'], 'exit_idx': sig['exit_spy_index'], 'allocation': policy['allocation'],
                'gross_target': gross_target, 'gross_entry': sum(x['entry_notional'] for x in legs.values()), 'entry_cost': entry_cost_total,
                'portfolio_beta_pre_scale': alloc['portfolio_beta_pre_scale'], 'gross_scale': alloc['gross_scale'], 'portfolio_beta_post_scale': alloc['portfolio_beta_post_scale'], 'legs': legs,
            })

        survivors = []
        for sl in sleeves:
            if sl['exit_idx'] == i:
                sleeve_pnl = 0.0
                sector_pnl, sector_notional = defaultdict(float), defaultdict(float)
                for symbol, leg in sl['legs'].items():
                    xb = exact_bar(data[symbol], date)
                    if not xb:
                        raise RuntimeError(f'missing exact exit close {symbol} {date}')
                    exit_value = leg['shares'] * xb['close']
                    exit_cost = exit_value * (leg['rt_cost_bps'] / 20000.0)
                    cash += exit_value - exit_cost
                    turnover += exit_value
                    total_cost += exit_cost
                    pnl = (exit_value - exit_cost) - (leg['entry_notional'] + leg['entry_cost'])
                    sleeve_pnl += pnl
                    sector_pnl[leg['sector']] += pnl
                    sector_notional[leg['sector']] += leg['entry_notional']
                closed_sleeves.append({
                    'sleeve_id': sl['sleeve_id'], 'family': sl['family'], 'signal_date': sl['signal_date'], 'entry_date': sl['entry_date'], 'exit_date': date,
                    'entry_gross_usd': round(sl['gross_entry'], 2), 'net_pnl_usd': round(sleeve_pnl, 2),
                    'net_return_pct_on_entry_gross': round(100.0 * sleeve_pnl / sl['gross_entry'], 6),
                    'sector_pnl_usd': {k: round(v, 2) for k, v in sector_pnl.items()},
                    'sector_entry_notional_usd': {k: round(v, 2) for k, v in sector_notional.items()},
                })
            else:
                survivors.append(sl)
        sleeves = survivors

        equity, gross, beta_dollar = cash, 0.0, 0.0
        sector_values = defaultdict(float)
        for sl in sleeves:
            for symbol, leg in sl['legs'].items():
                px = asof_close(data, symbol, date, caches)
                if px is None:
                    continue
                value = leg['shares'] * px
                equity += value
                gross += abs(value)
                beta_dollar += value * leg['beta60']
                sector_values[leg['sector']] += value
        gross_frac = 0.0 if equity == 0 else gross / equity
        beta_frac = 0.0 if equity == 0 else beta_dollar / equity
        if gross > 0:
            norm = [v / gross for v in sector_values.values()]
            hhi = sum(x * x for x in norm)
            max_sector = max(sector_values.values()) / equity if equity else 0.0
            exposure_days += 1
        else:
            hhi, max_sector = 0.0, 0.0
        gross_series.append(gross_frac)
        beta_series.append(beta_frac)
        max_sector_series.append(max_sector)
        hhi_series.append(hhi)
        if keep_curve:
            curve.append({'date': date, 'equity': round(equity, 4), 'gross_exposure': round(gross_frac, 8), 'beta_exposure': round(beta_frac, 8), 'max_sector_weight': round(max_sector, 8), 'sector_hhi': round(hhi, 8)})

        for sig in by_signal.get(i, []):
            if policy['dedup'] and active_or_pending_after_close(i):
                skipped.append({'signal_date': sig['signal_date'], 'family': sig['family'], 'reason': 'active_or_pending_same_instrument_basket'})
                continue
            pending.append({'signal': sig, 'signal_idx': i, 'entry_idx': sig['entry_spy_index']})

    if pending or sleeves:
        raise RuntimeError(f'unclosed/pending sleeves for {policy_name}/{cost_model}: pending={len(pending)} active={len(sleeves)}')
    final_equity = cash
    peak, max_dd = -float('inf'), 0.0
    for r in curve:
        e = r['equity']
        peak = max(peak, e)
        if peak > 0:
            max_dd = min(max_dd, e / peak - 1.0)
    sector_pnl, sector_notional = defaultdict(float), defaultdict(float)
    for sl in closed_sleeves:
        for k, v in sl['sector_pnl_usd'].items():
            sector_pnl[k] += v
        for k, v in sl['sector_entry_notional_usd'].items():
            sector_notional[k] += v
    wins = [sl['net_pnl_usd'] > 0 for sl in closed_sleeves]
    return {
        'policy': policy_name, 'cost_model': cost_model, 'start_capital_usd': start_capital, 'final_equity_usd': round(final_equity, 2),
        'total_return_pct': round(100.0 * (final_equity / start_capital - 1.0), 6), 'max_drawdown_pct': round(100.0 * max_dd, 6),
        'eligible_signal_count': len(signals), 'closed_sleeve_count': len(closed_sleeves), 'skipped_signal_count': len(skipped), 'skipped_signals': skipped,
        'exposure_day_pct': round(100.0 * exposure_days / len(spy), 4), 'average_gross_exposure': round(mean(gross_series), 6), 'max_gross_exposure': round(max(gross_series), 6),
        'average_beta_exposure': round(mean(beta_series), 6), 'max_beta_exposure': round(max(beta_series), 6),
        'average_max_sector_weight': round(mean(max_sector_series), 6), 'max_sector_weight': round(max(max_sector_series), 6),
        'average_sector_hhi': round(mean(hhi_series), 6), 'max_sector_hhi': round(max(hhi_series), 6),
        'turnover_multiple_start_capital': round(turnover / start_capital, 6), 'total_modeled_cost_usd': round(total_cost, 2),
        'average_modeled_rt_cost_bps': None if not all_cost_bps else round(mean(all_cost_bps), 6),
        'max_asset_adv_participation_pct': round(max_participation * 100.0, 8), 'sleeve_win_rate_pct': None if not wins else round(100.0 * sum(wins) / len(wins), 2),
        'sector_aggregate_entry_notional_usd': {k: round(v, 2) for k, v in sorted(sector_notional.items())},
        'sector_aggregate_net_pnl_usd': {k: round(v, 2) for k, v in sorted(sector_pnl.items())},
        'closed_sleeves': closed_sleeves, 'equity_curve': curve if keep_curve else None,
    }


def signal_context_summary(signals):
    out = {}
    for symbol in ASSETS:
        vals = [s['context'].get(symbol) for s in signals if s['context'].get(symbol)]
        if not vals:
            continue
        out[symbol] = {
            'sector': ASSETS[symbol], 'n': len(vals), 'median_adv20_usd': round(median(v['adv20_usd'] for v in vals), 2),
            'min_adv20_usd': round(min(v['adv20_usd'] for v in vals), 2), 'median_annualized_vol20_pct': round(100.0 * median(v['annualized_vol20'] for v in vals), 4),
            'median_beta60': round(median(v['beta60'] for v in vals), 6), 'min_beta60': round(min(v['beta60'] for v in vals), 6), 'max_beta60': round(max(v['beta60'] for v in vals), 6),
        }
    return out


def main():
    state_rows = build_state_rows()
    data, sources = fetch_universe()
    signals = build_historical_signals(state_rows, data)
    primary = {p: {c: simulate(data, signals, p, c, START_CAPITAL, keep_curve=True) for c in COST_MODELS} for p in POLICIES}
    sweep = {
        str(int(capital)): simulate(data, signals, 'early_full_stack25_beta100_cap100', 'square_root_impact', capital, keep_curve=False)
        for capital in CAPITAL_SWEEP
    }
    out = {
        'schema': 'TASK14-STAGE4-MULTIASSET-V1', 'generated_at': datetime.now(timezone.utc).isoformat(), 'research_only': True, 'diagnostic_only': True,
        'production_effect': 'none', 'thresholds_changed': False, 'broker_orders_enabled': False, 'frozen_through_market_date': FROZEN_THROUGH,
        'study_spec': SPEC, 'benchmark': BENCHMARK, 'asset_universe': [{'symbol': s, 'sector': ASSETS[s]} for s in ASSETS], 'data_sources': sources,
        'historical_signal_counts': {'early_sequence': sum(s['family'] == 'early_sequence' for s in signals), 'full_sequence': sum(s['family'] == 'full_sequence' for s in signals), 'combined_records': len(signals)},
        'execution_convention': {'entry': 'next_regular_session_open', 'exit': 'close_at_signal_plus_10_SPY_sessions', 'signal_decision_time': 'signal_close', 'same_day_priority': ['full_sequence', 'early_sequence']},
        'allocation_rules': {'equal': 'equal eligible sector weights, single-sector cap 20%', 'invvol': 'inverse trailing-20D annualized vol, iterative 20% sector cap', 'invvol_beta100': 'inverse-vol weights plus no-leverage gross scale when weighted trailing-60D beta > 1.00'},
        'policies': {k: {**v, 'families': sorted(v['families'])} for k, v in POLICIES.items()},
        'cost_models': {'fixed_10bps_rt': '10 bps round trip per asset trade', 'square_root_impact': '1 bp floor + sigma20_daily_bps * sqrt(asset_notional/ADV20)'},
        'signal_context_by_asset': signal_context_summary(signals), 'signals': signals, 'portfolio_results': primary, 'capital_scale_sweep': sweep,
        'guardrails': {'may_change_production': False, 'may_change_signal_definition': False, 'historical_results_count_as_forward_oos': False, 'automatic_promotion': False, 'broker_orders_enabled': False, 'stock_selection_inferred': False},
        'warnings': ['The sector ETF universe is a frozen multi-asset execution proxy, not a historical stock-selection strategy.', 'Historical policy comparisons are post-discovery diagnostics and cannot promote a production rule.', 'Trailing-60D beta is a simple SPY covariance beta, not a complete factor-risk model.', 'The square-root impact model is a stress envelope, not a calibrated broker fill model.'],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'signals': out['historical_signal_counts'], 'sources': sources, 'results': {p: {c: {'return_pct': primary[p][c]['total_return_pct'], 'max_dd_pct': primary[p][c]['max_drawdown_pct'], 'beta_max': primary[p][c]['max_beta_exposure'], 'max_sector': primary[p][c]['max_sector_weight'], 'max_participation_pct': primary[p][c]['max_asset_adv_participation_pct']} for c in COST_MODELS} for p in POLICIES}, 'sweep': {k: {'return_pct': v['total_return_pct'], 'avg_cost_bps': v['average_modeled_rt_cost_bps'], 'max_participation_pct': v['max_asset_adv_participation_pct']} for k, v in sweep.items()}}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
