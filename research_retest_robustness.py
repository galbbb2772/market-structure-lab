from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

from research_pattern_edge_map import build_sp_state_map, feature_rows, outcomes

SRC = Path('docs/data/structure_lab.json')
OUT = Path('docs/data/retest_robustness.json')
SYMS = ['^GSPC', '^IXIC', '^DJI']
H = 5


def avg(xs):
    xs = [float(x) for x in xs if x is not None and math.isfinite(float(x))]
    return statistics.fmean(xs) if xs else None


def median(xs):
    xs = sorted(float(x) for x in xs if x is not None and math.isfinite(float(x)))
    if not xs:
        return None
    n = len(xs)
    return xs[n//2] if n % 2 else (xs[n//2-1] + xs[n//2]) / 2


def enrich(bars, rows):
    cl = [float(b[4]) for b in bars]
    pref = [0.0]
    for x in cl:
        pref.append(pref[-1] + x)
    out = []
    for r in rows:
        i = r['idx']
        if i < 200:
            continue
        ma20 = (pref[i+1] - pref[i-19]) / 20
        ma50 = (pref[i+1] - pref[i-49]) / 50
        ma200 = (pref[i+1] - pref[i-199]) / 200
        rr = dict(r)
        rr.update({
            'day_ret': 100 * (cl[i] / cl[i-1] - 1),
            'prior_ret': 100 * (cl[i-1] / cl[i-2] - 1),
            'pre5': 100 * (cl[i] / cl[i-5] - 1),
            'pre10': 100 * (cl[i] / cl[i-10] - 1),
            'ma20_dist': 100 * (cl[i] / ma20 - 1),
            'ma50_dist': 100 * (cl[i] / ma50 - 1),
            'ma200_dist': 100 * (cl[i] / ma200 - 1),
        })
        out.append(rr)
    return out


def stat(bars, rows):
    vals = [outcomes(bars, r, H) for r in rows]
    rets = [x['ret'] for x in vals]
    if not rets:
        return {'n': 0}
    return {
        'n': len(rets),
        'up_pct': 100 * sum(x > 0 for x in rets) / len(rets),
        'mean': avg(rets),
        'median': median(rets),
        'avg_mfe': avg(x['mfe'] for x in vals),
        'avg_mae': avg(x['mae'] for x in vals),
    }


def eras(rows):
    bins = [
        ('pre_1980', lambda y: y < 1980),
        ('1980_1999', lambda y: 1980 <= y <= 1999),
        ('2000_2009', lambda y: 2000 <= y <= 2009),
        ('2010_2019', lambda y: 2010 <= y <= 2019),
        ('2020_2026', lambda y: 2020 <= y <= 2026),
    ]
    return {name: [r for r in rows if fn(r['year'])] for name, fn in bins}


def main():
    data = json.loads(SRC.read_text())
    sp_bars = data['instruments']['^GSPC']['bars']
    state_map = build_sp_state_map(sp_bars)
    result = {
        'schema': 'RETEST-ROBUSTNESS-V1',
        'note': 'Mechanism robustness only. Definitions were motivated by the previously discovered S&P survivor and are not an independent confirmation sample.',
        'target_horizon': 5,
        'instruments': {},
    }

    for sym in SYMS:
        inst = data['instruments'][sym]
        bars = inst['bars']
        rr = enrich(bars, feature_rows(bars, state_map))
        d1 = [r for r in rr if r['streak_bucket'] == 'D1']

        # Original strict state from the FDR survivor.
        original = [r for r in rr if r['streak_bucket']=='D1' and r['market_state']=='bull' and r['position']=='low' and r['volatility']=='mid']

        # Same structural idea with continuous thresholds widened modestly.
        relaxed = [r for r in rr if r['streak_bucket']=='D1' and r['market_state']=='bull' and r['pos60'] < 40 and 25 <= r['atr_rank'] < 75]

        # Mechanism-oriented retest proxy: bull trend intact, short-term weakness,
        # prior bounce then renewed down day, below MA50 but still above MA200.
        mechanism = [r for r in rr if r['market_state']=='bull' and r['streak_bucket']=='D1' and r['prior_ret'] > 0 and r['pre5'] < 0 and r['ma50_dist'] < 0 and r['ma200_dist'] > 0 and r['pos60'] < 40 and 25 <= r['atr_rank'] < 75]

        block = {
            'name': inst['name'],
            'baseline_D1': stat(bars, d1),
            'original_state': stat(bars, original),
            'relaxed_state': stat(bars, relaxed),
            'mechanism_proxy': stat(bars, mechanism),
            'era_breakdown': {},
        }
        for label, rows in [('original_state', original), ('relaxed_state', relaxed), ('mechanism_proxy', mechanism)]:
            block['era_breakdown'][label] = {k: stat(bars, v) for k, v in eras(rows).items()}
        result['instruments'][sym] = block

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
