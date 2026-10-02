from __future__ import annotations

import json
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
OUT = Path('docs/data/pattern_edge_oos_summary.json')
MIN_DETAIL_N = 30
TOP_N = 15


def avg(xs):
    xs = [float(x) for x in xs]
    return statistics.fmean(xs) if xs else None


def cell_key(r):
    return (r['streak_bucket'], r['market_state'], r['position'], r['volatility'])


def evaluate_horizon(bars, rows, h):
    by_year = defaultdict(list)
    for r in rows:
        by_year[r['year']].append(r)

    base_groups = defaultdict(list)
    cell_groups = defaultdict(list)
    records = defaultdict(list)

    for year in sorted(by_year):
        test = by_year[year]
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

        for r in test:
            sb = r['streak_bucket']
            key = cell_key(r)
            bs = base_stats.get(sb)
            cs = cell_stats.get(key)
            if not bs or not cs:
                continue
            actual = outcomes(bars, r, h)['ret']
            records[key].append({
                'actual_up': actual > 0,
                'actual_ret': actual,
                'base_up': bs['up_pct'],
                'cell_up': cs['up_pct'],
                'base_median': bs['median'],
                'cell_median': cs['median'],
            })

        for r in test:
            sb = r['streak_bucket']
            base_groups[sb].append(r)
            cell_groups[cell_key(r)].append(r)

    details = []
    for key, recs in records.items():
        if len(recs) < MIN_DETAIL_N:
            continue
        sb, ms, pos, vol = key
        base_brier = avg((r['base_up'] / 100 - (1 if r['actual_up'] else 0)) ** 2 for r in recs)
        cell_brier = avg((r['cell_up'] / 100 - (1 if r['actual_up'] else 0)) ** 2 for r in recs)
        base_mae = avg(abs(r['actual_ret'] - r['base_median']) for r in recs)
        cell_mae = avg(abs(r['actual_ret'] - r['cell_median']) for r in recs)
        details.append({
            'streak': sb,
            'market_state': ms,
            'position': pos,
            'volatility': vol,
            'n': len(recs),
            'actual_up_pct': 100 * sum(r['actual_up'] for r in recs) / len(recs),
            'avg_base_up_pct': avg(r['base_up'] for r in recs),
            'avg_cell_up_pct': avg(r['cell_up'] for r in recs),
            'brier_improvement': base_brier - cell_brier,
            'median_mae_improvement': base_mae - cell_mae,
            'both_improve': (base_brier > cell_brier and base_mae > cell_mae),
        })

    best = sorted(details, key=lambda x: (not x['both_improve'], -x['brier_improvement'], -x['median_mae_improvement']))[:TOP_N]
    worst = sorted(details, key=lambda x: (x['brier_improvement'], x['median_mae_improvement']))[:TOP_N]
    return {
        'tested_cells': len(details),
        'brier_improved_cells': sum(x['brier_improvement'] > 0 for x in details),
        'both_improved_cells': sum(x['both_improve'] for x in details),
        'top_cells': best,
        'worst_cells': worst,
        'all_cells': details,
    }


def stable_cells(by_horizon):
    bucket = defaultdict(list)
    meta = {}
    for h, block in by_horizon.items():
        for x in block['all_cells']:
            key = (x['streak'], x['market_state'], x['position'], x['volatility'])
            bucket[key].append((int(h), x))
            meta[key] = {k: x[k] for k in ('streak','market_state','position','volatility')}
    out = []
    for key, vals in bucket.items():
        both = [x for _, x in vals if x['both_improve']]
        brier_pos = [x for _, x in vals if x['brier_improvement'] > 0]
        if len(both) < 2:
            continue
        row = dict(meta[key])
        row.update({
            'horizons_available': [h for h, _ in vals],
            'both_improve_horizons': [h for h, x in vals if x['both_improve']],
            'brier_improve_horizons': [h for h, x in vals if x['brier_improvement'] > 0],
            'min_n': min(x['n'] for _, x in vals),
            'avg_brier_improvement': avg(x['brier_improvement'] for _, x in vals),
            'avg_median_mae_improvement': avg(x['median_mae_improvement'] for _, x in vals),
        })
        out.append(row)
    return sorted(out, key=lambda x: (-len(x['both_improve_horizons']), -x['avg_brier_improvement'], -x['avg_median_mae_improvement']))[:25]


def main():
    data = json.loads(SRC.read_text())
    sp_bars = data['instruments']['^GSPC']['bars']
    state_map = build_sp_state_map(sp_bars)
    result = {
        'schema': 'PATTERN-EDGE-OOS-SUMMARY-V1',
        'note': 'Discovery-stage pseudo-OOS. Cell rankings are multiple-comparison sensitive and are not trading recommendations.',
        'minimum_training_cell_n': MIN_CELL_N,
        'minimum_test_cell_n': MIN_DETAIL_N,
        'instruments': {},
    }
    printable = {}
    for sym in SYMS:
        inst = data['instruments'][sym]
        bars = inst['bars']
        rr = [r for r in feature_rows(bars, state_map) if r['streak_bucket'] != 'FLAT']
        by_h = {str(h): evaluate_horizon(bars, rr, h) for h in HORIZONS}
        stable = stable_cells(by_h)
        result['instruments'][sym] = {
            'name': inst['name'],
            'horizons': by_h,
            'stable_cells': stable,
        }
        printable[sym] = {
            'name': inst['name'],
            'counts': {h: {
                'tested': by_h[h]['tested_cells'],
                'brier_improved': by_h[h]['brier_improved_cells'],
                'both_improved': by_h[h]['both_improved_cells'],
            } for h in by_h},
            'stable_cells': stable[:10],
        }

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(printable, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
