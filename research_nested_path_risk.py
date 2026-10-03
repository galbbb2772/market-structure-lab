from __future__ import annotations

import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from research_pattern_edge_map import build_sp_state_map
from research_pattern_purged_validation import bh_adjust, nw_one_sided_p
from research_return_surface import PAIRS, prepare

SRC = Path('docs/data/structure_lab.json')
OUT = Path('docs/data/nested_path_risk.json')
SYMS = ('^GSPC', '^IXIC', '^DJI')
HORIZONS = (1, 3, 5, 10)
BANDWIDTHS = (0.12, 0.20)
BOUNDARY_GAP = 10
MIN_TRAIN_N = 400
MIN_SELECTOR_YEARS = 8
MIN_SELECTOR_EVENTS = 200
FDR_LEVEL = 0.10

CONT_TARGETS = {
    'mfe5': 'T+5 maximum favorable excursion (%)',
    'adverse5': 'T+5 maximum adverse excursion magnitude (%)',
    'range10': 'T+10 path range = MFE - MAE (%)',
    'time_to_mfe10': 'trading days to first T+10 maximum high',
    'time_to_mae10': 'trading days to first T+10 minimum low',
}


def avg(xs):
    z = [float(x) for x in xs if x is not None and math.isfinite(float(x))]
    return statistics.fmean(z) if z else None


def pct_map(train_values, query_values):
    s = np.sort(np.asarray(train_values, dtype=float))
    q = np.asarray(query_values, dtype=float)
    return np.searchsorted(s, q, side='right') / max(len(s), 1)


def combo_name(pair, bw):
    return f'{pair[0]}×{pair[1]}|bw={bw:.2f}'


def add_path_targets(bars, rows):
    out = []
    for r in rows:
        i = r['idx']
        if i + 10 >= len(bars):
            continue
        fut = bars[i + 1:i + 11]
        highs = [float(b[2]) for b in fut]
        lows = [float(b[3]) for b in fut]
        q = dict(r)
        q['mfe5'] = float(r['h5_mfe'])
        q['adverse5'] = max(0.0, -float(r['h5_mae']))
        q['range10'] = float(r['h10_mfe']) - float(r['h10_mae'])
        q['time_to_mfe10'] = float(highs.index(max(highs)) + 1)
        q['time_to_mae10'] = float(lows.index(min(lows)) + 1)
        returns = {h: float(r[f'h{h}_ret']) for h in HORIZONS}
        q['best_hold'] = max(HORIZONS, key=lambda h: (returns[h], -h))
        q['best_hold_return'] = returns[q['best_hold']]
        out.append(q)
    return out


def kernel_weights(train, test, pair, bw):
    xk, yk = pair
    tx = np.asarray([r[xk] for r in train], dtype=float)
    ty = np.asarray([r[yk] for r in train], dtype=float)
    qx = np.asarray([r[xk] for r in test], dtype=float)
    qy = np.asarray([r[yk] for r in test], dtype=float)
    train_x = pct_map(tx, tx)
    train_y = pct_map(ty, ty)
    test_x = pct_map(tx, qx)
    test_y = pct_map(ty, qy)
    d2 = (test_x[:, None] - train_x[None, :]) ** 2 + (test_y[:, None] - train_y[None, :]) ** 2
    w = np.exp(-0.5 * d2 / (bw * bw))
    sw = np.maximum(w.sum(axis=1), 1e-15)
    return w, sw


def continuous_metrics(train, test, w, sw, target):
    tr = np.asarray([r[target] for r in train], dtype=float)
    actual = np.asarray([r[target] for r in test], dtype=float)
    pred = (w @ tr) / sw
    base = float(np.mean(tr))
    train_var = float(np.mean((tr - base) ** 2))
    base_se = (actual - base) ** 2
    model_se = (actual - pred) ** 2
    imp = base_se - model_se
    return {
        'n': len(test),
        'train_var': train_var,
        'mse_improvement': float(np.mean(imp)),
        'normalized_skill': float(np.mean(imp) / train_var) if train_var > 1e-15 else 0.0,
        '_improvement': imp,
    }


def hold_metrics(train, test, w, sw):
    train_ret = {h: np.asarray([r[f'h{h}_ret'] for r in train], dtype=float) for h in HORIZONS}
    pred = {h: (w @ train_ret[h]) / sw for h in HORIZONS}
    base_means = {h: float(np.mean(train_ret[h])) for h in HORIZONS}
    base_hold = max(HORIZONS, key=lambda h: (base_means[h], -h))
    model_hold = np.asarray([
        max(HORIZONS, key=lambda h: (pred[h][j], -h))
        for j in range(len(test))
    ], dtype=int)
    actual_returns = {h: np.asarray([r[f'h{h}_ret'] for r in test], dtype=float) for h in HORIZONS}
    actual_best = np.asarray([
        max(HORIZONS, key=lambda h: (actual_returns[h][j], -h))
        for j in range(len(test))
    ], dtype=int)
    best_ret = np.asarray([actual_returns[actual_best[j]][j] for j in range(len(test))], dtype=float)
    base_ret = actual_returns[base_hold]
    model_ret = np.asarray([actual_returns[model_hold[j]][j] for j in range(len(test))], dtype=float)
    base_regret = best_ret - base_ret
    model_regret = best_ret - model_ret
    imp = base_regret - model_regret
    return {
        'n': len(test),
        'base_hold': int(base_hold),
        'base_hit_rate': float(np.mean(actual_best == base_hold)),
        'model_hit_rate': float(np.mean(actual_best == model_hold)),
        'regret_improvement': float(np.mean(imp)),
        '_improvement': imp,
    }


def precompute(rows, bars):
    rows = sorted(rows, key=lambda r: r['idx'])
    years = sorted({int(r['year']) for r in rows})
    by_year = {y: [r for r in rows if int(r['year']) == y] for y in years}
    metrics = defaultdict(dict)
    folds = []
    for year in years:
        test = by_year[year]
        if not test:
            continue
        first_idx = min(r['idx'] for r in test)
        cutoff = first_idx - BOUNDARY_GAP - 1
        train = [r for r in rows if r['idx'] <= cutoff]
        if len(train) < MIN_TRAIN_N:
            continue
        folds.append({'year': year, 'train_n': len(train), 'test_n': len(test), 'cutoff_idx': cutoff})
        for pair in PAIRS:
            for bw in BANDWIDTHS:
                cname = combo_name(pair, bw)
                w, sw = kernel_weights(train, test, pair, bw)
                for target in CONT_TARGETS:
                    metrics[(target, cname)][year] = continuous_metrics(train, test, w, sw, target)
                metrics[('best_hold', cname)][year] = hold_metrics(train, test, w, sw)
    return metrics, folds, years


def selector_score(history, target):
    if len(history) < MIN_SELECTOR_YEARS or sum(x['n'] for x in history) < MIN_SELECTOR_EVENTS:
        return None
    if target == 'best_hold':
        score = avg(x['regret_improvement'] for x in history)
    else:
        score = avg(x['normalized_skill'] for x in history)
    return {'score': score, 'years': len(history), 'events': sum(x['n'] for x in history)}


def nested_target(metrics, years, target):
    combos = sorted({c for t, c in metrics if t == target})
    selections = []
    improvements = []
    for year in years:
        candidates = []
        for c in combos:
            cur = metrics[(target, c)].get(year)
            if cur is None:
                continue
            hist = [metrics[(target, c)][y] for y in sorted(metrics[(target, c)]) if y < year]
            ss = selector_score(hist, target)
            if ss is not None:
                candidates.append((c, ss, cur))
        if not candidates:
            continue
        c, ss, cur = max(candidates, key=lambda x: (x[1]['score'], x[1]['events'], x[0]))
        improvements.extend(float(x) for x in cur['_improvement'])
        row = {
            'year': year,
            'combo': c,
            'selector_score': ss['score'],
            'prior_validation_years': ss['years'],
            'prior_validation_events': ss['events'],
            'test_n': cur['n'],
        }
        if target == 'best_hold':
            row.update({k:cur[k] for k in ('base_hold','base_hit_rate','model_hit_rate','regret_improvement')})
        else:
            row.update({k:cur[k] for k in ('train_var','mse_improvement','normalized_skill')})
        selections.append(row)
    if not selections:
        return None
    p = nw_one_sided_p(improvements, lag=10)
    freq = Counter(x['combo'] for x in selections)
    if target == 'best_hold':
        effect = avg(improvements)
        positive_year_rate = sum(x['regret_improvement'] > 0 for x in selections) / len(selections)
        extra = {
            'regret_improvement': effect,
            'positive_year_rate': positive_year_rate,
            'avg_model_hit_rate': avg(x['model_hit_rate'] for x in selections),
            'avg_base_hit_rate': avg(x['base_hit_rate'] for x in selections),
        }
    else:
        effect = avg(improvements)
        positive_year_rate = sum(x['mse_improvement'] > 0 for x in selections) / len(selections)
        extra = {
            'mse_improvement': effect,
            'positive_year_rate': positive_year_rate,
            'avg_normalized_skill': avg(x['normalized_skill'] for x in selections),
        }
    return {
        'target': target,
        'label': CONT_TARGETS.get(target, 'Best fixed exit horizon among 1/3/5/10 days'),
        'outer_years': len(selections),
        'outer_event_n': sum(x['test_n'] for x in selections),
        'p_value': p,
        'effect': effect,
        'combo_frequency': dict(freq.most_common()),
        'year_selections': selections,
        **extra,
    }


def main():
    data = json.loads(SRC.read_text())
    state_map = build_sp_state_map(data['instruments']['^GSPC']['bars'])
    result = {
        'schema': 'NESTED-PATH-RISK-V1',
        'note': 'Historical nested walk-forward test of whether D1 technical state can forecast path/risk/execution variables. Model and pair/bandwidth selection use prior data only. Feature-pair menu was researched previously, so passing results are Shadow evidence, not pristine independent forward confirmation and must not modify Frozen V4 MAIN automatically.',
        'method': {
            'event': 'D1 only',
            'continuous_targets': CONT_TARGETS,
            'hold_target': 'choose best expected endpoint among T+1/T+3/T+5/T+10; score by reduction in realized regret versus train-only baseline hold',
            'pairs': PAIRS,
            'bandwidths': BANDWIDTHS,
            'surface': '2D Gaussian kernel in train-only empirical-percentile space',
            'outer_fold': 'calendar-year expanding walk-forward with 10-session boundary gap',
            'selector': 'pair+bandwidth chosen using earlier walk-forward years only',
            'inference': 'one-sided Newey-West/HAC on event-level squared-error or regret improvement; BH-FDR across all 18 index×target tests',
            'fdr_level': FDR_LEVEL,
        },
        'instruments': {},
    }
    tests = []
    for sym in SYMS:
        bars = data['instruments'][sym]['bars']
        rows = add_path_targets(bars, prepare(data, sym, state_map))
        metrics, folds, years = precompute(rows, bars)
        stests = []
        for target in [*CONT_TARGETS.keys(), 'best_hold']:
            t = nested_target(metrics, years, target)
            if t:
                t['symbol'] = sym
                t['name'] = data['instruments'][sym]['name']
                stests.append(t)
                tests.append(t)
        result['instruments'][sym] = {'name': data['instruments'][sym]['name'], 'n_D1': len(rows), 'folds': folds, 'tests': stests}

    adj = [{'p_value': t['p_value']} for t in tests]
    bh_adjust(adj)
    for t, a in zip(tests, adj):
        t['q_value'] = a['q_value']
        t['confirmed'] = bool(
            t['q_value'] is not None and t['q_value'] <= FDR_LEVEL
            and t['effect'] is not None and t['effect'] > 0
            and t['positive_year_rate'] >= 0.60
            and t['outer_event_n'] >= 500
        )

    result['summary'] = {
        'tested': len(tests),
        'confirmed': sum(t['confirmed'] for t in tests),
        'tests': [
            {
                'symbol':t['symbol'],'name':t['name'],'target':t['target'],'label':t['label'],
                'outer_years':t['outer_years'],'outer_event_n':t['outer_event_n'],
                'effect':t['effect'],'positive_year_rate':t['positive_year_rate'],
                'p_value':t['p_value'],'q_value':t['q_value'],'confirmed':t['confirmed'],
                'top_combos':list(t['combo_frequency'].items())[:4],
                **({'avg_normalized_skill':t['avg_normalized_skill']} if 'avg_normalized_skill' in t else {}),
                **({'regret_improvement':t['regret_improvement'],'avg_model_hit_rate':t['avg_model_hit_rate'],'avg_base_hit_rate':t['avg_base_hit_rate']} if t['target']=='best_hold' else {}),
            }
            for t in tests
        ],
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result['summary'], ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
