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
OUT = Path('docs/data/nested_continuous_surface.json')

SYMS = ('^GSPC', '^IXIC', '^DJI')
BANDWIDTHS = (0.12, 0.20)
BOUNDARY_GAP = 10
MIN_TRAIN_N = 400
MIN_SELECTOR_YEARS = 8
MIN_SELECTOR_EVENTS = 200
MIN_EFFECTIVE_N = 25.0
FDR_LEVEL = 0.10


def avg(xs):
    z = [float(x) for x in xs if x is not None and math.isfinite(float(x))]
    return statistics.fmean(z) if z else None


def median(xs):
    z = sorted(float(x) for x in xs if x is not None and math.isfinite(float(x)))
    if not z:
        return None
    n = len(z)
    if n % 2:
        return z[n // 2]
    return 0.5 * (z[n // 2 - 1] + z[n // 2])


def pct_map(train_values, query_values):
    s = np.sort(np.asarray(train_values, dtype=float))
    q = np.asarray(query_values, dtype=float)
    # Empirical percentile coordinates learned from training only.
    return np.searchsorted(s, q, side='right') / max(len(s), 1)


def normal_sf(z):
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def combo_name(pair, bw):
    return f'{pair[0]}×{pair[1]}|bw={bw:.2f}'


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

    # One distance matrix serves both fixed bandwidths and all horizons.
    d2 = (test_x[:, None] - train_x[None, :]) ** 2 + (test_y[:, None] - train_y[None, :]) ** 2
    ret_matrix = {h: np.asarray([r[f'h{h}_ret'] for r in train], dtype=float) for h in HORIZONS}
    up_matrix = {h: (ret_matrix[h] > 0).astype(float) for h in HORIZONS}

    outputs = {}
    for bw in BANDWIDTHS:
        w = np.exp(-0.5 * d2 / (bw * bw))
        sw = np.maximum(w.sum(axis=1), 1e-15)
        eff = sw * sw / np.maximum((w * w).sum(axis=1), 1e-15)
        by_h = {}
        for h in HORIZONS:
            by_h[h] = {
                'prob': (w @ up_matrix[h]) / sw,
                'mean': (w @ ret_matrix[h]) / sw,
                'effective_n': eff,
            }
        outputs[bw] = by_h
    return outputs


def baseline_stats(train, h):
    r = np.asarray([x[f'h{h}_ret'] for x in train], dtype=float)
    return {
        'prob': float(np.mean(r > 0)),
        'mean': float(np.mean(r)),
    }


def year_combo_metrics(test, preds, base, h):
    actual = np.asarray([r[f'h{h}_ret'] for r in test], dtype=float)
    y = (actual > 0).astype(float)
    prob = np.asarray(preds['prob'], dtype=float)
    mean_pred = np.asarray(preds['mean'], dtype=float)
    eff = np.asarray(preds['effective_n'], dtype=float)

    base_brier = (base['prob'] - y) ** 2
    model_brier = (prob - y) ** 2
    base_ae = np.abs(actual - base['mean'])
    model_ae = np.abs(actual - mean_pred)

    # Evaluation-only same-year baseline for the selected positive ridge.
    year_mean = float(np.mean(actual))
    year_median = float(np.median(actual))
    year_up = 100.0 * float(np.mean(y))
    ridge = (prob > base['prob']) & (mean_pred > base['mean']) & (eff >= MIN_EFFECTIVE_N)
    ridx = np.where(ridge)[0]

    ridge_stats = {
        'n': int(len(ridx)),
        'mean': float(np.mean(actual[ridx])) if len(ridx) else None,
        'median': float(np.median(actual[ridx])) if len(ridx) else None,
        'up_pct': 100.0 * float(np.mean(y[ridx])) if len(ridx) else None,
        'mean_edge_vs_year_D1': float(np.mean(actual[ridx]) - year_mean) if len(ridx) else None,
        'median_edge_vs_year_D1': float(np.median(actual[ridx]) - year_median) if len(ridx) else None,
        'up_edge_pp_vs_year_D1': 100.0 * float(np.mean(y[ridx])) - year_up if len(ridx) else None,
    }

    return {
        'n': len(test),
        'baseline_brier': float(np.mean(base_brier)),
        'baseline_return_mae': float(np.mean(base_ae)),
        'brier_improvement': float(np.mean(base_brier - model_brier)),
        'return_mae_improvement': float(np.mean(base_ae - model_ae)),
        'ridge': ridge_stats,
        '_event': {
            'actual': actual,
            'brier_improvement': base_brier - model_brier,
            'return_mae_improvement': base_ae - model_ae,
            'ridge_mask': ridge,
            'year_mean': year_mean,
        },
    }


def selector_score(history):
    if len(history) < MIN_SELECTOR_YEARS:
        return None
    if sum(x['n'] for x in history) < MIN_SELECTOR_EVENTS:
        return None
    bskill = []
    rskill = []
    for x in history:
        if x['baseline_brier'] > 0:
            bskill.append(x['brier_improvement'] / x['baseline_brier'])
        if x['baseline_return_mae'] > 0:
            rskill.append(x['return_mae_improvement'] / x['baseline_return_mae'])
    if not bskill or not rskill:
        return None
    mb = avg(bskill)
    mr = avg(rskill)
    # Equal-weight classification calibration and continuous-return accuracy.
    score = 0.5 * (mb + mr)
    return {
        'score': score,
        'brier_skill': mb,
        'return_mae_skill': mr,
        'dual_positive': bool(mb > 0 and mr > 0),
        'years': len(history),
        'events': sum(x['n'] for x in history),
    }


def precompute_symbol(rows):
    rows = sorted(rows, key=lambda r: r['idx'])
    years = sorted({int(r['year']) for r in rows})
    by_year = {y: [r for r in rows if int(r['year']) == y] for y in years}
    metrics = defaultdict(dict)  # (combo, h) -> year -> metrics
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
        bases = {h: baseline_stats(train, h) for h in HORIZONS}
        folds.append({'year': year, 'train_n': len(train), 'test_n': len(test), 'cutoff_idx': cutoff})
        for pair in PAIRS:
            pair_preds = predict_pair(train, test, pair)
            for bw in BANDWIDTHS:
                cname = combo_name(pair, bw)
                for h in HORIZONS:
                    metrics[(cname, h)][year] = year_combo_metrics(test, pair_preds[bw][h], bases[h], h)
    return metrics, folds, years


def nested_select(metrics, years, h):
    combos = sorted({k[0] for k in metrics if k[1] == h})
    selections = []
    event_brier = []
    event_return = []
    ridge_event_edge = []
    ridge_year_edges = []

    for year in years:
        candidates = []
        for c in combos:
            current = metrics[(c, h)].get(year)
            if current is None:
                continue
            hist = [metrics[(c, h)][y] for y in sorted(metrics[(c, h)]) if y < year]
            ss = selector_score(hist)
            if ss is not None:
                candidates.append((c, ss, current))
        if not candidates:
            continue
        dual = [x for x in candidates if x[1]['dual_positive']]
        pool = dual if dual else candidates
        c, ss, cur = max(pool, key=lambda x: (x[1]['score'], x[1]['events'], x[0]))

        ev = cur['_event']
        event_brier.extend(float(x) for x in ev['brier_improvement'])
        event_return.extend(float(x) for x in ev['return_mae_improvement'])
        mask = ev['ridge_mask']
        actual = ev['actual']
        if int(np.sum(mask)) > 0:
            edges = actual[mask] - ev['year_mean']
            ridge_event_edge.extend(float(x) for x in edges)
            ridge_year_edges.append(float(np.mean(edges)))

        selections.append({
            'year': year,
            'combo': c,
            'selector_score': ss['score'],
            'selector_brier_skill': ss['brier_skill'],
            'selector_return_mae_skill': ss['return_mae_skill'],
            'selector_dual_positive': ss['dual_positive'],
            'prior_validation_years': ss['years'],
            'prior_validation_events': ss['events'],
            'test_n': cur['n'],
            'brier_improvement': cur['brier_improvement'],
            'return_mae_improvement': cur['return_mae_improvement'],
            'ridge': cur['ridge'],
        })

    if not selections:
        return None
    p_brier = nw_one_sided_p(event_brier, lag=max(HORIZONS))
    p_return = nw_one_sided_p(event_return, lag=max(HORIZONS))
    p_ridge = nw_one_sided_p(ridge_event_edge, lag=max(HORIZONS)) if len(ridge_event_edge) >= 3 else None
    joint = max(x for x in (p_brier, p_return, p_ridge) if x is not None)
    ridge_n = len(ridge_event_edge)
    pos_ridge_years = sum(x > 0 for x in ridge_year_edges)
    combo_freq = Counter(x['combo'] for x in selections)
    return {
        'horizon': h,
        'outer_years': len(selections),
        'outer_event_n': sum(x['test_n'] for x in selections),
        'brier_improvement': avg(event_brier),
        'return_mae_improvement': avg(event_return),
        'ridge_n': ridge_n,
        'ridge_mean_edge_vs_same_year_D1': avg(ridge_event_edge),
        'ridge_positive_years': pos_ridge_years,
        'ridge_years': len(ridge_year_edges),
        'ridge_positive_year_rate': pos_ridge_years / len(ridge_year_edges) if ridge_year_edges else None,
        'p_brier': p_brier,
        'p_return_mae': p_return,
        'p_ridge': p_ridge,
        'p_joint': joint,
        'combo_frequency': dict(combo_freq.most_common()),
        'year_selections': selections,
    }


def main():
    data = json.loads(SRC.read_text())
    state_map = build_sp_state_map(data['instruments']['^GSPC']['bars'])
    result = {
        'schema': 'NESTED-CONTINUOUS-SURFACE-V1',
        'note': 'Historical nested walk-forward methodology test on D1 events. Each year surface predictions use only prior data; pair/bandwidth selection uses only prior walk-forward validation years. The feature-pair menu was defined during earlier research, so this is not pristine independent forward evidence and must not modify Frozen V4 MAIN rules.',
        'method': {
            'event': 'D1 only',
            'pairs': PAIRS,
            'bandwidths_percentile_space': BANDWIDTHS,
            'surface': '2D Gaussian kernel in train-only empirical-percentile coordinates',
            'outer_fold': 'calendar-year expanding walk-forward',
            'boundary_gap_sessions': BOUNDARY_GAP,
            'selector': 'for each test year/horizon, select pair+bandwidth using only earlier walk-forward years; equal-weight normalized Brier skill and return-MAE skill; prefer dual-positive candidates',
            'minimum_training_n': MIN_TRAIN_N,
            'minimum_selector_years': MIN_SELECTOR_YEARS,
            'minimum_selector_events': MIN_SELECTOR_EVENTS,
            'ridge_definition': 'predicted up probability > train D1 baseline AND predicted mean return > train D1 baseline AND kernel effective N >= 25',
            'inference': 'one-sided Newey-West/HAC on event-level Brier improvement, return-MAE improvement, and ridge return edge; joint p=max of the three; BH-FDR across 3 indices × 4 horizons',
            'fdr_level': FDR_LEVEL,
        },
        'instruments': {},
    }

    tests = []
    for sym in SYMS:
        bars = data['instruments'][sym]['bars']
        rows = prepare(data, sym, state_map)
        metrics, folds, years = precompute_symbol(rows)
        htests = []
        for h in HORIZONS:
            t = nested_select(metrics, years, h)
            if t:
                t['symbol'] = sym
                t['name'] = data['instruments'][sym]['name']
                htests.append(t)
                tests.append(t)
        result['instruments'][sym] = {
            'name': data['instruments'][sym]['name'],
            'n_D1': len(rows),
            'folds': folds,
            'tests': htests,
        }

    # One family: all 12 outer tests. Joint p already requires all three evidence legs.
    bh_rows = [{'p_value': t['p_joint']} for t in tests]
    bh_adjust(bh_rows)
    for t, qrow in zip(tests, bh_rows):
        t['q_joint'] = qrow['q_value']
        t['confirmed'] = bool(
            t['q_joint'] is not None and t['q_joint'] <= FDR_LEVEL
            and t['brier_improvement'] is not None and t['brier_improvement'] > 0
            and t['return_mae_improvement'] is not None and t['return_mae_improvement'] > 0
            and t['ridge_n'] >= 100
            and t['ridge_mean_edge_vs_same_year_D1'] is not None and t['ridge_mean_edge_vs_same_year_D1'] > 0
            and t['ridge_positive_year_rate'] is not None and t['ridge_positive_year_rate'] >= 0.60
        )

    result['summary'] = {
        'tested': len(tests),
        'confirmed': sum(bool(t.get('confirmed')) for t in tests),
        'tests': [
            {
                'symbol': t['symbol'], 'name': t['name'], 'horizon': t['horizon'],
                'outer_years': t['outer_years'], 'outer_event_n': t['outer_event_n'],
                'brier_improvement': t['brier_improvement'],
                'return_mae_improvement': t['return_mae_improvement'],
                'ridge_n': t['ridge_n'],
                'ridge_mean_edge_vs_same_year_D1': t['ridge_mean_edge_vs_same_year_D1'],
                'ridge_positive_year_rate': t['ridge_positive_year_rate'],
                'p_joint': t['p_joint'], 'q_joint': t['q_joint'],
                'confirmed': t['confirmed'],
                'top_combos': list(t['combo_frequency'].items())[:4],
            }
            for t in tests
        ],
    }

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result['summary'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
