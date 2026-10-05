from __future__ import annotations

import json
from datetime import datetime, time as dtime, timezone
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo

import research_task14_stage4_portfolio_v1 as pf

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'docs/data/task14_challenger_forward_oos_v1.json'
OUT = ROOT / 'docs/data/task14_paper_portfolio_v1.json'
FROZEN_THROUGH = '2026-10-02'
START_CAPITAL = 100_000.0

IMMUTABLE_DECISION_FIELDS = (
    'accepted', 'skip_reason', 'family', 'signal_date', 'entry_date', 'entry_open',
    'target_fraction', 'entry_notional_usd', 'estimated_rt_cost_bps', 'adv_participation_pct',
)


def load_existing():
    if not OUT.exists():
        return None
    d = json.loads(OUT.read_text(encoding='utf-8'))
    if d.get('schema') != 'TASK14-PAPER-PORTFOLIO-V1':
        raise RuntimeError('paper portfolio schema mismatch')
    if d.get('frozen_through_market_date') != FROZEN_THROUGH:
        raise RuntimeError('paper portfolio freeze boundary mismatch')
    return d


def fetch_completed_spy():
    spy, source = pf.fetch_spy()
    now_ny = datetime.now(timezone.utc).astimezone(ZoneInfo('America/New_York'))
    excluded = False
    if spy and spy[-1]['date'] == now_ny.strftime('%Y-%m-%d') and now_ny.time() < dtime(16, 15):
        spy = spy[:-1]
        excluded = True
    source = dict(source)
    source['incomplete_current_session_excluded'] = excluded
    source['latest_completed_spy_date'] = None if not spy else spy[-1]['date']
    return spy, source


def collect_forward_signals(src, spy):
    idx = {r['date']: i for i, r in enumerate(spy)}
    raw = []
    streams = (
        ('early_sequence', ((src.get('challengers') or {}).get('early_sequence') or {}).get('events') or []),
        ('full_sequence', ((src.get('challengers') or {}).get('rmd2_price_score') or {}).get('events') or []),
    )
    for family, events in streams:
        for e in events:
            d = e.get('event_date')
            if not d or d <= FROZEN_THROUGH:
                continue
            si = idx.get(d)
            if si is None:
                continue
            adv20, sigma_bps, ann_vol = pf.trailing_context(spy, si)
            if adv20 in (None, 0) or sigma_bps in (None, 0) or ann_vol in (None, 0):
                continue
            raw.append({
                'family': family, 'signal_date': d, 'upstream_first_seen_at': e.get('first_seen_at'),
                'signal_spy_index': si, 'entry_spy_index': si + 1,
                'entry_date': spy[si + 1]['date'] if si + 1 < len(spy) else None,
                'exit_spy_index': si + pf.HOLD_SIGNAL_SESSIONS,
                'exit_date': spy[si + pf.HOLD_SIGNAL_SESSIONS]['date'] if si + pf.HOLD_SIGNAL_SESSIONS < len(spy) else None,
                'adv20_usd': round(adv20, 2), 'sigma20_daily_bps': round(sigma_bps, 6),
                'annualized_vol20': round(ann_vol, 8),
            })
    priority = {'full_sequence': 0, 'early_sequence': 1}
    raw.sort(key=lambda x: (x['signal_spy_index'], priority[x['family']]))
    return raw


def simulate_partial(spy, signals, policy_name, cost_model):
    policy = pf.POLICIES[policy_name]
    selected, prereg_skipped = pf.select_signals_for_policy(signals, policy)
    by_entry = {}
    for s in selected:
        if s.get('entry_date') is not None and s['entry_spy_index'] < len(spy):
            by_entry.setdefault(s['entry_spy_index'], []).append(s)

    decisions = [{
        'family': s['family'], 'signal_date': s['signal_date'], 'entry_date': None, 'entry_open': None,
        'accepted': False, 'skip_reason': x['reason'], 'target_fraction': None, 'entry_notional_usd': None,
        'estimated_rt_cost_bps': None, 'adv_participation_pct': None,
    } for s, x in []]
    # Pre-registration overlap skips happen at signal close, before next-open pricing.
    decisions = [{
        'family': x['family'], 'signal_date': x['signal_date'], 'entry_date': None, 'entry_open': None,
        'accepted': False, 'skip_reason': x['reason'], 'target_fraction': None,
        'entry_notional_usd': None, 'estimated_rt_cost_bps': None, 'adv_participation_pct': None,
    } for x in prereg_skipped]

    cash = START_CAPITAL
    lots, realized, curve = [], [], []
    total_cost = 0.0

    for i, bar in enumerate(spy):
        open_px, close_px = bar['open'], bar['close']
        for sig in by_entry.get(i, []):
            equity_open = cash + sum(x['shares'] * open_px for x in lots)
            gross_open = sum(abs(x['shares'] * open_px) for x in lots)
            frac = pf.desired_fraction(policy, sig)
            notional, cost_bps, participation = pf.solve_entry_notional(
                cash, equity_open, gross_open, frac, policy['gross_cap'], sig, cost_model
            )
            base = {
                'family': sig['family'], 'signal_date': sig['signal_date'], 'entry_date': bar['date'],
                'entry_open': round(open_px, 6), 'accepted': False, 'skip_reason': None,
                'target_fraction': round(frac, 8), 'entry_notional_usd': None,
                'estimated_rt_cost_bps': None, 'adv_participation_pct': None,
            }
            if notional <= max(1.0, equity_open * 1e-8):
                base['skip_reason'] = 'gross_cap_cash_or_zero_target_at_entry'
                decisions.append(base)
                continue
            entry_cost = notional * cost_bps / 20000.0
            shares = notional / open_px
            cash -= notional + entry_cost
            total_cost += entry_cost
            base.update({
                'accepted': True, 'entry_notional_usd': round(notional, 2),
                'estimated_rt_cost_bps': round(cost_bps, 6),
                'adv_participation_pct': round(participation * 100.0, 8),
            })
            decisions.append(base)
            lots.append({
                'family': sig['family'], 'signal_date': sig['signal_date'], 'entry_date': bar['date'],
                'entry_open': open_px, 'shares': shares, 'entry_notional': notional, 'entry_cost': entry_cost,
                'cost_bps': cost_bps, 'exit_idx': sig['exit_spy_index'],
            })

        survivors = []
        for lot in lots:
            if lot['exit_idx'] == i:
                exit_value = lot['shares'] * close_px
                exit_cost = exit_value * lot['cost_bps'] / 20000.0
                cash += exit_value - exit_cost
                total_cost += exit_cost
                pnl = (exit_value - exit_cost) - (lot['entry_notional'] + lot['entry_cost'])
                realized.append({
                    'family': lot['family'], 'signal_date': lot['signal_date'], 'entry_date': lot['entry_date'],
                    'exit_date': bar['date'], 'entry_open': round(lot['entry_open'], 6), 'exit_close': round(close_px, 6),
                    'net_pnl_usd': round(pnl, 2),
                    'net_return_pct_on_entry_notional': round(100.0 * pnl / lot['entry_notional'], 6),
                })
            else:
                survivors.append(lot)
        lots = survivors

        equity = cash + sum(x['shares'] * close_px for x in lots)
        gross = sum(abs(x['shares'] * close_px) for x in lots)
        gross_frac = 0.0 if equity == 0 else gross / equity
        if gross_frac > policy['gross_cap'] + 1e-6:
            raise RuntimeError(f'paper gross-cap violation {policy_name} {bar["date"]}: {gross_frac}')
        curve.append({'date': bar['date'], 'equity': round(equity, 4), 'gross_exposure': round(gross_frac, 8)})

    latest_close = spy[-1]['close']
    open_positions = [{
        'family': lot['family'], 'signal_date': lot['signal_date'], 'entry_date': lot['entry_date'],
        'entry_open': round(lot['entry_open'], 6), 'marked_date': spy[-1]['date'],
        'marked_close': round(latest_close, 6), 'marked_value_usd': round(lot['shares'] * latest_close, 2),
    } for lot in lots]
    exposures = [x['gross_exposure'] for x in curve]
    return {
        'policy': policy_name, 'cost_model': cost_model, 'start_capital_usd': START_CAPITAL,
        'latest_market_date': spy[-1]['date'], 'latest_equity_usd': curve[-1]['equity'],
        'return_to_date_pct': round(100.0 * (curve[-1]['equity'] / START_CAPITAL - 1.0), 6),
        'signal_decisions': sorted(decisions, key=lambda x: (x['signal_date'], 0 if x['family'] == 'full_sequence' else 1)),
        'realized_trades': realized, 'open_positions': open_positions,
        'total_modeled_cost_to_date_usd': round(total_cost, 2),
        'average_gross_exposure': round(mean(exposures), 6) if exposures else 0.0,
        'max_gross_exposure': round(max(exposures), 6) if exposures else 0.0,
        'equity_curve': curve,
    }


def decision_map(portfolios):
    out = {}
    for p, models in portfolios.items():
        for c, d in models.items():
            for x in d.get('signal_decisions') or []:
                out[f"{p}|{c}|{x['family']}|{x['signal_date']}"] = x
    return out


def compare_existing(existing, current):
    if not existing:
        return []
    old, new = decision_map(existing.get('portfolios') or {}), decision_map(current)
    discrepancies = []
    for key, a in old.items():
        b = new.get(key)
        if b is None:
            discrepancies.append({'key': key, 'field': 'decision_missing_on_recompute'})
            continue
        for f in IMMUTABLE_DECISION_FIELDS:
            if a.get(f) != b.get(f):
                discrepancies.append({'key': key, 'field': f, 'stored': a.get(f), 'recompute': b.get(f)})
    return discrepancies


def main():
    src = json.loads(SOURCE.read_text(encoding='utf-8'))
    if src.get('schema') != 'TASK14-CHALLENGER-FORWARD-OOS-V1':
        raise RuntimeError('unexpected challenger Forward-OOS schema')
    if src.get('frozen_through_market_date') != FROZEN_THROUGH:
        raise RuntimeError('upstream freeze boundary mismatch')

    spy, source = fetch_completed_spy()
    if not spy:
        raise RuntimeError('no completed SPY sessions available')
    signals = collect_forward_signals(src, spy)
    portfolios = {}
    for policy in pf.POLICIES:
        portfolios[policy] = {}
        for cost_model in pf.COST_MODELS:
            portfolios[policy][cost_model] = simulate_partial(spy, signals, policy, cost_model)

    existing = load_existing()
    discrepancies = compare_existing(existing, portfolios)
    if discrepancies:
        raise RuntimeError(f'immutable paper portfolio decision discrepancy: {discrepancies[:5]}')

    out = {
        'schema': 'TASK14-PAPER-PORTFOLIO-V1', 'generated_at': datetime.now(timezone.utc).isoformat(),
        'research_only': True, 'diagnostic_only': True, 'paper_only': True, 'production_effect': 'none',
        'broker_orders_enabled': False, 'frozen_through_market_date': FROZEN_THROUGH,
        'study_spec': pf.SPEC, 'source': source,
        'upstream_forward_signal_count': len(signals),
        'upstream_counts': {
            'early_sequence': sum(x['family'] == 'early_sequence' for x in signals),
            'full_sequence': sum(x['family'] == 'full_sequence' for x in signals),
        },
        'start_capital_usd': START_CAPITAL, 'portfolios': portfolios,
        'immutable_recompute_discrepancies': discrepancies,
        'guardrails': {
            'may_change_production': False, 'may_change_signal_definition': False,
            'historical_results_count_as_forward_oos': False, 'automatic_promotion': False,
            'broker_orders_enabled': False,
        },
        'warnings': [
            'This is a prospective paper portfolio only; no brokerage orders are enabled.',
            'Only post-2026-10-02 Forward-OOS Early Sequence and Full Sequence events are eligible.',
            'Deduplication is decided at signal close; execution occurs at the next completed regular-session open.',
            'An incomplete current U.S. trading session is excluded from the paper ledger.',
            'Existing signal decisions are immutable; a later recompute mismatch fails the build instead of rewriting history.',
        ],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({
        'signals': out['upstream_counts'], 'latest_completed_market_date': spy[-1]['date'],
        'incomplete_session_excluded': source['incomplete_current_session_excluded'],
        'portfolios': {p: {c: {
            'decisions': len(d['signal_decisions']), 'realized': len(d['realized_trades']),
            'open': len(d['open_positions']), 'equity': d['latest_equity_usd'],
        } for c, d in models.items()} for p, models in portfolios.items()},
        'discrepancies': len(discrepancies),
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
