#!/usr/bin/env python3
import json
from pathlib import Path
from statistics import mean, median

STATE = Path('docs/data/market_state_box_v1.json')
EVENTS = Path('docs/data/market_state_sequence_event_audit_v1.json')
OUT = Path('docs/data/residual_mean_reversion_distance_v1.json')
FAIL_DATE = '2022-06-07'


def num(x):
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def avg_ranks(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    p = 0
    while p < len(order):
        q = p + 1
        while q < len(order) and values[order[q]] == values[order[p]]:
            q += 1
        r = (p + 1 + q) / 2.0
        for k in range(p, q):
            ranks[order[k]] = r
        p = q
    return ranks


def pearson(x, y):
    if len(x) < 3:
        return None
    mx, my = mean(x), mean(y)
    sx = sum((a - mx) ** 2 for a in x)
    sy = sum((b - my) ** 2 for b in y)
    if sx <= 0 or sy <= 0:
        return None
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy) ** 0.5


def spearman_pairs(rows, xkey, ykey):
    pairs = []
    for r in rows:
        x, y = num(r.get(xkey)), num(r.get(ykey))
        if x is not None and y is not None:
            pairs.append((x, y))
    if len(pairs) < 3:
        return {'n': len(pairs), 'rho': None}
    x = [p[0] for p in pairs]
    y = [p[1] for p in pairs]
    rho = pearson(avg_ranks(x), avg_ranks(y))
    return {'n': len(pairs), 'rho': None if rho is None else round(rho, 4)}


def loo_spearman(rows, xkey, ykey):
    vals = []
    for i in range(len(rows)):
        z = spearman_pairs(rows[:i] + rows[i + 1:], xkey, ykey)
        if z.get('rho') is not None:
            vals.append(z['rho'])
    if not vals:
        return {'n_loo': 0, 'min_rho': None, 'median_rho': None, 'max_rho': None}
    return {
        'n_loo': len(vals),
        'min_rho': round(min(vals), 4),
        'median_rho': round(median(vals), 4),
        'max_rho': round(max(vals), 4),
    }


def outcome_summary(rows):
    out = {'n': len(rows)}
    for h in (1, 3, 5, 10):
        vals = [num(r.get(f'fwd_{h}d')) for r in rows]
        vals = [v for v in vals if v is not None]
        out[f'{h}d'] = {
            'n': len(vals),
            'mean_pct': None if not vals else round(mean(vals), 4),
            'median_pct': None if not vals else round(median(vals), 4),
            'positive_pct': None if not vals else round(100.0 * sum(v > 0 for v in vals) / len(vals), 2),
        }
    return out


def group_flag(rows, flag):
    yes = [r for r in rows if bool(r.get(flag))]
    no = [r for r in rows if not bool(r.get(flag))]
    def score(g, key):
        a = [num(r.get(key)) for r in g]
        a = [x for x in a if x is not None]
        return None if not a else round(mean(a), 4)
    return {
        'yes_n': len(yes), 'no_n': len(no),
        'rmd3_yes_mean': score(yes, 'rmd3'), 'rmd3_no_mean': score(no, 'rmd3'),
        'rmd4_yes_mean': score(yes, 'rmd4'), 'rmd4_no_mean': score(no, 'rmd4'),
    }


def main():
    state = json.loads(STATE.read_text(encoding='utf-8'))
    audit = json.loads(EVENTS.read_text(encoding='utf-8'))
    events = [dict(x) for x in audit.get('events', [])]
    if audit.get('event_definition') != 'D_TO_BOTH_REBOUND_SCORE' or len(events) != 12:
        raise RuntimeError('Frozen 12-event identity drifted')

    daily = [dict(r) for r in state.get('daily', [])]
    if len(daily) < 2000:
        raise RuntimeError('Market State Box V1 daily history missing/too short')
    by_date = {r.get('date'): r for r in daily}

    ret20_hist = []
    ret20_pct_by_date = {}
    for i, r in enumerate(daily):
        c = num(r.get('sp500_close'))
        c0 = num(daily[i - 20].get('sp500_close')) if i >= 20 else None
        ret20 = None if c is None or c0 in (None, 0) else (c / c0 - 1.0) * 100.0
        r['_ret20_calc'] = ret20
        if ret20 is not None:
            ret20_hist.append(ret20)
            if len(ret20_hist) >= 252:
                pct = sum(v <= ret20 for v in ret20_hist) / len(ret20_hist)
                ret20_pct_by_date[r.get('date')] = pct

    enriched = []
    for e in events:
        d = by_date.get(e.get('date'))
        if not d:
            raise RuntimeError(f"Missing market-state row for event {e.get('date')}")
        price_pct = ret20_pct_by_date.get(e.get('date'))
        breadth_pct = num(d.get('breadth_20d_pct'))
        score_pct = num(d.get('market_score_pct'))
        box_pos = num(d.get('box_position'))
        if price_pct is None or breadth_pct is None or score_pct is None:
            raise RuntimeError(f"Missing primary RMD component for {e.get('date')}: price={price_pct}, breadth={breadth_pct}, score={score_pct}")

        price_residual = 1.0 - clamp(price_pct)
        breadth_residual = 1.0 - clamp(breadth_pct / 100.0)
        score_residual = 1.0 - clamp(score_pct / 100.0)
        box_residual = None if box_pos is None else 1.0 - clamp(box_pos)
        rmd3 = mean([price_residual, breadth_residual, score_residual])
        rmd4 = None if box_residual is None else mean([price_residual, breadth_residual, score_residual, box_residual])

        x = dict(e)
        x.update({
            'ret20_expanding_percentile': round(price_pct * 100.0, 4),
            'market_score_pct': round(score_pct, 4),
            'price_residual': round(price_residual, 6),
            'breadth_residual': round(breadth_residual, 6),
            'score_residual': round(score_residual, 6),
            'box_residual': None if box_residual is None else round(box_residual, 6),
            'rmd3': round(rmd3, 6),
            'rmd4': None if rmd4 is None else round(rmd4, 6),
            'second_drop_5d': num(e.get('fwd_5d')) is not None and num(e.get('fwd_5d')) < 0,
            'second_drop_10d': num(e.get('fwd_10d')) is not None and num(e.get('fwd_10d')) < 0,
            'severe_adverse_10d': num(e.get('mae_10d')) is not None and num(e.get('mae_10d')) <= -5.0,
        })
        enriched.append(x)

    correlations = {}
    for score in ('rmd3', 'rmd4'):
        correlations[score] = {}
        for h in (3, 5, 10):
            key = f'fwd_{h}d'
            base = spearman_pairs(enriched, score, key)
            base['leave_one_out'] = loo_spearman(enriched, score, key)
            no_fail = [r for r in enriched if r.get('date') != FAIL_DATE]
            base['without_2022_06_07'] = spearman_pairs(no_fail, score, key)
            correlations[score][key] = base

    component_correlations = {}
    for comp in ('price_residual', 'breadth_residual', 'score_residual', 'box_residual'):
        component_correlations[comp] = {}
        for h in (5, 10):
            key = f'fwd_{h}d'
            z = spearman_pairs(enriched, comp, key)
            z['leave_one_out'] = loo_spearman(enriched, comp, key)
            component_correlations[comp][key] = z

    rank_halves = {}
    for score in ('rmd3', 'rmd4'):
        usable = [r for r in enriched if num(r.get(score)) is not None]
        usable = sorted(usable, key=lambda r: num(r.get(score)))
        cut = len(usable) // 2
        rank_halves[score] = {
            'lower_residual_half': outcome_summary(usable[:cut]),
            'upper_residual_half': outcome_summary(usable[cut:]),
            'lower_dates': [r['date'] for r in usable[:cut]],
            'upper_dates': [r['date'] for r in usable[cut:]],
        }

    ranked = sorted(enriched, key=lambda r: num(r.get('rmd3')), reverse=True)
    for i, r in enumerate(ranked, 1):
        r['rmd3_rank_high_to_low'] = i

    out = {
        'schema': 'RESIDUAL-MEAN-REVERSION-DISTANCE-V1',
        'research_only': True,
        'diagnostic_only': True,
        'production_effect': 'none',
        'thresholds_or_weights_optimized': False,
        'event_definition': audit.get('event_definition'),
        'event_count': len(enriched),
        'primary_score': 'RMD3 = equal-weight mean(price_residual, breadth_residual, score_residual)',
        'secondary_score': 'RMD4 = equal-weight RMD3 components plus current box_residual where current box exists',
        'hypothesized_direction': 'higher RMD -> higher subsequent mean-reversion return',
        'correlations': correlations,
        'component_correlations': component_correlations,
        'rank_halves': rank_halves,
        'risk_flag_score_means': {
            'second_drop_5d': group_flag(enriched, 'second_drop_5d'),
            'second_drop_10d': group_flag(enriched, 'second_drop_10d'),
            'severe_adverse_10d': group_flag(enriched, 'severe_adverse_10d'),
        },
        'events_ranked_by_rmd3': ranked,
        'decision': {
            'status': 'mechanism_diagnostic_only',
            'may_change_production': False,
            'may_change_existing_forward_oos_shadow': False,
            'note': 'Any use of RMD as a trading score requires a separately preregistered independent Forward-OOS test.'
        },
        'warnings': [
            'The 12 historical sequence events were known before this diagnostic; this is not fresh OOS evidence.',
            'RMD4 has fewer observations because current eligible box position is intentionally not backfilled.',
            'No component weight, threshold, nonlinear transform, or parameter grid is optimized in V1.'
        ]
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Wrote', OUT)
    print(json.dumps({'event_count': len(enriched), 'correlations': correlations, 'risk_flags': out['risk_flag_score_means']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
