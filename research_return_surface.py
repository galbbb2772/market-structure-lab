from __future__ import annotations

import bisect
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

from research_pattern_edge_map import build_sp_state_map, feature_rows, outcomes
from research_sp500_survivor_diagnostic import enrich

SRC = Path('docs/data/structure_lab.json')
OUT = Path('docs/data/return_surface.json')
HORIZONS = (1, 3, 5, 10)
GRID_SIZES = (4, 5, 6)
MAIN_GRID = 5
MIN_CELL = 30
MIN_ERA_CELL = 10
PAIRS = [
    ('ma20_dist', 'ma200_dist'),
    ('ma50_dist', 'ma200_dist'),
    ('dd20', 'atr_rank'),
    ('pos60', 'atr_rank'),
    ('ma20_dist', 'dd20'),
    ('pre5', 'atr_rank'),
]
ERAS = [
    ('pre_1980', None, 1979),
    ('1980_1999', 1980, 1999),
    ('2000_2009', 2000, 2009),
    ('2010_2019', 2010, 2019),
    ('2020_2026', 2020, 2026),
]


def finite(xs):
    return [float(x) for x in xs if x is not None and math.isfinite(float(x))]


def avg(xs):
    z = finite(xs)
    return statistics.fmean(z) if z else None


def quantile(xs, p):
    s = sorted(finite(xs))
    if not s:
        return None
    z = (len(s) - 1) * p
    i = int(z)
    f = z - i
    return s[i] + (s[min(i + 1, len(s) - 1)] - s[i]) * f


def era_name(year):
    for name, lo, hi in ERAS:
        if (lo is None or year >= lo) and year <= hi:
            return name
    return 'other'


def summary(rows, h):
    if not rows:
        return {'n': 0}
    ret = [r[f'h{h}_ret'] for r in rows]
    return {
        'n': len(rows),
        'up_pct': 100 * sum(x > 0 for x in ret) / len(ret),
        'mean': avg(ret),
        'median': quantile(ret, .5),
        'p25': quantile(ret, .25),
        'p75': quantile(ret, .75),
        'avg_mfe': avg(r[f'h{h}_mfe'] for r in rows),
        'avg_mae': avg(r[f'h{h}_mae'] for r in rows),
    }


def prepare(data, sym, state_map):
    bars = data['instruments'][sym]['bars']
    base = [r for r in feature_rows(bars, state_map) if r['streak_bucket'] == 'D1']
    base = enrich(bars, base)
    out = []
    for r in base:
        if r['idx'] + max(HORIZONS) >= len(bars):
            continue
        q = dict(r)
        ok = True
        for h in HORIZONS:
            o = outcomes(bars, r, h)
            if not o or o.get('ret') is None:
                ok = False
                break
            q[f'h{h}_ret'] = float(o['ret'])
            q[f'h{h}_mfe'] = float(o['mfe'])
            q[f'h{h}_mae'] = float(o['mae'])
        if not ok:
            continue
        if all(q.get(k) is not None and math.isfinite(float(q[k])) for pair in PAIRS for k in pair):
            q['era'] = era_name(int(q['year']))
            out.append(q)
    return out


def edges(rows, key, nbin):
    xs = [r[key] for r in rows]
    return [quantile(xs, j / nbin) for j in range(1, nbin)]


def bin_id(value, cuts):
    return bisect.bisect_right(cuts, float(value))


def bounds(cuts, idx):
    lo = None if idx == 0 else cuts[idx - 1]
    hi = None if idx == len(cuts) else cuts[idx]
    return lo, hi


def build_surface(rows, xkey, ykey, h, nbin):
    xcuts = edges(rows, xkey, nbin)
    ycuts = edges(rows, ykey, nbin)
    baseline = summary(rows, h)
    era_baseline = {name: summary([r for r in rows if r['era'] == name], h) for name, _, _ in ERAS}
    cells = defaultdict(list)
    for r in rows:
        cells[(bin_id(r[xkey], xcuts), bin_id(r[ykey], ycuts))].append(r)

    raw = {}
    for i in range(nbin):
        for j in range(nbin):
            z = cells.get((i, j), [])
            s = summary(z, h)
            s['i'] = i
            s['j'] = j
            s['x_bounds'] = bounds(xcuts, i)
            s['y_bounds'] = bounds(ycuts, j)
            if s['n']:
                s['median_edge'] = s['median'] - baseline['median']
                s['up_edge_pp'] = s['up_pct'] - baseline['up_pct']
            else:
                s['median_edge'] = None
                s['up_edge_pp'] = None

            era_stats = {}
            eligible = pos_med = pos_up = 0
            for ename, _, _ in ERAS:
                ez = [r for r in z if r['era'] == ename]
                es = summary(ez, h)
                eb = era_baseline[ename]
                if es['n'] >= MIN_ERA_CELL and eb['n']:
                    eligible += 1
                    es['median_edge_vs_era'] = es['median'] - eb['median']
                    es['up_edge_pp_vs_era'] = es['up_pct'] - eb['up_pct']
                    if es['median_edge_vs_era'] > 0:
                        pos_med += 1
                    if es['up_edge_pp_vs_era'] > 0:
                        pos_up += 1
                else:
                    es['median_edge_vs_era'] = None
                    es['up_edge_pp_vs_era'] = None
                era_stats[ename] = es
            s['eras'] = era_stats
            s['eligible_eras'] = eligible
            s['positive_median_eras'] = pos_med
            s['positive_up_eras'] = pos_up
            s['positive_median_era_frac'] = pos_med / eligible if eligible else None
            s['positive_up_era_frac'] = pos_up / eligible if eligible else None
            raw[(i, j)] = s

    for (i, j), s in raw.items():
        support = 0
        eligible_neighbors = 0
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = raw.get((i + di, j + dj))
            if not n or n['n'] < MIN_CELL:
                continue
            eligible_neighbors += 1
            if n['median_edge'] is not None and n['median_edge'] > 0:
                support += 1
        s['adjacent_positive_median_neighbors'] = support
        s['eligible_neighbors'] = eligible_neighbors
        s['persistent_positive'] = bool(
            s['n'] >= MIN_CELL
            and s['eligible_eras'] >= 3
            and (s['positive_median_era_frac'] or 0) >= .75
            and (s['positive_up_era_frac'] or 0) >= .60
            and support >= 2
            and s['median_edge'] is not None and s['median_edge'] > 0
        )

    out_cells = [raw[(i, j)] for i in range(nbin) for j in range(nbin)]
    candidates = [c for c in out_cells if c['n'] >= MIN_CELL and c['median_edge'] is not None]
    candidates.sort(key=lambda c: (
        c['positive_median_era_frac'] if c['positive_median_era_frac'] is not None else -1,
        c['adjacent_positive_median_neighbors'],
        c['median_edge'],
        c['n'],
    ), reverse=True)
    return {
        'x': xkey, 'y': ykey, 'horizon': h, 'grid': nbin,
        'x_cuts': xcuts, 'y_cuts': ycuts,
        'baseline': baseline,
        'era_baseline': era_baseline,
        'cells': out_cells,
        'persistent_positive_count': sum(1 for c in out_cells if c['persistent_positive']),
        'top_cells': candidates[:8],
    }


def compact_surface(s):
    return {
        'pair': f"{s['x']} × {s['y']}",
        'horizon': s['horizon'],
        'grid': s['grid'],
        'persistent_positive_count': s['persistent_positive_count'],
        'top_cells': [
            {k: c[k] for k in (
                'i','j','n','x_bounds','y_bounds','up_pct','median','median_edge','up_edge_pp',
                'eligible_eras','positive_median_eras','positive_up_eras',
                'positive_median_era_frac','positive_up_era_frac','adjacent_positive_median_neighbors',
                'persistent_positive'
            )}
            for c in s['top_cells'][:4]
        ],
    }


def main():
    data = json.loads(SRC.read_text())
    state_map = build_sp_state_map(data['instruments']['^GSPC']['bars'])
    result = {
        'schema': 'CONDITIONAL-RETURN-SURFACE-V1',
        'note': 'Descriptive conditional return surfaces on D1 events. Quantile grids reveal broad ridges/valleys; era consistency and neighboring-cell support are used to distinguish plateaus from isolated cells. This is structural research, not independent OOS alpha evidence.',
        'config': {
            'horizons': HORIZONS,
            'grid_sizes': GRID_SIZES,
            'main_grid': MAIN_GRID,
            'min_cell': MIN_CELL,
            'min_era_cell': MIN_ERA_CELL,
            'pairs': PAIRS,
            'eras': [x[0] for x in ERAS],
        },
        'instruments': {},
    }
    printable = {}
    for sym in ['^GSPC', '^IXIC', '^DJI']:
        rows = prepare(data, sym, state_map)
        surfaces = []
        for xkey, ykey in PAIRS:
            for h in HORIZONS:
                for g in GRID_SIZES:
                    surfaces.append(build_surface(rows, xkey, ykey, h, g))
        result['instruments'][sym] = {
            'name': data['instruments'][sym]['name'],
            'n_D1': len(rows),
            'surfaces': surfaces,
        }
        printable[sym] = {
            'name': data['instruments'][sym]['name'],
            'n_D1': len(rows),
            'main_grid_t5': [compact_surface(s) for s in surfaces if s['grid'] == MAIN_GRID and s['horizon'] == 5],
        }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(printable, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
