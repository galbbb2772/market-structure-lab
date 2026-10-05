from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import mean, stdev

ROOT = Path(__file__).resolve().parent
SRC = ROOT / 'docs/data/task14_stage4_multiasset_v1.json'
PAPER = ROOT / 'docs/data/task14_paper_multiasset_v1.json'
OUT = ROOT / 'docs/data/task14_stage4_multiasset_v1_summary.json'
SQRT252 = math.sqrt(252.0)


def risk_from_curve(curve):
    vals = [float(x['equity']) for x in curve or [] if x.get('equity') is not None]
    if len(vals) < 2:
        return {'observations': len(vals), 'annualized_vol_pct': None, 'sharpe0': None, 'cagr_pct': None}
    rets = [vals[i] / vals[i - 1] - 1.0 for i in range(1, len(vals)) if vals[i - 1] != 0]
    mu = mean(rets) if rets else 0.0
    sd = stdev(rets) if len(rets) >= 2 else 0.0
    years = (len(vals) - 1) / 252.0
    return {
        'observations': len(vals),
        'annualized_vol_pct': round(sd * SQRT252 * 100.0, 6),
        'sharpe0': None if sd == 0 else round(mu / sd * SQRT252, 6),
        'cagr_pct': None if years <= 0 or vals[0] <= 0 or vals[-1] <= 0 else round(((vals[-1] / vals[0]) ** (1.0 / years) - 1.0) * 100.0, 6),
    }


def compact(r):
    out = {
        'return_pct': r.get('total_return_pct'), 'max_drawdown_pct': r.get('max_drawdown_pct'),
        'closed_sleeve_count': r.get('closed_sleeve_count'), 'skipped_signal_count': r.get('skipped_signal_count'),
        'exposure_day_pct': r.get('exposure_day_pct'), 'average_gross_exposure': r.get('average_gross_exposure'), 'max_gross_exposure': r.get('max_gross_exposure'),
        'average_beta_exposure': r.get('average_beta_exposure'), 'max_beta_exposure': r.get('max_beta_exposure'),
        'average_max_sector_weight': r.get('average_max_sector_weight'), 'max_sector_weight': r.get('max_sector_weight'),
        'average_sector_hhi': r.get('average_sector_hhi'), 'max_sector_hhi': r.get('max_sector_hhi'),
        'turnover_multiple_start_capital': r.get('turnover_multiple_start_capital'), 'total_modeled_cost_usd': r.get('total_modeled_cost_usd'),
        'average_modeled_rt_cost_bps': r.get('average_modeled_rt_cost_bps'), 'max_asset_adv_participation_pct': r.get('max_asset_adv_participation_pct'),
        'sleeve_win_rate_pct': r.get('sleeve_win_rate_pct'), 'sector_aggregate_net_pnl_usd': r.get('sector_aggregate_net_pnl_usd'),
    }
    out.update(risk_from_curve(r.get('equity_curve')))
    return out


def main():
    h = json.loads(SRC.read_text(encoding='utf-8'))
    p = json.loads(PAPER.read_text(encoding='utf-8'))
    results = {policy: {cost: compact(r) for cost, r in models.items()} for policy, models in h['portfolio_results'].items()}
    sweep = {
        k: {
            'return_pct': v.get('total_return_pct'), 'max_drawdown_pct': v.get('max_drawdown_pct'),
            'average_modeled_rt_cost_bps': v.get('average_modeled_rt_cost_bps'), 'max_asset_adv_participation_pct': v.get('max_asset_adv_participation_pct'),
            'max_beta_exposure': v.get('max_beta_exposure'), 'max_sector_weight': v.get('max_sector_weight'),
        }
        for k, v in h['capital_scale_sweep'].items()
    }
    paper = {
        'latest_complete_market_date': p.get('latest_complete_market_date'), 'upstream_forward_signal_count': p.get('upstream_forward_signal_count'),
        'upstream_counts': p.get('upstream_counts'), 'immutable_recompute_discrepancy_count': len(p.get('immutable_recompute_discrepancies') or []),
        'portfolios': {
            policy: {
                cost: {
                    'decision_count': len(x.get('signal_decisions') or []), 'realized_sleeve_count': len(x.get('realized_sleeves') or []),
                    'open_position_count': len(x.get('open_positions') or []), 'pending_entry_count': x.get('pending_entry_count'),
                    'latest_equity_usd': x.get('latest_equity_usd'), 'return_to_date_pct': x.get('return_to_date_pct'),
                }
                for cost, x in models.items()
            }
            for policy, models in p.get('portfolios', {}).items()
        },
    }
    out = {
        'schema': 'TASK14-STAGE4-MULTIASSET-V1-SUMMARY', 'generated_at': h.get('generated_at'), 'research_only': True, 'diagnostic_only': True,
        'production_effect': 'none', 'frozen_through_market_date': h.get('frozen_through_market_date'), 'benchmark': h.get('benchmark'),
        'asset_universe': h.get('asset_universe'), 'historical_signal_counts': h.get('historical_signal_counts'), 'execution_convention': h.get('execution_convention'),
        'signal_context_by_asset': h.get('signal_context_by_asset'), 'portfolio_results': results, 'capital_scale_sweep': sweep, 'paper_multiasset': paper,
        'interpretation_guardrails': {'historical_results_are_post_discovery': True, 'sector_etfs_are_execution_proxies_not_stock_selection': True, 'beta60_is_diagnostic_not_factor_model': True, 'no_policy_auto_promoted': True},
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
