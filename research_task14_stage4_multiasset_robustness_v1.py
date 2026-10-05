from __future__ import annotations

import copy
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import research_task14_stage4_multiasset_v1 as m

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'docs/data/task14_stage4_multiasset_robustness_v1.json'
SPEC = 'research/task14_stage4_multiasset_robustness_v1/STUDY_SPEC.md'
BASE_POLICY = 'early_full_stack25_invvol_cap100'
BASE_COST = 'square_root_impact'
EQ_POLICY = 'early_full_stack25_equal_cap100'


def compact_sim(result):
    r = dict(result)
    r['equity_curve'] = None
    return r


def signal_without_sector(sig, drop_symbol):
    s = copy.deepcopy(sig)
    s['context'] = {k: v for k, v in s['context'].items() if k != drop_symbol}
    s['prices'] = {k: v for k, v in s.get('prices', {}).items() if k != drop_symbol}
    if len(s['context']) < 8:
        raise RuntimeError(f'LOO {drop_symbol} leaves too few eligible assets for {s["signal_date"]}')
    s['allocations'] = {
        'equal': m.allocation_from_context(s['context'], 'equal'),
        'invvol': m.allocation_from_context(s['context'], 'invvol'),
        'invvol_beta100': m.allocation_from_context(s['context'], 'invvol_beta100'),
    }
    return s


def abs_pnl_concentration(sector_pnl):
    absvals = {k: abs(float(v)) for k, v in sector_pnl.items()}
    total = sum(absvals.values())
    if total <= 0:
        return {
            'absolute_pnl_total_usd': 0.0,
            'absolute_pnl_shares': {},
            'largest_sector': None,
            'largest_sector_share_pct': 0.0,
            'top2_share_pct': 0.0,
            'absolute_pnl_hhi': 0.0,
        }
    shares = {k: v / total for k, v in absvals.items()}
    ranked = sorted(shares.items(), key=lambda kv: kv[1], reverse=True)
    return {
        'absolute_pnl_total_usd': round(total, 2),
        'absolute_pnl_shares': {k: round(100.0 * v, 4) for k, v in ranked},
        'largest_sector': ranked[0][0],
        'largest_sector_share_pct': round(100.0 * ranked[0][1], 4),
        'top2_share_pct': round(100.0 * sum(v for _, v in ranked[:2]), 4),
        'absolute_pnl_hhi': round(sum(v * v for v in shares.values()), 6),
    }


def result_core(r):
    return {
        'return_pct': r['total_return_pct'],
        'max_drawdown_pct': r['max_drawdown_pct'],
        'closed_sleeve_count': r['closed_sleeve_count'],
        'skipped_signal_count': r['skipped_signal_count'],
        'average_modeled_rt_cost_bps': r['average_modeled_rt_cost_bps'],
        'max_asset_adv_participation_pct': r['max_asset_adv_participation_pct'],
        'max_beta_exposure': r['max_beta_exposure'],
        'max_sector_weight': r['max_sector_weight'],
        'sleeve_win_rate_pct': r['sleeve_win_rate_pct'],
    }


def main():
    state_rows = m.build_state_rows()
    data, sources = m.fetch_universe()
    signals = m.build_historical_signals(state_rows, data)
    if sum(s['family'] == 'early_sequence' for s in signals) != 15 or sum(s['family'] == 'full_sequence' for s in signals) != 12:
        raise RuntimeError('historical signal counts changed during robustness audit')

    primary = json.loads(m.OUT.read_text(encoding='utf-8'))
    original_zero_dd = {
        k: primary.get('capital_scale_sweep', {}).get(k, {}).get('max_drawdown_pct')
        for k in ('100000', '1000000', '10000000', '100000000')
    }

    corrected_sweep = {}
    for capital in m.CAPITAL_SWEEP:
        result = m.simulate(data, signals, 'early_full_stack25_beta100_cap100', BASE_COST, capital, keep_curve=True)
        corrected_sweep[str(int(capital))] = compact_sim(result)

    # Repair only the known reporting bug in the primary historical diagnostic.
    primary['capital_scale_sweep'] = corrected_sweep
    primary['capital_scale_drawdown_repaired'] = True
    primary['capital_scale_drawdown_repair_note'] = (
        'V1 robustness repair: max drawdown is now calculated with the equity path retained internally; '
        'the stored scale records still omit the full equity curve.'
    )
    if 'warnings' in primary:
        note = 'Capital-scale max drawdown was repaired by the frozen Multi-Asset Robustness V1 audit; no trading rule changed.'
        if note not in primary['warnings']:
            primary['warnings'].append(note)
    m.OUT.write_text(json.dumps(primary, ensure_ascii=False, indent=2), encoding='utf-8')

    baseline = m.simulate(data, signals, BASE_POLICY, BASE_COST, m.START_CAPITAL, keep_curve=True)
    stored_baseline = primary['portfolio_results'][BASE_POLICY][BASE_COST]
    if abs(baseline['total_return_pct'] - stored_baseline['total_return_pct']) > 0.05:
        raise RuntimeError('robustness baseline no longer reproduces primary return within 5bp')

    loo = {}
    for drop_symbol in m.ASSETS:
        reduced = [signal_without_sector(s, drop_symbol) for s in signals]
        r = m.simulate(data, reduced, BASE_POLICY, BASE_COST, m.START_CAPITAL, keep_curve=True)
        loo[drop_symbol] = {
            'sector': m.ASSETS[drop_symbol],
            **result_core(r),
            'return_delta_vs_baseline_pp': round(r['total_return_pct'] - baseline['total_return_pct'], 6),
            'drawdown_delta_vs_baseline_pp': round(r['max_drawdown_pct'] - baseline['max_drawdown_pct'], 6),
        }

    # Equal-weight is a diagnostic comparator only; it is not added to production or prospective policy registries.
    old_eq = m.POLICIES.get(EQ_POLICY)
    m.POLICIES[EQ_POLICY] = {
        'families': {'early_sequence', 'full_sequence'},
        'dedup': False,
        'sleeve_fraction': 0.25,
        'allocation': 'equal',
        'gross_cap': 1.0,
    }
    try:
        eq_result = m.simulate(data, signals, EQ_POLICY, BASE_COST, m.START_CAPITAL, keep_curve=True)
    finally:
        if old_eq is None:
            m.POLICIES.pop(EQ_POLICY, None)
        else:
            m.POLICIES[EQ_POLICY] = old_eq

    loo_returns = [x['return_pct'] for x in loo.values()]
    positive_loo = sum(x > 0 for x in loo_returns)
    concentration = abs_pnl_concentration(baseline['sector_aggregate_net_pnl_usd'])
    most_negative = min(baseline['sector_aggregate_net_pnl_usd'].items(), key=lambda kv: kv[1])
    most_positive = max(baseline['sector_aggregate_net_pnl_usd'].items(), key=lambda kv: kv[1])

    out = {
        'schema': 'TASK14-STAGE4-MULTIASSET-ROBUSTNESS-V1',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'research_only': True,
        'diagnostic_only': True,
        'production_effect': 'none',
        'thresholds_changed': False,
        'frozen_through_market_date': m.FROZEN_THROUGH,
        'study_spec': SPEC,
        'historical_signal_counts': {
            'early_sequence': sum(s['family'] == 'early_sequence' for s in signals),
            'full_sequence': sum(s['family'] == 'full_sequence' for s in signals),
            'combined_records': len(signals),
        },
        'data_sources': sources,
        'capital_scale_drawdown_repair': {
            'original_reported_max_drawdown_pct': original_zero_dd,
            'corrected': {
                k: {
                    'return_pct': v['total_return_pct'],
                    'max_drawdown_pct': v['max_drawdown_pct'],
                    'average_modeled_rt_cost_bps': v['average_modeled_rt_cost_bps'],
                    'max_asset_adv_participation_pct': v['max_asset_adv_participation_pct'],
                }
                for k, v in corrected_sweep.items()
            },
            'trading_rules_changed': False,
        },
        'baseline': {
            'policy': BASE_POLICY,
            'cost_model': BASE_COST,
            **result_core(baseline),
            'sector_aggregate_net_pnl_usd': baseline['sector_aggregate_net_pnl_usd'],
        },
        'sector_leave_one_out': loo,
        'loo_summary': {
            'n': len(loo),
            'positive_return_count': positive_loo,
            'positive_return_pct': round(100.0 * positive_loo / len(loo), 2),
            'min_return_pct': round(min(loo_returns), 6),
            'max_return_pct': round(max(loo_returns), 6),
            'median_return_pct': round(sorted(loo_returns)[len(loo_returns) // 2], 6),
            'no_XLU': loo['XLU'],
            'no_XLE': loo['XLE'],
        },
        'allocation_comparison': {
            'inverse_volatility': result_core(baseline),
            'equal_weight': result_core(eq_result),
            'equal_minus_invvol_return_pp': round(eq_result['total_return_pct'] - baseline['total_return_pct'], 6),
            'equal_minus_invvol_drawdown_pp': round(eq_result['max_drawdown_pct'] - baseline['max_drawdown_pct'], 6),
        },
        'pnl_concentration': {
            **concentration,
            'most_positive_sector': {'sector': most_positive[0], 'net_pnl_usd': most_positive[1]},
            'most_negative_sector': {'sector': most_negative[0], 'net_pnl_usd': most_negative[1]},
        },
        'guardrails': {
            'may_change_production': False,
            'may_change_signal_definition': False,
            'historical_results_count_as_forward_oos': False,
            'automatic_sector_exclusion': False,
            'automatic_policy_promotion': False,
            'broker_orders_enabled': False,
            'stock_selection_inferred': False,
        },
        'warnings': [
            'Leave-one-sector-out is a robustness audit, not authorization to remove a historically weak sector.',
            'Equal-vs-inverse-vol is a post-discovery allocation diagnostic and cannot promote a policy.',
            'The sector ETF basket remains an execution proxy, not a frozen stock-selection strategy.',
        ],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({
        'baseline': result_core(baseline),
        'loo_summary': out['loo_summary'],
        'allocation_comparison': out['allocation_comparison'],
        'pnl_concentration': out['pnl_concentration'],
        'corrected_sweep': out['capital_scale_drawdown_repair']['corrected'],
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
