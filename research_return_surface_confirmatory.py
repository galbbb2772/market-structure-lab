from __future__ import annotations

import bisect
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

from research_pattern_edge_map import build_sp_state_map
from research_return_surface import HORIZONS, prepare

SRC = Path('docs/data/structure_lab.json')
OUT = Path('docs/data/return_surface_confirmatory.json')
SYMS = ('^GSPC', '^IXIC', '^DJI')
BOUNDARY_GAP = max(HORIZONS)
MIN_TRAIN_BASE = 100
MIN_TRAIN_GATE = 40
MIN_OOS_GATE = 30
NW_LAG = 5
FDR_LEVEL = 0.10

# Frozen after the descriptive return-surface stage. These are intentionally
# broad, interpretable regions rather than one best-looking quantile cell.
HYPOTHESES = {
    'A_strength_dip': {
        'label': 'Strength-Dip',
        'description': 'D1 after >= +2% prior-5-session strength, with moderate ATR percentile.',
        'rule': {'pre5_min': 2.0, 'atr_rank_min': 35.0, 'atr_rank_max': 70.0},
    },
    'B_trend_geometry': {
        'label': 'Trend Geometry',
        'description': 'D1 while price is >=1.5% above MA20 and 0% to 8% above MA200.',
        'rule': {'ma20_dist_min': 1.5, 'ma200_dist_min': 0.0, 'ma200_dist_max': 8.0},
    },
    'C_moderate_pullback': {
        'label': 'Moderate Pullback',
        'description': 'D1 with 20-session drawdown between -5% and -1% and non-extreme ATR percentile.',
        'rule': {'dd20_min': -5.0, 'dd20_max': -1.0, 'atr_rank_min': 35.0, 'atr_rank_max': 85.0},
    },
}


def avg(xs):
    z = [float(x) for x in xs if x is not None and math.isfinite(float(x))]
    return statistics.fmean(z) if z else None


def quantile(xs, p):
    z = sorted(float(x) for x in xs if x is not None and math.isfinite(float(x)))
    if not z:
        return None
    q = (len(z) - 1) * p
    i = int(q)
    f = q - i
    return z[i] + (z[min(i + 1, len(z) - 1)] - z[i]) * f


def summarize_returns(rows, h):
    if not rows:
        return {'n': 0, 'up_pct': None, 'mean': None, 'median': None, 'p25': None, 'p75': None}
    ret = [float(r[f'h{h}_ret']) for r in rows]
    return {
        'n': len(ret),
        'up_pct': 100.0 * sum(x > 0 for x in ret) / len(ret),
        'mean': avg(ret),
        'median': quantile(ret, .5),
        'p25': quantile(ret, .25),
        'p75': quantile(ret, .75),
    }


def normal_sf(z):
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def nw_one_sided_p(values, lag=NW_LAG):
    x = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    n = len(x)
    if n < 3:
        return None
    mu = avg(x)
    e = [v - mu for v in x]
    gamma0 = sum(v * v for v in e) / n
    lrv = gamma0
    max_lag = min(lag, n - 1)
    for L in range(1, max_lag + 1):
        w = 1.0 - L / (max_lag + 1.0)
        gamma = sum(e[t] * e[t - L] for t in range(L, n)) / n
        lrv += 2.0 * w * gamma
    lrv = max(lrv, 1e-18)
    se = math.sqrt(lrv / n)
    return normal_sf(mu / se if se > 0 else 0.0)


def bh_adjust(rows, p_field='p_value', q_field='q_value'):
    valid = [(i, r[p_field]) for i, r in enumerate(rows) if r.get(p_field) is not None]
    valid.sort(key=lambda x: x[1])
    m = len(valid)
    running = 1.0
    for k in range(m - 1, -1, -1):
        idx, p = valid[k]
        rank = k + 1
        q = min(running, p * m / rank)
        running = q
        rows[idx][q_field] = min(1.0, q)
    for r in rows:
        r.setdefault(q_field, None)


def in_gate(r, key):
    if key == 'A_strength_dip':
        return r['pre5'] >= 2.0 and 35.0 <= r['atr_rank'] <= 70.0
    if key == 'B_trend_geometry':
        return r['ma20_dist'] >= 1.5 and 0.0 <= r['ma200_dist'] <= 8.0
    if key == 'C_moderate_pullback':
        return -5.0 <= r['dd20'] <= -1.0 and 35.0 <= r['atr_rank'] <= 85.0
    raise KeyError(key)


def fold_records(rows, h, gate_key):
    rows = sorted(rows, key=lambda r: r['idx'])
    idxs = [r['idx'] for r in rows]
    by_year = defaultdict(list)
    for r in rows:
        by_year[int(r['year'])].append(r)

    records = []
    folds = []
    for year in sorted(by_year):
        test_all = by_year[year]
        test_gate = [r for r in test_all if in_gate(r, gate_key)]
        if not test_gate:
            continue

        first_test_idx = min(r['idx'] for r in test_all)
        cutoff_idx = first_test_idx - BOUNDARY_GAP - 1
        stop = bisect.bisect_right(idxs, cutoff_idx)
        train = [r for r in rows[:stop] if r['idx'] + h < first_test_idx]
        train_gate = [r for r in train if in_gate(r, gate_key)]

        if len(train) < MIN_TRAIN_BASE or len(train_gate) < MIN_TRAIN_GATE:
            folds.append({
                'test_year': year,
                'status': 'insufficient_training',
                'training_base_n': len(train),
                'training_gate_n': len(train_gate),
                'test_gate_n': len(test_gate),
            })
            continue

        bs = summarize_returns(train, h)
        gs = summarize_returns(train_gate, h)
        test_base_s = summarize_returns(test_all, h)
        test_gate_s = summarize_returns(test_gate, h)
        year_records = []
        for r in test_gate:
            actual = float(r[f'h{h}_ret'])
            y = 1.0 if actual > 0 else 0.0
            bp = bs['up_pct'] / 100.0
            gp = gs['up_pct'] / 100.0
            base_brier = (bp - y) ** 2
            gate_brier = (gp - y) ** 2
            base_abs = abs(actual - bs['median'])
            gate_abs = abs(actual - gs['median'])
            rec = {
                'date': r['date'],
                'year': year,
                'actual_ret': actual,
                'actual_up': bool(y),
                'base_train_up_pct': bs['up_pct'],
                'gate_train_up_pct': gs['up_pct'],
                'base_train_median': bs['median'],
                'gate_train_median': gs['median'],
                'brier_improvement': base_brier - gate_brier,
                'median_ae_improvement': base_abs - gate_abs,
            }
            records.append(rec)
            year_records.append(rec)

        folds.append({
            'test_year': year,
            'status': 'used',
            'training_cutoff_idx': cutoff_idx,
            'training_base_n': len(train),
            'training_gate_n': len(train_gate),
            'test_base_n': len(test_all),
            'test_gate_n': len(test_gate),
            'test_gate_mean': test_gate_s['mean'],
            'test_base_mean': test_base_s['mean'],
            'test_mean_edge': test_gate_s['mean'] - test_base_s['mean'],
            'test_gate_median': test_gate_s['median'],
            'test_base_median': test_base_s['median'],
            'test_median_edge': test_gate_s['median'] - test_base_s['median'],
            'test_gate_up_pct': test_gate_s['up_pct'],
            'test_base_up_pct': test_base_s['up_pct'],
            'test_up_edge_pp': test_gate_s['up_pct'] - test_base_s['up_pct'],
            'avg_brier_improvement': avg(x['brier_improvement'] for x in year_records),
            'avg_median_ae_improvement': avg(x['median_ae_improvement'] for x in year_records),
        })
    return records, folds


def summarize_test(sym, inst_name, gate_key, h, records, folds):
    used_folds = [f for f in folds if f['status'] == 'used']
    bdiff = [r['brier_improvement'] for r in records]
    mdiff = [r['median_ae_improvement'] for r in records]
    realized_mean_edges = [f['test_mean_edge'] for f in used_folds]
    realized_median_edges = [f['test_median_edge'] for f in used_folds]
    realized_up_edges = [f['test_up_edge_pp'] for f in used_folds]
    positive_mean_years = sum(v > 0 for v in realized_mean_edges)
    positive_median_years = sum(v > 0 for v in realized_median_edges)
    positive_up_years = sum(v > 0 for v in realized_up_edges)
    p = nw_one_sided_p(bdiff)
    return {
        'symbol': sym,
        'name': inst_name,
        'hypothesis': gate_key,
        'label': HYPOTHESES[gate_key]['label'],
        'horizon': h,
        'oos_n': len(records),
        'used_years': len(used_folds),
        'positive_mean_edge_years': positive_mean_years,
        'positive_median_edge_years': positive_median_years,
        'positive_up_edge_years': positive_up_years,
        'positive_mean_edge_year_rate': positive_mean_years / len(used_folds) if used_folds else None,
        'positive_median_edge_year_rate': positive_median_years / len(used_folds) if used_folds else None,
        'positive_up_edge_year_rate': positive_up_years / len(used_folds) if used_folds else None,
        'avg_realized_mean_edge': avg(realized_mean_edges),
        'avg_realized_median_edge': avg(realized_median_edges),
        'avg_realized_up_edge_pp': avg(realized_up_edges),
        'avg_brier_improvement': avg(bdiff),
        'avg_median_mae_improvement': avg(mdiff),
        'p_value': p,
        'folds': folds,
    }


def main():
    data = json.loads(SRC.read_text())
    state_map = build_sp_state_map(data['instruments']['^GSPC']['bars'])
    result = {
        'schema': 'RETURN-SURFACE-CONFIRMATORY-V1',
        'note': 'Retrospective confirmatory / pseudo-OOS validation of three frozen broad D1 regions discovered in the prior descriptive return-surface stage. Because the families were motivated using the full historical surface, this is stronger than an in-sample cell scan but is not a pristine untouched holdout.',
        'method': {
            'event': 'D1 only',
            'walk_forward': 'calendar-year expanding window',
            'boundary_gap_sessions': BOUNDARY_GAP,
            'purge_rule': 'all training labels must end before the first observation of the test year; a 10-session boundary gap is enforced',
            'baseline': 'all D1 events in the same index',
            'forecast_test': 'historical gate-vs-D1 up probability and median return are estimated using prior data only; evaluated on gate events in the test year',
            'realized_test': 'each test-year gate distribution is compared with that same test year all-D1 distribution',
            'serial_dependence': f'one-sided Newey-West/HAC test on paired Brier improvement, lag={NW_LAG}',
            'multiple_testing': 'Benjamini-Hochberg FDR across 3 frozen hypotheses x 4 horizons within each index',
            'fdr_level': FDR_LEVEL,
            'minimum_training_base_n': MIN_TRAIN_BASE,
            'minimum_training_gate_n': MIN_TRAIN_GATE,
            'minimum_oos_gate_n': MIN_OOS_GATE,
        },
        'hypotheses': HYPOTHESES,
        'instruments': {},
    }

    printable = {}
    for sym in SYMS:
        inst = data['instruments'][sym]
        rows = prepare(data, sym, state_map)
        tests = []
        for gate_key in HYPOTHESES:
            for h in HORIZONS:
                records, folds = fold_records(rows, h, gate_key)
                t = summarize_test(sym, inst['name'], gate_key, h, records, folds)
                if t['oos_n'] >= MIN_OOS_GATE:
                    tests.append(t)

        bh_adjust(tests)
        for t in tests:
            t['forecast_pass'] = bool(
                t['q_value'] is not None
                and t['q_value'] <= FDR_LEVEL
                and (t['avg_brier_improvement'] or 0) > 0
                and (t['avg_median_mae_improvement'] or 0) > 0
            )
            t['realized_pass'] = bool(
                (t['avg_realized_mean_edge'] or 0) > 0
                and (t['avg_realized_median_edge'] or 0) > 0
                and (t['avg_realized_up_edge_pp'] or 0) > 0
                and (t['positive_mean_edge_year_rate'] or 0) >= 0.60
                and (t['positive_median_edge_year_rate'] or 0) >= 0.60
            )
            t['confirmatory_pass'] = bool(t['forecast_pass'] and t['realized_pass'])

        by_hyp = {}
        for gate_key in HYPOTHESES:
            z = [t for t in tests if t['hypothesis'] == gate_key]
            by_hyp[gate_key] = {
                'tested_horizons': [t['horizon'] for t in z],
                'confirmatory_horizons': [t['horizon'] for t in z if t['confirmatory_pass']],
                'forecast_pass_horizons': [t['horizon'] for t in z if t['forecast_pass']],
                'realized_pass_horizons': [t['horizon'] for t in z if t['realized_pass']],
                'min_oos_n': min((t['oos_n'] for t in z), default=0),
                'best_q': min((t['q_value'] for t in z if t['q_value'] is not None), default=None),
                'avg_mean_edge': avg(t['avg_realized_mean_edge'] for t in z),
                'avg_median_edge': avg(t['avg_realized_median_edge'] for t in z),
                'avg_up_edge_pp': avg(t['avg_realized_up_edge_pp'] for t in z),
            }

        result['instruments'][sym] = {
            'name': inst['name'],
            'n_D1': len(rows),
            'tests': tests,
            'hypothesis_summary': by_hyp,
        }
        printable[sym] = {
            'name': inst['name'],
            'n_D1': len(rows),
            'summary': by_hyp,
            'passes': [
                {
                    'hypothesis': t['hypothesis'],
                    'horizon': t['horizon'],
                    'oos_n': t['oos_n'],
                    'q': t['q_value'],
                    'brier_imp': t['avg_brier_improvement'],
                    'median_mae_imp': t['avg_median_mae_improvement'],
                    'mean_edge': t['avg_realized_mean_edge'],
                    'median_edge': t['avg_realized_median_edge'],
                    'up_edge_pp': t['avg_realized_up_edge_pp'],
                    'confirmatory_pass': t['confirmatory_pass'],
                }
                for t in tests
            ],
        }

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(printable, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
