from __future__ import annotations

import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from research_pattern_edge_map import build_sp_state_map
from research_pattern_purged_validation import bh_adjust, nw_one_sided_p
from research_return_surface import HORIZONS, PAIRS, prepare

SRC = Path('docs/data/structure_lab.json')
OUT = Path('docs/data/nested_excursion_targets.json')
SYMS = ('^GSPC', '^IXIC', '^DJI')
BANDWIDTHS = (0.12, 0.20)
BOUNDARY_GAP = 10
MIN_TRAIN_N = 400
MIN_SELECTOR_YEARS = 8
MIN_SELECTOR_EVENTS = 200
FDR_LEVEL = 0.10

TARGETS = ('mfe', 'downside', 'range', 'balance')


def avg(xs):
    z = [float(x) for x in xs if x is not None and math.isfinite(float(x))]
    return statistics.fmean(z) if z else None


def pct_map(train_values, query_values):
    s = np.sort(np.asarray(train_values, dtype=float))
    q = np.asarray(query_values, dtype=float)
    return np.searchsorted(s, q, side='right') / max(len(s), 1)


def combo_name(pair, bw):
    return f'{pair[0]}×{pair[1]}|bw={bw:.2f}'


def target_value(row, h, target):
    mfe = float(row[f'h{h}_mfe'])
    mae = float(row[f'h{h}_mae'])
    if target == 'mfe':
        return mfe
    if target == 'downside':
        return -mae
    if target == 'range':
        return mfe - mae
    if target == 'balance':
        return mfe + mae
    raise KeyError(target)


def predict_pair(train, test, pair):
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

    values = {
        (target, h): np.asarray([target_value(r, h, target) for r in train], dtype=float)
        for target in TARGETS for h in HORIZONS
    }
    out = {}
    for bw in BANDWIDTHS:
        w = np.exp(-0.5 * d2 / (bw * bw))
        sw = np.maximum(w.sum(axis=1), 1e-15)
        eff = sw * sw / np.maximum((w * w).sum(axis=1), 1e-15)
        pred = {}
        for key, arr in values.items():
            pred[key] = (w @ arr) / sw
        out[bw] = {'pred': pred, 'effective_n': eff}
    return out


def baseline_stats(train, h, target):
    arr = np.asarray([target_value(r, h, target) for r in train], dtype=float)
    mu = float(np.mean(arr))
    return {'mean': mu}


def score_year(test, pred, base, h, target):
    actual = np.asarray([target_value(r, h, target) for r in test], dtype=float)
    model = np.asarray(pred, dtype=float)
    base_err = np.abs(actual - base['mean'])
    model_err = np.abs(actual - model)
    diff = base_err - model_err
    return {
        'n': len(actual),
        'baseline_mae': float(np.mean(base_err)),
        'model_mae': float(np.mean(model_err)),
        'mae_improvement': float(np.mean(diff)),
        'normalized_skill': float(np.mean(diff) / np.mean(base_err)) if np.mean(base_err) > 0 else None,
        '_event_diff': diff,
    }


def selector_score(history):
    if len(history) < MIN_SELECTOR_YEARS:
        return None
    events = sum(x['n'] for x in history)
    if events < MIN_SELECTOR_EVENTS:
        return None
    skills = [x['normalized_skill'] for x in history if x.get('normalized_skill') is not None]
    if not skills:
        return None
    return {'score': avg(skills), 'years': len(history), 'events': events}


def precompute(rows):
    rows = sorted(rows, key=lambda r: r['idx'])
    years = sorted({int(r['year']) for r in rows})
    by_year = {y: [r for r in rows if int(r['year']) == y] for y in years}
    metrics = defaultdict(dict)  # (combo,target,h) -> year -> score
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
        bases = {(target, h): baseline_stats(train, h, target) for target in TARGETS for h in HORIZONS}
        folds.append({'year': year, 'train_n': len(train), 'test_n': len(test), 'cutoff_idx': cutoff})
        for pair in PAIRS:
            pp = predict_pair(train, test, pair)
            for bw in BANDWIDTHS:
                cname = combo_name(pair, bw)
                for target in TARGETS:
                    for h in HORIZONS:
                        metrics[(cname, target, h)][year] = score_year(
                            test, pp[bw]['pred'][(target, h)], bases[(target, h)], h, target
                        )
    return metrics, folds, years


def nested_select(metrics, years, target, h):
    combos = sorted({k[0] for k in metrics if k[1] == target and k[2] == h})
    selections = []
    event_diffs = []
    year_edges = []

    for year in years:
        cand = []
        for c in combos:
            cur = metrics[(c, target, h)].get(year)
            if cur is None:
                continue
            hist = [metrics[(c, target, h)][y] for y in sorted(metrics[(c, target, h)]) if y < year]
            ss = selector_score(hist)
            if ss is not None:
                cand.append((c, ss, cur))
        if not cand:
            continue
        # No future threshold tuning: select the historically best prior-OOS normalized MAE skill.
        c, ss, cur = max(cand, key=lambda x: (x[1]['score'], x[1]['events'], x[0]))
        diffs = [float(x) for x in cur['_event_diff']]
        event_diffs.extend(diffs)
        year_edges.append(avg(diffs))
        selections.append({
            'year': year,
            'combo': c,
            'selector_score': ss['score'],
            'prior_validation_years': ss['years'],
            'prior_validation_events': ss['events'],
            'test_n': cur['n'],
            'baseline_mae': cur['baseline_mae'],
            'model_mae': cur['model_mae'],
            'mae_improvement': cur['mae_improvement'],
            'normalized_skill': cur['normalized_skill'],
        })

    if not selections:
        return None
    p = nw_one_sided_p(event_diffs, lag=max(HORIZONS))
    pos_years = sum(x > 0 for x in year_edges)
    base_mae = avg(s['baseline_mae'] for s in selections)
    model_mae = avg(s['model_mae'] for s in selections)
    return {
        'target': target,
        'horizon': h,
        'outer_years': len(selections),
        'outer_event_n': sum(x['test_n'] for x in selections),
        'baseline_mae': base_mae,
        'model_mae': model_mae,
        'mae_improvement': avg(event_diffs),
        'skill_pct': 100 * avg(event_diffs) / base_mae if base_mae and base_mae > 0 else None,
        'positive_years': pos_years,
        'positive_year_rate': pos_years / len(year_edges) if year_edges else None,
        'p_value': p,
        'combo_frequency': dict(Counter(x['combo'] for x in selections).most_common()),
        'year_selections': selections,
    }


def main():
    data = json.loads(SRC.read_text())
    state_map = build_sp_state_map(data['instruments']['^GSPC']['bars'])
    result = {
        'schema': 'NESTED-EXCURSION-TARGETS-V1',
        'note': 'Historical nested walk-forward test of whether D1 state geometry predicts excursion/risk magnitudes better than the prior-history D1 mean. Pair+bandwidth choice is based only on earlier walk-forward years. This is Shadow research and does not modify Frozen V4 MAIN.',
        'targets': {
            'mfe': 'maximum favorable excursion over horizon, percent from event close',
            'downside': 'magnitude of maximum adverse excursion = -MAE, percent',
            'range': 'MFE - MAE, a forward excursion-width proxy',
            'balance': 'MFE + MAE = favorable excursion minus adverse-excursion magnitude',
        },
        'method': {
            'event': 'D1 only',
            'pairs': PAIRS,
            'bandwidths': BANDWIDTHS,
            'outer_fold': 'calendar-year expanding walk-forward',
            'boundary_gap_sessions': BOUNDARY_GAP,
            'selector': 'within each target+horizon, choose pair+bandwidth using only earlier OOS years by normalized MAE skill',
            'primary_loss': 'absolute prediction error vs prior-history D1 mean baseline',
            'inference': 'one-sided Newey-West/HAC on event-level paired absolute-error improvement; BH-FDR across 3 indices × 4 horizons × 4 targets = 48 tests',
            'fdr_level': FDR_LEVEL,
        },
        'instruments': {},
    }

    tests = []
    for sym in SYMS:
        rows = prepare(data, sym, state_map)
        metrics, folds, years = precompute(rows)
        stests = []
        for target in TARGETS:
            for h in HORIZONS:
                t = nested_select(metrics, years, target, h)
                if t:
                    t['symbol'] = sym
                    t['name'] = data['instruments'][sym]['name']
                    stests.append(t)
                    tests.append(t)
        result['instruments'][sym] = {
            'name': data['instruments'][sym]['name'],
            'n_D1': len(rows),
            'folds': folds,
            'tests': stests,
        }

    bh_rows = [{'p_value': t['p_value']} for t in tests]
    bh_adjust(bh_rows)
    for t, qr in zip(tests, bh_rows):
        t['q_value'] = qr['q_value']
        t['confirmed'] = bool(
            t['q_value'] is not None and t['q_value'] <= FDR_LEVEL
            and t['mae_improvement'] is not None and t['mae_improvement'] > 0
            and t['positive_year_rate'] is not None and t['positive_year_rate'] >= 0.60
            and t['outer_event_n'] >= 500
        )

    ranked = sorted(tests, key=lambda t: (t['q_value'] if t['q_value'] is not None else 2, -float(t['skill_pct'] or -999)))
    result['summary'] = {
        'tested': len(tests),
        'confirmed': sum(bool(t['confirmed']) for t in tests),
        'confirmed_tests': [
            {k:t[k] for k in ('symbol','name','target','horizon','outer_years','outer_event_n','baseline_mae','model_mae','mae_improvement','skill_pct','positive_year_rate','p_value','q_value','confirmed')}
            for t in ranked if t['confirmed']
        ],
        'best_tests': [
            {**{k:t[k] for k in ('symbol','name','target','horizon','outer_years','outer_event_n','baseline_mae','model_mae','mae_improvement','skill_pct','positive_year_rate','p_value','q_value','confirmed')},
             'top_combos': list(t['combo_frequency'].items())[:4]}
            for t in ranked[:16]
        ],
    }

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result['summary'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
