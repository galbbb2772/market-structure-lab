from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import research_task14_stage4_multiasset_v1 as ma

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'docs/data/task14_challenger_forward_oos_v1.json'
OUT = ROOT / 'docs/data/task14_paper_multiasset_v1.json'
FROZEN_THROUGH = '2026-10-02'
START_CAPITAL = 100_000.0

BASE_IMMUTABLE = (
    'family', 'signal_date', 'accepted', 'skip_reason', 'allocation_mode',
    'allocation_weights', 'portfolio_beta_pre_scale', 'gross_scale', 'portfolio_beta_post_scale',
)
ENTRY_IMMUTABLE = ('entry_date', 'entry_gross_usd', 'asset_entry_details')


def load_existing():
    if not OUT.exists():
        return None
    d = json.loads(OUT.read_text(encoding='utf-8'))
    if d.get('schema') != 'TASK14-PAPER-MULTIASSET-V1':
        raise RuntimeError('paper multi-asset schema mismatch')
    if d.get('frozen_through_market_date') != FROZEN_THROUGH:
        raise RuntimeError('paper multi-asset freeze boundary mismatch')
    return d


def drop_current_utc_session(data):
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    return {symbol: [r for r in rows if r['date'] < today] for symbol, rows in data.items()}


def upstream_event_counts(src):
    early = ((src.get('challengers') or {}).get('early_sequence') or {}).get('events') or []
    full = ((src.get('challengers') or {}).get('rmd2_price_score') or {}).get('events') or []
    e = sum(bool(x.get('event_date')) and x['event_date'] > FROZEN_THROUGH for x in early)
    f = sum(bool(x.get('event_date')) and x['event_date'] > FROZEN_THROUGH for x in full)
    return {'early_sequence': e, 'full_sequence': f}


def collect_forward_signals(src, data):
    spy = data[ma.BENCHMARK]
    sidx = {r['date']: i for i, r in enumerate(spy)}
    streams = (
        ('early_sequence', ((src.get('challengers') or {}).get('early_sequence') or {}).get('events') or []),
        ('full_sequence', ((src.get('challengers') or {}).get('rmd2_price_score') or {}).get('events') or []),
    )
    out = []
    for family, events in streams:
        for e in events:
            d = e.get('event_date')
            if not d or d <= FROZEN_THROUGH:
                continue
            si = sidx.get(d)
            if si is None:
                continue
            context = {}
            for symbol in ma.ASSETS:
                c = ma.trailing_asset_context(symbol, data, spy, d)
                if c and ma.exact_bar(data[symbol], d):
                    context[symbol] = c
            if len(context) < 8:
                raise RuntimeError(f'insufficient sector context for future event {family} {d}: {len(context)}')
            allocations = {
                'equal': ma.allocation_from_context(context, 'equal'),
                'invvol': ma.allocation_from_context(context, 'invvol'),
                'invvol_beta100': ma.allocation_from_context(context, 'invvol_beta100'),
            }
            entry_idx = si + 1
            exit_idx = si + ma.HOLD_SIGNAL_SESSIONS
            out.append({
                'family': family,
                'signal_date': d,
                'upstream_first_seen_at': e.get('first_seen_at'),
                'signal_spy_index': si,
                'entry_spy_index': entry_idx,
                'entry_date': spy[entry_idx]['date'] if entry_idx < len(spy) else None,
                'exit_spy_index': exit_idx,
                'exit_date': spy[exit_idx]['date'] if exit_idx < len(spy) else None,
                'context': context,
                'allocations': allocations,
            })
    priority = {'full_sequence': 0, 'early_sequence': 1}
    out.sort(key=lambda x: (x['signal_date'], priority[x['family']]))
    return out


def decision_key(policy, cost, family, signal_date):
    return f'{policy}|{cost}|{family}|{signal_date}'


def existing_decision_map(existing):
    out = {}
    if not existing:
        return out
    for policy, models in (existing.get('portfolios') or {}).items():
        for cost, p in models.items():
            for d in p.get('signal_decisions') or []:
                out[decision_key(policy, cost, d['family'], d['signal_date'])] = d
    return out


def empty_portfolios(latest_market_date):
    return {
        p: {
            c: {
                'policy': p,
                'cost_model': c,
                'start_capital_usd': START_CAPITAL,
                'latest_market_date': latest_market_date,
                'latest_equity_usd': START_CAPITAL,
                'return_to_date_pct': 0.0,
                'signal_decisions': [],
                'realized_sleeves': [],
                'open_positions': [],
                'pending_entry_count': 0,
                'total_modeled_cost_to_date_usd': 0.0,
                'equity_curve': [],
            }
            for c in ma.COST_MODELS
        }
        for p in ma.POLICIES
    }


def simulate_partial(data, signals, policy_name, cost_model, old_map, now):
    spy = data[ma.BENCHMARK]
    policy = ma.POLICIES[policy_name]
    eligible = [s for s in signals if s['family'] in policy['families']]
    by_signal = defaultdict(list)
    priority = {'full_sequence': 0, 'early_sequence': 1}
    for s in eligible:
        by_signal[s['signal_spy_index']].append(s)
    for k in by_signal:
        by_signal[k].sort(key=lambda x: priority[x['family']])

    cash = START_CAPITAL
    pending, sleeves, decisions, realized, curve = [], [], [], [], []
    caches = {s: {} for s in ma.ASSETS}
    total_cost = 0.0

    def active_or_pending_after_close(signal_idx):
        return any(x['exit_idx'] > signal_idx for x in sleeves) or any(x['signal_idx'] >= signal_idx for x in pending)

    for i, bar in enumerate(spy):
        date = bar['date']

        entrants = [x for x in pending if x['entry_idx'] == i]
        pending = [x for x in pending if x['entry_idx'] != i]
        for item in entrants:
            sig = item['signal']
            dec = item['decision']
            alloc = sig['allocations'][policy['allocation']]
            missing = [s for s in alloc['weights'] if ma.exact_bar(data[s], date) is None]
            if missing:
                dec['execution_status'] = 'entry_data_missing'
                dec['entry_missing_symbols'] = missing
                continue
            equity_open, gross_open = cash, 0.0
            for sl in sleeves:
                for leg in sl['legs'].values():
                    b = ma.exact_bar(data[leg['symbol']], date)
                    px = b['open'] if b else ma.asof_close(data, leg['symbol'], date, caches)
                    equity_open += leg['shares'] * px
                    gross_open += abs(leg['shares'] * px)
            target = policy['sleeve_fraction'] * alloc['gross_scale'] * equity_open
            available_gross = max(0.0, policy['gross_cap'] * equity_open - gross_open)
            gross_target = min(target, available_gross)
            gross, _, details = ma.fit_gross_to_cash(sig, alloc, gross_target, cash, cost_model)
            if gross <= max(1.0, equity_open * 1e-8):
                dec['execution_status'] = 'gross_cap_or_cash_blocked'
                continue
            legs, entry_details, entry_cost_total = {}, {}, 0.0
            for symbol, x in details.items():
                b = ma.exact_bar(data[symbol], date)
                n, cost = x['notional'], x['entry_cost']
                shares = n / b['open']
                cash -= n + cost
                total_cost += cost
                entry_cost_total += cost
                legs[symbol] = {
                    'symbol': symbol,
                    'sector': ma.ASSETS[symbol],
                    'shares': shares,
                    'entry_open': b['open'],
                    'entry_notional': n,
                    'entry_cost': cost,
                    'rt_cost_bps': x['rt_cost_bps'],
                    'participation': x['participation'],
                    'beta60': sig['context'][symbol]['beta60'],
                }
                entry_details[symbol] = {
                    'sector': ma.ASSETS[symbol],
                    'entry_open': round(b['open'], 6),
                    'entry_notional_usd': round(n, 2),
                    'estimated_rt_cost_bps': round(x['rt_cost_bps'], 6),
                    'adv_participation_pct': round(x['participation'] * 100.0, 8),
                    'adv20_usd': round(sig['context'][symbol]['adv20_usd'], 2),
                    'beta60': round(sig['context'][symbol]['beta60'], 6),
                }
            dec.update({
                'execution_status': 'entered',
                'entry_date': date,
                'entry_gross_usd': round(sum(x['entry_notional'] for x in legs.values()), 2),
                'asset_entry_details': entry_details,
            })
            sleeves.append({
                'sleeve_id': f"{sig['family']}|{sig['signal_date']}",
                'family': sig['family'],
                'signal_date': sig['signal_date'],
                'signal_idx': sig['signal_spy_index'],
                'entry_date': date,
                'exit_idx': sig['exit_spy_index'],
                'exit_date': sig.get('exit_date'),
                'entry_gross': sum(x['entry_notional'] for x in legs.values()),
                'entry_cost': entry_cost_total,
                'legs': legs,
            })

        survivors = []
        for sl in sleeves:
            if sl['exit_idx'] < i:
                raise RuntimeError(f"missed exact paper exit for {sl['sleeve_id']} at SPY index {sl['exit_idx']}")
            if sl['exit_idx'] == i:
                missing = [s for s in sl['legs'] if ma.exact_bar(data[s], date) is None]
                if missing:
                    raise RuntimeError(f"missing exact exit bars for {sl['sleeve_id']} on {date}: {missing}")
                pnl = 0.0
                for symbol, leg in sl['legs'].items():
                    b = ma.exact_bar(data[symbol], date)
                    exit_value = leg['shares'] * b['close']
                    exit_cost = exit_value * (leg['rt_cost_bps'] / 20000.0)
                    cash += exit_value - exit_cost
                    total_cost += exit_cost
                    pnl += (exit_value - exit_cost) - (leg['entry_notional'] + leg['entry_cost'])
                realized.append({
                    'sleeve_id': sl['sleeve_id'],
                    'family': sl['family'],
                    'signal_date': sl['signal_date'],
                    'entry_date': sl['entry_date'],
                    'exit_date': date,
                    'entry_gross_usd': round(sl['entry_gross'], 2),
                    'net_pnl_usd': round(pnl, 2),
                    'net_return_pct_on_entry_gross': round(100.0 * pnl / sl['entry_gross'], 6),
                })
            else:
                survivors.append(sl)
        sleeves = survivors

        equity, gross, beta_dollar = cash, 0.0, 0.0
        sector_values = defaultdict(float)
        for sl in sleeves:
            for symbol, leg in sl['legs'].items():
                px = ma.asof_close(data, symbol, date, caches)
                if px is None:
                    continue
                value = leg['shares'] * px
                equity += value
                gross += abs(value)
                beta_dollar += value * leg['beta60']
                sector_values[leg['sector']] += value
        gross_frac = 0.0 if equity == 0 else gross / equity
        beta_frac = 0.0 if equity == 0 else beta_dollar / equity
        max_sector = 0.0 if not sector_values or equity == 0 else max(sector_values.values()) / equity
        curve.append({
            'date': date,
            'equity': round(equity, 4),
            'gross_exposure': round(gross_frac, 8),
            'beta_exposure': round(beta_frac, 8),
            'max_sector_weight': round(max_sector, 8),
        })

        for sig in by_signal.get(i, []):
            alloc = sig['allocations'][policy['allocation']]
            base = {
                'family': sig['family'],
                'signal_date': sig['signal_date'],
                'upstream_first_seen_at': sig.get('upstream_first_seen_at'),
                'paper_first_seen_at': now,
                'accepted': False,
                'skip_reason': None,
                'allocation_mode': policy['allocation'],
                'allocation_weights': {k: round(v, 10) for k, v in sorted(alloc['weights'].items())},
                'portfolio_beta_pre_scale': round(alloc['portfolio_beta_pre_scale'], 8),
                'gross_scale': round(alloc['gross_scale'], 8),
                'portfolio_beta_post_scale': round(alloc['portfolio_beta_post_scale'], 8),
                'execution_status': 'pending_entry',
                'entry_date': None,
                'entry_gross_usd': None,
                'asset_entry_details': None,
            }
            k = decision_key(policy_name, cost_model, sig['family'], sig['signal_date'])
            old = old_map.get(k)
            if old and old.get('paper_first_seen_at'):
                base['paper_first_seen_at'] = old['paper_first_seen_at']
            if policy['dedup'] and active_or_pending_after_close(i):
                base['skip_reason'] = 'active_or_pending_same_instrument_basket'
                base['execution_status'] = 'skipped'
                decisions.append(base)
                continue
            base['accepted'] = True
            decisions.append(base)
            pending.append({'signal': sig, 'signal_idx': i, 'entry_idx': sig['entry_spy_index'], 'decision': base})

    latest_date = spy[-1]['date'] if spy else None
    open_positions = []
    for sl in sleeves:
        marked = 0.0
        for symbol, leg in sl['legs'].items():
            px = ma.asof_close(data, symbol, latest_date, caches)
            if px is not None:
                marked += leg['shares'] * px
        open_positions.append({
            'sleeve_id': sl['sleeve_id'],
            'family': sl['family'],
            'signal_date': sl['signal_date'],
            'entry_date': sl['entry_date'],
            'marked_date': latest_date,
            'marked_value_usd': round(marked, 2),
        })

    latest_equity = curve[-1]['equity'] if curve else START_CAPITAL
    return {
        'policy': policy_name,
        'cost_model': cost_model,
        'start_capital_usd': START_CAPITAL,
        'latest_market_date': latest_date,
        'latest_equity_usd': latest_equity,
        'return_to_date_pct': round(100.0 * (latest_equity / START_CAPITAL - 1.0), 6),
        'signal_decisions': decisions,
        'realized_sleeves': realized,
        'open_positions': open_positions,
        'pending_entry_count': sum(d.get('accepted') and d.get('entry_date') is None for d in decisions),
        'total_modeled_cost_to_date_usd': round(total_cost, 2),
        'equity_curve': curve,
    }


def compare_existing(existing, current):
    if not existing:
        return []
    old = existing_decision_map(existing)
    new = {}
    for policy, models in current.items():
        for cost, p in models.items():
            for d in p.get('signal_decisions') or []:
                new[decision_key(policy, cost, d['family'], d['signal_date'])] = d
    discrepancies = []
    for key, a in old.items():
        b = new.get(key)
        if b is None:
            discrepancies.append({'key': key, 'field': 'decision_missing_on_recompute'})
            continue
        for f in BASE_IMMUTABLE:
            if a.get(f) != b.get(f):
                discrepancies.append({'key': key, 'field': f, 'stored': a.get(f), 'recompute': b.get(f)})
        if a.get('entry_date') is not None:
            for f in ENTRY_IMMUTABLE:
                if a.get(f) != b.get(f):
                    discrepancies.append({'key': key, 'field': f, 'stored': a.get(f), 'recompute': b.get(f)})
    return discrepancies


def write_output(src, sources, latest_market_date, signals, portfolios, discrepancies, now):
    counts = {
        'early_sequence': sum(s['family'] == 'early_sequence' for s in signals),
        'full_sequence': sum(s['family'] == 'full_sequence' for s in signals),
    }
    out = {
        'schema': 'TASK14-PAPER-MULTIASSET-V1',
        'generated_at': now,
        'research_only': True,
        'diagnostic_only': True,
        'paper_only': True,
        'production_effect': 'none',
        'broker_orders_enabled': False,
        'frozen_through_market_date': FROZEN_THROUGH,
        'study_spec': ma.SPEC,
        'data_sources': sources,
        'latest_complete_market_date': latest_market_date,
        'upstream_forward_signal_count': len(signals),
        'upstream_counts': counts,
        'asset_universe': [{'symbol': s, 'sector': ma.ASSETS[s]} for s in ma.ASSETS],
        'start_capital_usd': START_CAPITAL,
        'portfolios': portfolios,
        'immutable_recompute_discrepancies': discrepancies,
        'guardrails': {
            'may_change_production': False,
            'may_change_signal_definition': False,
            'historical_results_count_as_forward_oos': False,
            'automatic_promotion': False,
            'broker_orders_enabled': False,
            'stock_selection_inferred': False,
        },
        'warnings': [
            'This is a prospective sector-ETF paper portfolio only; no brokerage orders are enabled.',
            'Current UTC-date daily bars are excluded to prevent partial U.S. sessions from entering the ledger.',
            'Existing signal decisions and populated entry fields are immutable; recompute mismatches fail the build.',
            'Scheduled exits require exact sector-ETF bars on the frozen +10D SPY exit session; exits are never silently delayed.',
        ],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    return out


def main():
    src = json.loads(SOURCE.read_text(encoding='utf-8'))
    if src.get('schema') != 'TASK14-CHALLENGER-FORWARD-OOS-V1':
        raise RuntimeError('unexpected challenger Forward-OOS schema')
    if src.get('frozen_through_market_date') != FROZEN_THROUGH:
        raise RuntimeError('upstream freeze boundary mismatch')

    existing = load_existing()
    old_map = existing_decision_map(existing)
    now = datetime.now(timezone.utc).isoformat()
    upstream_counts = upstream_event_counts(src)

    # Zero future events is a valid state. Do not hit 12 market-data endpoints just to re-prove an empty ledger.
    if sum(upstream_counts.values()) == 0:
        if old_map:
            raise RuntimeError('upstream forward events disappeared while immutable paper decisions already exist')
        latest = src.get('latest_market_date')
        portfolios = empty_portfolios(latest)
        out = write_output(src, {'market_data_fetch': 'skipped_zero_forward_events'}, latest, [], portfolios, [], now)
        print(json.dumps({'signals': out['upstream_counts'], 'latest_complete_market_date': latest, 'market_data_fetch': 'skipped_zero_forward_events', 'discrepancies': 0}, ensure_ascii=False, indent=2))
        return

    raw_data, sources = ma.fetch_universe()
    data = drop_current_utc_session(raw_data)
    if not data[ma.BENCHMARK]:
        raise RuntimeError('no complete SPY sessions available')
    signals = collect_forward_signals(src, data)
    if len(signals) != sum(upstream_counts.values()):
        raise RuntimeError(f'not all upstream forward events could be reconstructed: upstream={upstream_counts} reconstructed={len(signals)}')
    portfolios = {
        p: {c: simulate_partial(data, signals, p, c, old_map, now) for c in ma.COST_MODELS}
        for p in ma.POLICIES
    }
    discrepancies = compare_existing(existing, portfolios)
    if discrepancies:
        raise RuntimeError(f'immutable paper multi-asset discrepancy: {discrepancies[:5]}')
    out = write_output(src, sources, data[ma.BENCHMARK][-1]['date'], signals, portfolios, discrepancies, now)
    print(json.dumps({
        'signals': out['upstream_counts'],
        'latest_complete_market_date': out['latest_complete_market_date'],
        'portfolios': {
            p: {c: {'decisions': len(x['signal_decisions']), 'realized': len(x['realized_sleeves']), 'open': len(x['open_positions']), 'pending': x['pending_entry_count'], 'equity': x['latest_equity_usd']} for c, x in models.items()}
            for p, models in portfolios.items()
        },
        'discrepancies': len(discrepancies),
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
