from __future__ import annotations

import bisect
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

from research_pattern_edge_map import (
    HORIZONS,
    MIN_CELL_N,
    SYMS,
    build_sp_state_map,
    feature_rows,
    outcomes,
    summarize,
)

SRC = Path('docs/data/structure_lab.json')
OUT = Path('docs/data/pattern_purged_validation.json')

# Strictly forward-only training. A 10-session gap is left before every test-year
# boundary. Because no post-test observations are ever admitted into that fold's
# training set, a classical post-test embargo is structurally unnecessary.
BOUNDARY_GAP = max(HORIZONS)  # 10 sessions
MIN_OOS_N = 40
NW_LAG = 5
FDR_LEVEL = 0.10
STRONG_FDR = 0.05


def avg(xs):
    xs = [float(x) for x in xs]
    return statistics.fmean(xs) if xs else None


def cell_key(r):
    return (r['streak_bucket'], r['market_state'], r['position'], r['volatility'])


def normal_sf(z):
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def nw_one_sided_p(diffs, lag=NW_LAG):
    """One-sided H1: mean paired improvement > 0, HAC/Newey-West approximation."""
    x = [float(v) for v in diffs if v is not None and math.isfinite(float(v))]
    n = len(x)
    if n < 3:
        return None
    mu = avg(x)
    e = [v - mu for v in x]
    gamma0 = sum(v * v for v in e) / n
    lrv = gamma0
    max_lag = min(lag, n - 1)
    for L in range(1, max_lag + 1):
        weight = 1.0 - L / (max_lag + 1.0)
        gamma = sum(e[t] * e[t - L] for t in range(L, n)) / n
        lrv += 2.0 * weight * gamma
    lrv = max(lrv, 1e-18)
    se = math.sqrt(lrv / n)
    z = mu / se if se > 0 else 0.0
    return normal_sf(z)


def bh_adjust(rows, p_field='p_value', out_field='q_value'):
    valid = [(i, r[p_field]) for i, r in enumerate(rows) if r.get(p_field) is not None]
    valid.sort(key=lambda x: x[1])
    m = len(valid)
    running = 1.0
    for rank_rev in range(m - 1, -1, -1):
        idx, p = valid[rank_rev]
        rank = rank_rev + 1
        q = min(running, p * m / rank)
        running = q
        rows[idx][out_field] = min(1.0, q)
    for r in rows:
        if out_field not in r:
            r[out_field] = None
    return rows


def fold_predictions(bars, rows, h):
    rows = sorted(rows, key=lambda r: r['idx'])
    idxs = [r['idx'] for r in rows]
    by_year = defaultdict(list)
    for r in rows:
        by_year[r['year']].append(r)

    records = defaultdict(list)
    fold_meta = []
    for year in sorted(by_year):
        test = by_year[year]
        if not test:
            continue
        first_test_idx = min(r['idx'] for r in test)
        cutoff_idx = first_test_idx - BOUNDARY_GAP - 1
        stop = bisect.bisect_right(idxs, cutoff_idx)
        train = rows[:stop]
        if not train:
            continue

        # The boundary gap is >= all tested horizons, so train labels cannot
        # overlap the test year. Keep an explicit assertion for auditability.
        train = [r for r in train if r['idx'] + h < first_test_idx]

        base_groups = defaultdict(list)
        cell_groups = defaultdict(list)
        for r in train:
            base_groups[r['streak_bucket']].append(r)
            cell_groups[cell_key(r)].append(r)

        base_stats = {
            k: summarize(bars, g, h)
            for k, g in base_groups.items()
            if len(g) >= MIN_CELL_N
        }
        cell_stats = {
            k: summarize(bars, g, h)
            for k, g in cell_groups.items()
            if len(g) >= MIN_CELL_N
        }

        used = 0
        for r in test:
            sb = r['streak_bucket']
            key = cell_key(r)
            bs = base_stats.get(sb)
            cs = cell_stats.get(key)
            if not bs or not cs:
                continue
            actual = outcomes(bars, r, h)['ret']
            y = 1.0 if actual > 0 else 0.0
            base_prob = bs['up_pct'] / 100.0
            cell_prob = cs['up_pct'] / 100.0
            base_brier = (base_prob - y) ** 2
            cell_brier = (cell_prob - y) ** 2
            base_abs = abs(actual - bs['median'])
            cell_abs = abs(actual - cs['median'])
            records[key].append({
                'date': r['date'],
                'year': year,
                'actual_up': bool(y),
                'actual_ret': actual,
                'base_up_pct': bs['up_pct'],
                'cell_up_pct': cs['up_pct'],
                'base_median': bs['median'],
                'cell_median': cs['median'],
                'brier_improvement': base_brier - cell_brier,
                'median_ae_improvement': base_abs - cell_abs,
            })
            used += 1
        fold_meta.append({
            'test_year': year,
            'first_test_idx': first_test_idx,
            'training_cutoff_idx': cutoff_idx,
            'training_rows': len(train),
            'test_rows_used': used,
        })
    return records, fold_meta


def summarize_cell(key, recs, h):
    sb, ms, pos, vol = key
    bdiff = [r['brier_improvement'] for r in recs]
    mdiff = [r['median_ae_improvement'] for r in recs]
    by_year = defaultdict(list)
    for r in recs:
        by_year[r['year']].append(r)
    year_edges = {
        str(y): avg(x['brier_improvement'] for x in rs)
        for y, rs in sorted(by_year.items())
    }
    positive_years = sum(v > 0 for v in year_edges.values())
    tested_years = len(year_edges)
    p = nw_one_sided_p(bdiff)
    return {
        'horizon': h,
        'streak': sb,
        'market_state': ms,
        'position': pos,
        'volatility': vol,
        'n': len(recs),
        'years': tested_years,
        'positive_years': positive_years,
        'positive_year_rate': positive_years / tested_years if tested_years else None,
        'actual_up_pct': 100 * sum(r['actual_up'] for r in recs) / len(recs),
        'avg_base_up_pct': avg(r['base_up_pct'] for r in recs),
        'avg_cell_up_pct': avg(r['cell_up_pct'] for r in recs),
        'brier_improvement': avg(bdiff),
        'median_mae_improvement': avg(mdiff),
        'p_value': p,
        'year_brier_improvement': year_edges,
    }


def stable_across_horizons(tests):
    grouped = defaultdict(list)
    for x in tests:
        key = (x['streak'], x['market_state'], x['position'], x['volatility'])
        grouped[key].append(x)
    out = []
    for key, vals in grouped.items():
        survivors = [x for x in vals if x.get('survives_fdr')]
        strong = [x for x in vals if x.get('strong_survivor')]
        if not survivors:
            continue
        sb, ms, pos, vol = key
        out.append({
            'streak': sb,
            'market_state': ms,
            'position': pos,
            'volatility': vol,
            'surviving_horizons': sorted(x['horizon'] for x in survivors),
            'strong_horizons': sorted(x['horizon'] for x in strong),
            'min_n': min(x['n'] for x in survivors),
            'min_year_rate': min(x['positive_year_rate'] for x in survivors),
            'max_q': max(x['q_value'] for x in survivors),
            'avg_brier_improvement': avg(x['brier_improvement'] for x in survivors),
            'avg_median_mae_improvement': avg(x['median_mae_improvement'] for x in survivors),
        })
    return sorted(
        out,
        key=lambda x: (-len(x['strong_horizons']), -len(x['surviving_horizons']), x['max_q'], -x['min_n'])
    )


def main():
    data = json.loads(SRC.read_text())
    sp_bars = data['instruments']['^GSPC']['bars']
    state_map = build_sp_state_map(sp_bars)

    result = {
        'schema': 'PATTERN-PURGED-FDR-V1',
        'method': {
            'walk_forward': 'calendar-year expanding window; only prior observations enter training',
            'boundary_gap_sessions': BOUNDARY_GAP,
            'purge_rule': 'training feature dates within the boundary gap are excluded; every training label must end before test starts',
            'embargo_note': 'post-test embargo is not needed because folds are strictly forward-only and never train on future observations',
            'primary_loss': 'paired Brier loss: baseline(same signed streak bucket) vs conditioned cell',
            'secondary_loss': 'absolute error of forward-return median prediction',
            'serial_dependence': f'one-sided Newey-West/HAC normal approximation, lag={NW_LAG}',
            'multiple_testing': 'Benjamini-Hochberg FDR across every cell x horizon test within each index',
            'fdr_level': FDR_LEVEL,
            'strong_fdr_level': STRONG_FDR,
            'minimum_training_cell_n': MIN_CELL_N,
            'minimum_oos_cell_n': MIN_OOS_N,
        },
        'instruments': {},
    }

    printable = {}
    for sym in SYMS:
        inst = data['instruments'][sym]
        bars = inst['bars']
        rr = [r for r in feature_rows(bars, state_map) if r['streak_bucket'] != 'FLAT']
        tests = []
        folds = {}
        for h in HORIZONS:
            records, fold_meta = fold_predictions(bars, rr, h)
            folds[str(h)] = fold_meta
            for key, recs in records.items():
                if len(recs) < MIN_OOS_N:
                    continue
                tests.append(summarize_cell(key, recs, h))

        bh_adjust(tests)
        m = sum(x['p_value'] is not None for x in tests)
        for x in tests:
            x['bonferroni_p'] = min(1.0, x['p_value'] * m) if x['p_value'] is not None else None
            x['survives_fdr'] = bool(
                x['q_value'] is not None
                and x['q_value'] <= FDR_LEVEL
                and x['brier_improvement'] > 0
                and x['median_mae_improvement'] > 0
                and x['positive_year_rate'] >= 0.60
                and x['n'] >= 50
            )
            x['strong_survivor'] = bool(
                x['q_value'] is not None
                and x['q_value'] <= STRONG_FDR
                and x['brier_improvement'] > 0
                and x['median_mae_improvement'] > 0
                and x['positive_year_rate'] >= 2/3
                and x['n'] >= 80
            )

        stable = stable_across_horizons(tests)
        survivors = [x for x in tests if x['survives_fdr']]
        strong = [x for x in tests if x['strong_survivor']]
        rejected = [x for x in tests if not x['survives_fdr']]
        result['instruments'][sym] = {
            'name': inst['name'],
            'coverage': [rr[0]['date'], rr[-1]['date']] if rr else None,
            'tested_hypotheses': len(tests),
            'fdr_survivors': len(survivors),
            'strong_survivors': len(strong),
            'tests': tests,
            'stable_cells': stable,
            'folds': folds,
        }
        printable[sym] = {
            'name': inst['name'],
            'tested': len(tests),
            'fdr_survivors': len(survivors),
            'strong_survivors': len(strong),
            'stable_cells': stable[:12],
            'best_surviving_tests': sorted(
                survivors,
                key=lambda x: (x['q_value'], -x['n'], -x['brier_improvement'])
            )[:15],
            'rejected_count': len(rejected),
        }

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(printable, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
