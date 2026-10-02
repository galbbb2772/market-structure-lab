from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

from research_pattern_edge_map import build_sp_state_map, feature_rows, outcomes

SRC = Path('docs/data/structure_lab.json')
OUT = Path('docs/data/sp500_survivor_diagnostic.json')
TARGET = ('D1', 'bull', 'low', 'mid')
H = 5


def q(xs, p):
    s = sorted(float(x) for x in xs if x is not None and math.isfinite(float(x)))
    if not s:
        return None
    z = (len(s) - 1) * p
    i = int(z)
    f = z - i
    return s[i] + (s[min(i + 1, len(s) - 1)] - s[i]) * f


def avg(xs):
    s = [float(x) for x in xs if x is not None and math.isfinite(float(x))]
    return statistics.fmean(s) if s else None


def rsi14(cl, i):
    if i < 14:
        return None
    g = l = 0.0
    for j in range(i - 13, i + 1):
        d = cl[j] - cl[j - 1]
        g += max(d, 0.0)
        l += max(-d, 0.0)
    if l == 0:
        return 100.0
    rs = (g / 14) / (l / 14)
    return 100 - 100 / (1 + rs)


def sma(pref, i, n):
    if i < n - 1:
        return None
    return (pref[i + 1] - pref[i + 1 - n]) / n


def enrich(bars, rows):
    cl = [float(b[4]) for b in bars]
    pref = [0.0]
    for x in cl:
        pref.append(pref[-1] + x)
    out = []
    for r in rows:
        i = r['idx']
        if i < 252 or i + H >= len(bars):
            continue
        ma20 = sma(pref, i, 20)
        ma50 = sma(pref, i, 50)
        ma200 = sma(pref, i, 200)
        hi20 = max(float(b[2]) for b in bars[i-19:i+1])
        hi60 = max(float(b[2]) for b in bars[i-59:i+1])
        lo60 = min(float(b[3]) for b in bars[i-59:i+1])
        close = cl[i]
        o = outcomes(bars, r, H)
        out.append({
            **r,
            'close': close,
            'day_ret': 100 * (close / cl[i-1] - 1),
            'pre1': 100 * (cl[i-1] / cl[i-2] - 1),
            'pre3': 100 * (cl[i-1] / cl[i-4] - 1),
            'pre5': 100 * (cl[i-1] / cl[i-6] - 1),
            'pre10': 100 * (cl[i-1] / cl[i-11] - 1),
            'dd20': 100 * (close / hi20 - 1),
            'dd60': 100 * (close / hi60 - 1),
            'ma20_dist': 100 * (close / ma20 - 1),
            'ma50_dist': 100 * (close / ma50 - 1),
            'ma200_dist': 100 * (close / ma200 - 1),
            'rsi14': rsi14(cl, i),
            'range60_width': 100 * (hi60 / lo60 - 1) if lo60 else None,
            't5_ret': o['ret'],
            't5_up': o['ret'] > 0,
            't5_mfe': o['mfe'],
            't5_mae': o['mae'],
        })
    return out


def summary(rows):
    if not rows:
        return {'n': 0}
    return {
        'n': len(rows),
        't5_up_pct': 100 * sum(r['t5_up'] for r in rows) / len(rows),
        't5_mean': avg(r['t5_ret'] for r in rows),
        't5_median': q([r['t5_ret'] for r in rows], .5),
        't5_p25': q([r['t5_ret'] for r in rows], .25),
        't5_p75': q([r['t5_ret'] for r in rows], .75),
        'avg_mfe': avg(r['t5_mfe'] for r in rows),
        'avg_mae': avg(r['t5_mae'] for r in rows),
    }


def describe(rows, keys):
    out = {}
    for k in keys:
        xs = [r[k] for r in rows if r.get(k) is not None]
        out[k] = {
            'median': q(xs, .5), 'p25': q(xs, .25), 'p75': q(xs, .75),
            'mean': avg(xs),
        }
    return out


def split(rows, name, fn):
    groups = {}
    for r in rows:
        label = fn(r)
        groups.setdefault(label, []).append(r)
    return {'name': name, 'groups': {k: summary(v) for k, v in sorted(groups.items())}}


def quartile_split(rows, key, label):
    xs = [r[key] for r in rows if r.get(key) is not None]
    a, b, c = q(xs, .25), q(xs, .5), q(xs, .75)
    def bucket(r):
        x = r.get(key)
        if x is None: return 'NA'
        if x <= a: return f'Q1 <= {a:.2f}'
        if x <= b: return f'Q2 <= {b:.2f}'
        if x <= c: return f'Q3 <= {c:.2f}'
        return f'Q4 > {c:.2f}'
    return split(rows, label, bucket)


def main():
    data = json.loads(SRC.read_text())
    bars = data['instruments']['^GSPC']['bars']
    state_map = build_sp_state_map(bars)
    base_rows = [r for r in feature_rows(bars, state_map) if r['streak_bucket'] == 'D1']
    target_rows = [r for r in base_rows if (r['streak_bucket'], r['market_state'], r['position'], r['volatility']) == TARGET]
    base = enrich(bars, base_rows)
    target = enrich(bars, target_rows)

    keys = ['day_ret','pre1','pre3','pre5','pre10','dd20','dd60','ma20_dist','ma50_dist','ma200_dist','rsi14','atr_rank','pos60','range60_width']
    diagnostics = [
        split(target, 'current day loss size', lambda r: 'mild > -0.5%' if r['day_ret'] > -.5 else 'medium -1%..-0.5%' if r['day_ret'] > -1 else 'large <= -1%'),
        split(target, 'prior day sign', lambda r: 'prior up' if r['pre1'] > 0 else 'prior non-up'),
        split(target, 'below MA20?', lambda r: 'below MA20' if r['ma20_dist'] < 0 else 'above MA20'),
        split(target, 'below MA50?', lambda r: 'below MA50' if r['ma50_dist'] < 0 else 'above MA50'),
        split(target, 'RSI14 band', lambda r: '<40' if r['rsi14'] < 40 else '40-50' if r['rsi14'] < 50 else '50-60' if r['rsi14'] < 60 else '>=60'),
        split(target, '20D drawdown band', lambda r: '<=-10%' if r['dd20'] <= -10 else '-10..-5%' if r['dd20'] <= -5 else '-5..-2%' if r['dd20'] <= -2 else '>-2%'),
        quartile_split(target, 'pre5', 'prior 5D return quartiles'),
        quartile_split(target, 'dd20', '20D drawdown quartiles'),
        quartile_split(target, 'rsi14', 'RSI14 quartiles'),
        quartile_split(target, 'ma20_dist', 'MA20 distance quartiles'),
    ]

    episodes = sorted(target, key=lambda r: r['date'])
    result = {
        'schema': 'SP500-SURVIVOR-DIAGNOSTIC-V1',
        'target': {'streak':'D1','market_state':'bull','position':'low','volatility':'mid','horizon':5},
        'interpretation_guardrail': 'Diagnostic decomposition only. The strict OOS survivor has N=52 and is not yet a confirmed trading rule.',
        'full_history': {
            'baseline_D1': summary(base),
            'target_state': summary(target),
            'baseline_features': describe(base, keys),
            'target_features': describe(target, keys),
        },
        'diagnostic_splits': diagnostics,
        'episodes': [{k:r[k] for k in ['date','day_ret','pre1','pre3','pre5','pre10','dd20','dd60','ma20_dist','ma50_dist','ma200_dist','rsi14','atr_rank','pos60','t5_ret','t5_mfe','t5_mae']} for r in episodes],
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({
        'baseline_D1': result['full_history']['baseline_D1'],
        'target_state': result['full_history']['target_state'],
        'target_features': result['full_history']['target_features'],
        'splits': diagnostics,
        'episodes_n': len(episodes),
    }, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
