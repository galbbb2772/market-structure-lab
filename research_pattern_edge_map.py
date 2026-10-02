from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

SRC = Path('docs/data/structure_lab.json')
OUT = Path('docs/data/pattern_edge_map.json')
SYMS = ['^GSPC', '^IXIC', '^DJI']
HORIZONS = (1, 3, 5, 10)
MIN_CELL_N = 40
MIN_OOS_N = 30


def q(values, p):
    s = sorted(float(x) for x in values if x is not None and math.isfinite(float(x)))
    if not s:
        return None
    z = (len(s) - 1) * p
    i = int(z)
    f = z - i
    return s[i] + (s[min(i + 1, len(s) - 1)] - s[i]) * f


def avg(values):
    s = [float(x) for x in values if x is not None and math.isfinite(float(x))]
    return statistics.fmean(s) if s else None


def sign_bucket(streak: int) -> str:
    if streak == 0:
        return 'FLAT'
    side = 'U' if streak > 0 else 'D'
    n = abs(streak)
    return f'{side}{n}' if n <= 5 else f'{side}6+'


def pos_bucket(v: float) -> str:
    if v < 33.333333:
        return 'low'
    if v < 66.666667:
        return 'mid'
    return 'high'


def vol_bucket(v: float) -> str:
    if v < 33.333333:
        return 'low'
    if v < 66.666667:
        return 'mid'
    return 'high'


def market_state(sp_close: float, sp_ma200: float, sp_ma200_20ago: float) -> str:
    slope = sp_ma200 / sp_ma200_20ago - 1 if sp_ma200_20ago else 0.0
    if sp_close >= sp_ma200 and slope > 0:
        return 'bull'
    if sp_close < sp_ma200 and slope < 0:
        return 'weak'
    return 'sideways'


def feature_rows(bars, sp_state_map):
    n = len(bars)
    cl = [float(b[4]) for b in bars]
    pref = [0.0]
    for x in cl:
        pref.append(pref[-1] + x)
    streak = [0] * n
    tr = [None] * n
    atr = [None] * n
    for i in range(1, n):
        d = 1 if cl[i] > cl[i - 1] else -1 if cl[i] < cl[i - 1] else 0
        streak[i] = 0 if d == 0 else (streak[i - 1] + d if streak[i - 1] and (1 if streak[i - 1] > 0 else -1) == d else d)
        tr[i] = max(
            float(bars[i][2]) - float(bars[i][3]),
            abs(float(bars[i][2]) - cl[i - 1]),
            abs(float(bars[i][3]) - cl[i - 1]),
        )
    tsum = 0.0
    for i in range(1, n):
        tsum += tr[i] or 0.0
        if i > 14:
            tsum -= tr[i - 14] or 0.0
        if i >= 14:
            atr[i] = 100 * (tsum / 14) / cl[i]

    out = []
    for i in range(252, n - max(HORIZONS)):
        ah = [x for x in atr[max(14, i - 251):i + 1] if x is not None]
        ar = atr[i]
        atr_rank = 100 * sum(x <= ar for x in ah) / len(ah) if ah else None
        seg = bars[i - 59:i + 1]
        lo = min(float(b[3]) for b in seg)
        hi = max(float(b[2]) for b in seg)
        p60 = 100 * (cl[i] - lo) / (hi - lo) if hi > lo else 50.0
        state = sp_state_map.get(bars[i][0])
        if state is None or atr_rank is None:
            continue
        out.append({
            'idx': i,
            'date': bars[i][0],
            'year': int(bars[i][0][:4]),
            'streak': streak[i],
            'streak_bucket': sign_bucket(streak[i]),
            'market_state': state,
            'position': pos_bucket(p60),
            'volatility': vol_bucket(atr_rank),
            'atr_rank': atr_rank,
            'pos60': p60,
        })
    return out


def outcomes(bars, row, h):
    i = row['idx']
    base = float(bars[i][4])
    fut = bars[i + 1:i + h + 1]
    return {
        'ret': 100 * (float(bars[i + h][4]) / base - 1),
        'mfe': 100 * (max(float(b[2]) for b in fut) / base - 1),
        'mae': 100 * (min(float(b[3]) for b in fut) / base - 1),
    }


def summarize(bars, rows, h):
    o = [outcomes(bars, r, h) for r in rows]
    rets = [x['ret'] for x in o]
    if not rets:
        return {'n': 0}
    return {
        'n': len(rets),
        'up_pct': 100 * sum(x > 0 for x in rets) / len(rets),
        'mean': avg(rets),
        'median': q(rets, .5),
        'p25': q(rets, .25),
        'p75': q(rets, .75),
        'avg_mfe': avg(x['mfe'] for x in o),
        'avg_mae': avg(x['mae'] for x in o),
    }


def delta(cell, base):
    if cell.get('n', 0) < MIN_CELL_N or base.get('n', 0) < MIN_CELL_N:
        return {'usable': False}
    return {
        'usable': True,
        'up_edge_pp': cell['up_pct'] - base['up_pct'],
        'median_edge_pct': cell['median'] - base['median'],
        'mean_edge_pct': cell['mean'] - base['mean'],
        'mfe_edge_pct': cell['avg_mfe'] - base['avg_mfe'],
        'mae_edge_pct': cell['avg_mae'] - base['avg_mae'],
    }


def build_sp_state_map(sp_bars):
    cl = [float(b[4]) for b in sp_bars]
    pref = [0.0]
    for x in cl:
        pref.append(pref[-1] + x)
    ma200 = [None] * len(sp_bars)
    for i in range(199, len(sp_bars)):
        ma200[i] = (pref[i + 1] - pref[i - 199]) / 200
    out = {}
    for i in range(219, len(sp_bars)):
        out[sp_bars[i][0]] = market_state(cl[i], ma200[i], ma200[i - 20])
    return out


def oos_cell_test(bars, rows, h):
    # Expanding-window, year-by-year pseudo-OOS test. For each test year, the
    # conditioned cell and streak baseline are estimated only from prior years.
    by_year = defaultdict(list)
    for r in rows:
        by_year[r['year']].append(r)
    years = sorted(by_year)
    pred_records = []
    for y in years:
        train = [r for yy in years if yy < y for r in by_year[yy]]
        test = by_year[y]
        if not train:
            continue
        base_groups = defaultdict(list)
        cell_groups = defaultdict(list)
        for r in train:
            if r['streak_bucket'] == 'FLAT':
                continue
            base_groups[r['streak_bucket']].append(r)
            cell_groups[(r['streak_bucket'], r['market_state'], r['position'], r['volatility'])].append(r)
        for r in test:
            sb = r['streak_bucket']
            if sb == 'FLAT':
                continue
            key = (sb, r['market_state'], r['position'], r['volatility'])
            br = base_groups.get(sb, [])
            cr = cell_groups.get(key, [])
            if len(br) < MIN_CELL_N or len(cr) < MIN_CELL_N:
                continue
            bs = summarize(bars, br, h)
            cs = summarize(bars, cr, h)
            actual = outcomes(bars, r, h)['ret']
            pred_records.append({
                'actual_up': actual > 0,
                'actual_ret': actual,
                'base_up_pct': bs['up_pct'],
                'cell_up_pct': cs['up_pct'],
                'base_median': bs['median'],
                'cell_median': cs['median'],
            })
    if len(pred_records) < MIN_OOS_N:
        return {'n': len(pred_records), 'usable': False}
    def brier(p, y):
        return (p / 100 - (1.0 if y else 0.0)) ** 2
    base_brier = avg(brier(r['base_up_pct'], r['actual_up']) for r in pred_records)
    cell_brier = avg(brier(r['cell_up_pct'], r['actual_up']) for r in pred_records)
    base_abs = avg(abs(r['actual_ret'] - r['base_median']) for r in pred_records)
    cell_abs = avg(abs(r['actual_ret'] - r['cell_median']) for r in pred_records)
    return {
        'n': len(pred_records),
        'usable': True,
        'base_brier': base_brier,
        'cell_brier': cell_brier,
        'brier_improvement': base_brier - cell_brier,
        'base_median_mae': base_abs,
        'cell_median_mae': cell_abs,
        'median_mae_improvement': base_abs - cell_abs,
    }


def main():
    data = json.loads(SRC.read_text())
    sp_bars = data['instruments']['^GSPC']['bars']
    sp_state_map = build_sp_state_map(sp_bars)
    result = {
        'schema': 'PATTERN-EDGE-MAP-V1',
        'definitions': {
            'streak_buckets': ['U1','U2','U3','U4','U5','U6+','D1','D2','D3','D4','D5','D6+'],
            'market_state': {
                'bull': 'S&P 500 close >= MA200 and MA200 20-session slope > 0',
                'weak': 'S&P 500 close < MA200 and MA200 20-session slope < 0',
                'sideways': 'all other combinations',
            },
            'position': {'low': '<33.3% of 60D high-low range', 'mid': '33.3%-66.7%', 'high': '>=66.7%'},
            'volatility': {'low': '<33.3 ATR14 percentile', 'mid': '33.3-66.7', 'high': '>=66.7'},
            'baseline': 'same signed streak bucket across all market states/positions/volatility',
            'minimum_cell_n': MIN_CELL_N,
        },
        'instruments': {},
    }
    for sym in SYMS:
        inst = data['instruments'][sym]
        bars = inst['bars']
        rr = feature_rows(bars, sp_state_map)
        rr = [r for r in rr if r['streak_bucket'] != 'FLAT']
        base_groups = defaultdict(list)
        cell_groups = defaultdict(list)
        for r in rr:
            base_groups[r['streak_bucket']].append(r)
            cell_groups[(r['streak_bucket'], r['market_state'], r['position'], r['volatility'])].append(r)
        baselines = {}
        cells = []
        for sb, group in sorted(base_groups.items()):
            baselines[sb] = {str(h): summarize(bars, group, h) for h in HORIZONS}
        for key, group in cell_groups.items():
            sb, ms, pos, vol = key
            entry = {
                'streak': sb,
                'market_state': ms,
                'position': pos,
                'volatility': vol,
                'n': len(group),
                'horizons': {},
            }
            for h in HORIZONS:
                cs = summarize(bars, group, h)
                bs = baselines[sb][str(h)]
                entry['horizons'][str(h)] = {
                    'cell': cs,
                    'baseline': bs,
                    'edge': delta(cs, bs),
                }
            cells.append(entry)
        # Rank descriptively by T+5 combined directional + median edge, but only
        # expose a score as a research sorting field, not as a trading recommendation.
        for e in cells:
            x = e['horizons']['5']['edge']
            e['research_sort_score'] = None if not x.get('usable') else abs(x['up_edge_pp']) + 10 * abs(x['median_edge_pct'])
        cells.sort(key=lambda e: (-1 if e['research_sort_score'] is None else -e['research_sort_score'], e['streak'], e['market_state'], e['position'], e['volatility']))
        result['instruments'][sym] = {
            'name': inst['name'],
            'coverage': [rr[0]['date'], rr[-1]['date']] if rr else None,
            'rows': len(rr),
            'baselines': baselines,
            'cells': cells,
            'oos': {str(h): oos_cell_test(bars, rr, h) for h in HORIZONS},
        }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({s: result['instruments'][s]['oos'] for s in SYMS}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
