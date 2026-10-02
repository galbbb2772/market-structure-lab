from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

SRC = Path('docs/data/structure_lab.json')
OUT = Path('docs/data/concentration_latest.json')
SYMS = ['^GSPC', '^IXIC', '^DJI']
HORIZONS = [1, 3, 5, 10]
TOP_K = 40
STREAK_TOL = 1
DECLUSTER = 5
FEATURES = [
    ('streak', 2.0, 2.0), ('r1', 1.0, 2.0), ('r3', 1.0, 4.0),
    ('r5', 1.0, 6.0), ('rsi', 1.0, 15.0), ('atr_rank', .8, 25.0),
    ('vol_ratio', .4, .8), ('ma20_dist', 1.0, 5.0),
    ('pos60', .8, 25.0), ('market5', 1.0, 6.0),
]


def finite(v):
    return isinstance(v, (int, float)) and math.isfinite(v)


def mean(values):
    xs = [float(x) for x in values if finite(x)]
    return sum(xs) / len(xs) if xs else None


def quantile(values, q):
    xs = sorted(float(x) for x in values if finite(x))
    if not xs:
        return None
    p = (len(xs) - 1) * q
    i = int(math.floor(p))
    f = p - i
    j = min(i + 1, len(xs) - 1)
    return xs[i] + (xs[j] - xs[i]) * f


def r4(v):
    return round(v, 4) if finite(v) else None


def market5_map(data):
    bars = data['instruments']['^GSPC']['bars']
    out = {}
    for i in range(5, len(bars)):
        out[bars[i][0]] = 100.0 * (float(bars[i][4]) / float(bars[i - 5][4]) - 1.0)
    return out


def rolling_rows(bars, m5):
    n = len(bars)
    if n < 260:
        return []
    close = [float(b[4]) for b in bars]
    vol = [float(b[5] or 0) for b in bars]
    pref = [0.0]
    vpref = [0.0]
    for c, v in zip(close, vol):
        pref.append(pref[-1] + c)
        vpref.append(vpref[-1] + v)

    tr = [None] * n
    atr = [None] * n
    streak = [0] * n
    for i in range(1, n):
        hi, lo = float(bars[i][2]), float(bars[i][3])
        tr[i] = max(hi - lo, abs(hi - close[i - 1]), abs(lo - close[i - 1]))
        direction = 1 if close[i] > close[i - 1] else -1 if close[i] < close[i - 1] else 0
        if direction == 0:
            streak[i] = 0
        elif streak[i - 1] and (1 if streak[i - 1] > 0 else -1) == direction:
            streak[i] = streak[i - 1] + direction
        else:
            streak[i] = direction

    rsi = [None] * n
    gains = losses = 0.0
    for i in range(1, n):
        d = close[i] - close[i - 1]
        gains += max(d, 0.0)
        losses += max(-d, 0.0)
        if i > 14:
            old = close[i - 14] - close[i - 15]
            gains -= max(old, 0.0)
            losses -= max(-old, 0.0)
        if i >= 14:
            ag, al = gains / 14.0, losses / 14.0
            rsi[i] = 100.0 if al == 0 else 100.0 - 100.0 / (1.0 + ag / al)

    trsum = 0.0
    for i in range(1, n):
        trsum += tr[i] or 0.0
        if i > 14:
            trsum -= tr[i - 14] or 0.0
        if i >= 14:
            atr[i] = 100.0 * (trsum / 14.0) / close[i]

    rows = []
    for i in range(252, n):
        ma20 = (pref[i + 1] - pref[i - 19]) / 20.0
        ma200 = (pref[i + 1] - pref[i - 199]) / 200.0
        seg = bars[i - 59:i + 1]
        lo60 = min(float(b[3]) for b in seg)
        hi60 = max(float(b[2]) for b in seg)
        atr_hist = [x for x in atr[max(14, i - 251):i + 1] if finite(x)]
        ar = atr[i]
        atr_rank = 100.0 * sum(x <= ar for x in atr_hist) / len(atr_hist) if atr_hist and finite(ar) else None
        avg_vol = (vpref[i] - vpref[max(0, i - 20)]) / min(20, i)
        vol_ratio = vol[i] / avg_vol if avg_vol > 0 else None
        rows.append({
            'idx': i, 'date': bars[i][0], 'close': close[i], 'streak': streak[i],
            'r1': 100.0 * (close[i] / close[i - 1] - 1.0),
            'r3': 100.0 * (close[i] / close[i - 3] - 1.0),
            'r5': 100.0 * (close[i] / close[i - 5] - 1.0),
            'rsi': rsi[i], 'atr_rank': atr_rank, 'vol_ratio': vol_ratio,
            'ma20_dist': 100.0 * (close[i] / ma20 - 1.0),
            'pos60': 100.0 * (close[i] - lo60) / (hi60 - lo60) if hi60 > lo60 else 50.0,
            'market5': m5.get(bars[i][0]),
            'regime': 'above200' if close[i] >= ma200 else 'below200',
        })
    return rows


def distance(a, b):
    ss = ww = 0.0
    for key, wt, scale in FEATURES:
        av, bv = a.get(key), b.get(key)
        if not finite(av) or not finite(bv):
            continue
        d = (float(av) - float(bv)) / scale
        ss += wt * d * d
        ww += wt
    return math.sqrt(ss / ww) if ww else math.inf


def outcome(bars, row, h):
    i = row['idx']
    if i + h >= len(bars):
        return None
    base = float(bars[i][4])
    future = bars[i + 1:i + h + 1]
    return {
        'ret': 100.0 * (float(bars[i + h][4]) / base - 1.0),
        'mfe': 100.0 * (max(float(b[2]) for b in future) / base - 1.0),
        'mae': 100.0 * (min(float(b[3]) for b in future) / base - 1.0),
    }


def summarize(bars, rows, h):
    vals = [outcome(bars, r, h) for r in rows]
    vals = [x for x in vals if x]
    rets = [x['ret'] for x in vals]
    if not rets:
        return {'n': 0}
    return {
        'n': len(rets),
        'up_pct': r4(100.0 * sum(x > 0 for x in rets) / len(rets)),
        'mean_pct': r4(mean(rets)),
        'p10_pct': r4(quantile(rets, .10)),
        'p25_pct': r4(quantile(rets, .25)),
        'median_pct': r4(quantile(rets, .50)),
        'p75_pct': r4(quantile(rets, .75)),
        'p90_pct': r4(quantile(rets, .90)),
        'avg_mfe_pct': r4(mean(x['mfe'] for x in vals)),
        'avg_mae_pct': r4(mean(x['mae'] for x in vals)),
    }


def path_summary(bars, matches, max_h=10):
    paths = []
    for r in matches:
        i, base = r['idx'], float(bars[r['idx']][4])
        if i + max_h >= len(bars):
            continue
        paths.append([0.0] + [100.0 * (float(bars[i + h][4]) / base - 1.0) for h in range(1, max_h + 1)])
    out = []
    for h in range(max_h + 1):
        col = [p[h] for p in paths]
        out.append({'h': h, 'p10': r4(quantile(col, .10)), 'p25': r4(quantile(col, .25)),
                    'median': r4(quantile(col, .50)), 'p75': r4(quantile(col, .75)),
                    'p90': r4(quantile(col, .90))})
    return out


def run_symbol(data, sym, m5):
    inst = data['instruments'][sym]
    bars = inst['bars']
    rows = rolling_rows(bars, m5)
    target = rows[-1]
    candidates = [r for r in rows if r['idx'] + 10 < target['idx']]
    if target['streak']:
        candidates = [r for r in candidates if r['streak'] and (r['streak'] > 0) == (target['streak'] > 0)]
    candidates = [r for r in candidates if abs(abs(r['streak']) - abs(target['streak'])) <= STREAK_TOL]
    candidates = [r for r in candidates if r['regime'] == target['regime']]
    ranked = sorted(((distance(target, r), r) for r in candidates), key=lambda x: x[0])
    selected = []
    for d, r in ranked:
        if not finite(d):
            continue
        if any(abs(r['idx'] - x['idx']) < DECLUSTER for x in selected):
            continue
        rr = dict(r)
        rr['distance'] = d
        rr['similarity'] = 100.0 / (1.0 + d)
        selected.append(rr)
        if len(selected) >= TOP_K:
            break

    exact_streak = [r for r in rows if r['idx'] + 10 < target['idx'] and r['streak'] == target['streak']]
    summaries = {f'T+{h}': summarize(bars, selected, h) for h in HORIZONS}
    baseline = {f'T+{h}': summarize(bars, exact_streak, h) for h in HORIZONS}

    top = []
    for r in selected[:12]:
        item = {
            'date': r['date'], 'similarity_pct': r4(r['similarity']), 'distance': r4(r['distance']),
            'streak': r['streak'], 'r1_pct': r4(r['r1']), 'r3_pct': r4(r['r3']),
            'r5_pct': r4(r['r5']), 'rsi14': r4(r['rsi']), 'atr_rank_pct': r4(r['atr_rank']),
            'ma20_dist_pct': r4(r['ma20_dist']), 'pos60_pct': r4(r['pos60']),
        }
        for h in HORIZONS:
            o = outcome(bars, r, h)
            item[f't{h}_ret_pct'] = r4(o['ret']) if o else None
        top.append(item)

    current = {k: target.get(k) for k in ['date', 'close', 'streak', 'r1', 'r3', 'r5', 'rsi', 'atr_rank', 'vol_ratio', 'ma20_dist', 'pos60', 'market5', 'regime']}
    current = {k: r4(v) if finite(v) else v for k, v in current.items()}
    return {
        'symbol': sym, 'name': inst.get('name', sym), 'source_start': inst.get('start'), 'source_end': inst.get('end'),
        'settings': {'top_k': TOP_K, 'streak_tolerance': STREAK_TOL, 'same_direction': True,
                     'same_ma200_regime': True, 'decluster_sessions': DECLUSTER},
        'current_state': current,
        'candidate_pool_n': len(candidates), 'analog_n': len(selected), 'exact_streak_n': len(exact_streak),
        'analog': summaries, 'exact_streak_baseline': baseline,
        'path_quantiles': path_summary(bars, selected), 'top_matches': top,
    }


def main():
    data = json.loads(SRC.read_text(encoding='utf-8'))
    m5 = market5_map(data)
    results = [run_symbol(data, sym, m5) for sym in SYMS if sym in data.get('instruments', {})]
    payload = {
        'schema': 'HISTORICAL-PATTERN-CONCENTRATION-V1',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'method': 'Same as docs/concentration-lab.html V1 defaults; descriptive historical analogs, not a forecast.',
        'results': results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    for r in results:
        print(r['symbol'], r['current_state']['date'], r['current_state']['streak'], r['analog_n'])
        for h in HORIZONS:
            s = r['analog'][f'T+{h}']
            print(' ', f'T+{h}', 'up', s.get('up_pct'), 'median', s.get('median_pct'), 'P10/P90', s.get('p10_pct'), s.get('p90_pct'))
    print('Wrote', OUT)


if __name__ == '__main__':
    main()
