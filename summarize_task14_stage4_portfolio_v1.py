from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import mean, stdev

ROOT = Path(__file__).resolve().parent
SRC = ROOT / 'docs/data/task14_stage4_portfolio_v1.json'
PAPER = ROOT / 'docs/data/task14_paper_portfolio_v1.json'
OUT = ROOT / 'docs/data/task14_stage4_portfolio_v1_summary.json'
SQRT252 = math.sqrt(252.0)


def risk_from_curve(curve):
    vals = [float(x['equity']) for x in curve or [] if x.get('equity') is not None]
    if len(vals) < 2:
        return {'observations': len(vals), 'annualized_vol_pct': None, 'sharpe0': None, 'cagr_pct': None}
    rets = [vals[i] / vals[i - 1] - 1.0 for i in range(1, len(vals)) if vals[i - 1] != 0]
    mu = mean(rets) if rets else 0.0
    sd = stdev(rets) if len(rets) >= 2 else 0.0
    ann_vol = sd * SQRT252 * 100.0
    sharpe = None if sd == 0 else mu / sd * SQRT252
    years = (len(vals) - 1) / 252.0
    cagr = None if years <= 0 or vals[0] <= 0 or vals[-1] <= 0 else ((vals[-1] / vals[0]) ** (1.0 / years) - 1.0) * 100.0
    return {
        'observations': len(vals),
        'annualized_vol_pct': round(ann_vol, 6),
        'sharpe0': None if sharpe is None else round(sharpe, 6),
        'cagr_pct': None if cagr is None else round(cagr, 6),
    }


def compact_result(r):
    out = {
        'return_pct': r.get('total_return_pct'),
        'max_drawdown_pct': r.get('max_drawdown_pct'),
        'trade_count': r.get('trade_count'),
        'skipped_signal_count': r.get('skipped_signal_count'),
        'exposure_day_pct': r.get('exposure_day_pct'),
        'average_gross_exposure': r.get('average_gross_exposure'),
        'max_gross_exposure': r.get('max_gross_exposure'),
        'turnover_multiple_start_capital': r.get('turnover_multiple_start_capital'),
        'total_modeled_cost_usd': r.get('total_modeled_cost_usd'),
        'average_modeled_rt_cost_bps': r.get('average_modeled_rt_cost_bps'),
        'max_adv_participation_pct': r.get('max_adv_participation_pct'),
        'trade_win_rate_pct': r.get('trade_win_rate_pct'),
    }
    out.update(risk_from_curve(r.get('equity_curve')))
    return out


def main():
    d = json.loads(SRC.read_text(encoding='utf-8'))
    p = json.loads(PAPER.read_text(encoding='utf-8'))
    results = {
        policy: {cost: compact_result(r) for cost, r in models.items()}
        for policy, models in d['portfolio_results'].items()
    }
    sweep = {
        k: {
            'return_pct': v.get('total_return_pct'),
            'average_modeled_rt_cost_bps': v.get('average_modeled_rt_cost_bps'),
            'max_adv_participation_pct': v.get('max_adv_participation_pct'),
            'trade_count': v.get('trade_count'),
        }
        for k, v in d['capital_scale_sweep'].items()
    }
    paper = {
        'upstream_forward_signal_count': p.get('upstream_forward_signal_count'),
        'upstream_counts': p.get('upstream_counts'),
        'immutable_recompute_discrepancy_count': len(p.get('immutable_recompute_discrepancies') or []),
        'portfolios': {
            policy: {
                cost: {
                    'decision_count': len(x.get('signal_decisions') or []),
                    'realized_trade_count': len(x.get('realized_trades') or []),
                    'open_position_count': len(x.get('open_positions') or []),
                    'latest_equity_usd': x.get('latest_equity_usd'),
                    'return_to_date_pct': x.get('return_to_date_pct'),
                }
                for cost, x in models.items()
            }
            for policy, models in p.get('portfolios', {}).items()
        },
    }
    out = {
        'schema': 'TASK14-STAGE4-PORTFOLIO-V1-SUMMARY',
        'generated_at': d.get('generated_at'),
        'research_only': True,
        'diagnostic_only': True,
        'production_effect': 'none',
        'frozen_through_market_date': d.get('frozen_through_market_date'),
        'historical_signal_counts': d.get('historical_signal_counts'),
        'execution_convention': d.get('execution_convention'),
        'portfolio_results': results,
        'capacity_threshold_summary': d.get('capacity_threshold_summary'),
        'capital_scale_sweep': sweep,
        'paper_portfolio': paper,
        'interpretation_guardrails': {
            'historical_policy_results_are_post_discovery': True,
            'sharpe0_is_diagnostic_not_promotion_metric': True,
            'square_root_impact_is_stress_model_not_broker_calibration': True,
            'no_policy_auto_promoted': True,
        },
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
