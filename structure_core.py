"""Point-in-time daily range-box, sector activity and distribution utilities.

Research definitions are provisional; the signal can use a box only from the
session *after* its detected_at date. Never use completed-box age as a feature.
"""
from __future__ import annotations

import math
import statistics
from typing import Any


def validate_bars(bars: list[list]) -> list[list]:
    """Sort and validate [YYYY-MM-DD, open, high, low, close, volume] bars."""
    clean = []
    for b in bars:
        if len(b) != 6 or any(x is None for x in b[1:5]):
            continue
        date, op, hi, lo, cl, vol = b
        try:
            op, hi, lo, cl = (float(x) for x in (op, hi, lo, cl))
            vol = float(vol or 0)
        except (ValueError, TypeError):
            continue
        if min(op, hi, lo, cl) <= 0 or hi < max(lo, op, cl) or lo > min(op, cl):
            continue
        clean.append([str(date)[:10], round(op, 4), round(hi, 4),
                      round(lo, 4), round(cl, 4), round(vol, 0)])
    unique = {b[0]: b for b in clean}
    return [unique[k] for k in sorted(unique)]


def box_scores(bars: list[list], start: int, end: int, lower: float, upper: float) -> dict[str, float]:
    """Use observations at/before end only; 10=hardest for difficulty."""
    segment = bars[start:end + 1]
    age = len(segment)
    width = max(upper - lower, 1e-9)
    center = (upper + lower) / 2
    formation = min(10.0, 10 * math.log1p(age) / math.log1p(120))
    stability = 10 * max(0.0, 1 - sum(abs(b[4] - center) / (width / 2)
                                          for b in segment) / age)
    median_range = statistics.median(b[2] - b[3] for b in segment)
    difficulty = 10 * min(1.0, median_range / max(width / 2, 1e-9))
    return {"formation": round(formation, 2), "stability": round(stability, 2),
            "difficulty": round(difficulty, 2),
            "composite": round((formation + stability + (10 - difficulty)) / 3, 2)}


def detect_boxes(bars: list[list], window: int, max_width_pct: float,
                 breakout_tolerance: float = .02, min_touches: int = 2) -> list[dict[str, Any]]:
    """Online anchored channel, finalized using closes only; no future reads.

    Candidate is detected AFTER today's close; next-session eligibility only.
    Earlier lookback bars are drawn for context, NOT backdated signals.
    """
    if not 0 < max_width_pct < 1 or window < 5:
        raise ValueError('invalid box parameters')
    boxes = []
    active = None
    last_break = -1
    for t, bar in enumerate(bars):
        close = bar[4]
        if active is not None:
            lower, upper = active['lower'], active['upper']
            if close < lower * (1 - breakout_tolerance) or close > upper * (1 + breakout_tolerance):
                end = t - 1
                active['end_at'] = bars[end][0]
                active['days'] = end - active['_start_i'] + 1
                active['scores'] = box_scores(bars, active['_start_i'], end, lower, upper)
                active['break_direction'] = 'down' if close < lower else 'up'
                active['break_at'] = bar[0]
                del active['_start_i']
                boxes.append(active)
                active = None
                last_break = t
            else:
                continue
        if t - last_break < window or t < window - 1:
            continue
        prev = bars[t - window + 1:t + 1]
        upper = max(b[2] for b in prev)
        lower = min(b[3] for b in prev)
        width_pct = (upper - lower) / max((upper + lower) / 2, 1e-9)
        if width_pct > max_width_pct or width_pct < .002:
            continue
        if abs(prev[-1][4] - prev[0][4]) > .55 * (upper - lower):
            continue
        width = upper - lower
        touches_upper = sum(b[2] >= upper - .12 * width for b in prev)
        touches_lower = sum(b[3] <= lower + .12 * width for b in prev)
        if min(touches_upper, touches_lower) < min_touches:
            continue
        start = t - window + 1
        scores = box_scores(bars, start, t, lower, upper)
        active = dict(start_at=bars[start][0], detected_at=bar[0], end_at=None,
                      lower=round(lower, 4), upper=round(upper, 4),
                      width_pct=round(width_pct * 100, 2), days=window,
                      scores=scores, break_direction=None, break_at=None,
                      _start_i=start)
    if active is not None:
        t = len(bars) - 1
        active['days'] = t - active['_start_i'] + 1
        active['scores'] = box_scores(bars, active['_start_i'], t,
                                      active['lower'], active['upper'])
        del active['_start_i']
        boxes.append(active)
    return boxes


def numbered_boxes(symbol: str, bars: list[list]) -> list[dict[str, Any]]:
    out = []
    for name, window, width in [('small', 20, .14), ('large', 60, .28)]:
        for i, box in enumerate(detect_boxes(bars, window, width), start=1):
            box['id'] = f'{symbol}-{name.upper()}-{i:04d}'
            box['scale'] = name
            box['window'] = window
            box['next_session_only'] = True
            out.append(box)
    return sorted(out, key=lambda b: (b['detected_at'], b['scale']))


def sector_activity(bars: list[list], lookback: int = 60) -> dict[str, float | str | None]:
    """Activity != media attention; rank current dollar volume vs prior 60 days."""
    if len(bars) <= lookback:
        return {'status': 'insufficient_history', 'activity': None}
    prior = bars[-lookback-1:-1]
    current = bars[-1]
    prior_turnover = [b[4] * b[5] for b in prior]
    turnover = current[4] * current[5]
    rank = 100 * sum(v <= turnover for v in prior_turnover) / len(prior_turnover)
    prior_ranges = [(b[2] - b[3]) / b[4] for b in prior]
    current_range = (current[2] - current[3]) / current[4]
    range_rank = 100 * sum(v <= current_range for v in prior_ranges) / len(prior_ranges)
    return {'status': 'ok', 'date': current[0],
            'turnover_rank': round(rank, 1), 'range_rank': round(range_rank, 1),
            'activity': round((rank + range_rank) / 2, 1),
            'day_return_pct': round(100 * (current[4] / bars[-2][4] - 1), 2),
            'news_attention': None, 'label': 'ETF成交额和振幅代理；非真实题材关注度'}


def sector_activity_history(bars: list[list], lookback: int = 60) -> list[list]:
    """Publication-safe daily ETF activity history: [date, score, day_pct]."""
    series=[]
    if len(bars)<=lookback:
        return series
    turnovers=[b[4]*b[5] for b in bars]
    ranges=[(b[2]-b[3])/b[4] for b in bars]
    for i in range(lookback,len(bars)):
        left=i-lookback
        rank=100*sum(v<=turnovers[i] for v in turnovers[left:i])/lookback
        rrank=100*sum(v<=ranges[i] for v in ranges[left:i])/lookback
        day_return=100*(bars[i][4]/bars[i-1][4]-1)
        series.append([bars[i][0], round((rank+rrank)/2,1), round(day_return,2)])
    return series


def news_tension(news_history: dict, benchmarks: dict[str, list[list]]) -> list[dict]:
    """Experimental equal-weight 0-100 reaction-adjusted news risk proxy.

    Never reconstruct an earlier publication date from today's headlines.
    """
    returns = {}
    for label, bars in benchmarks.items():
        returns[label] = {b[0]: round(100 * (b[4] / bars[i-1][4] - 1), 3)
                          for i,b in enumerate(bars) if i>0}
    keys = ('us_policy_event_sentiment', 'geopolitical_news_risk',
            'systemic_news_risk', 'ai_narrative_risk', 'negative_narrative_density')
    out = {}
    for day in news_history.get('history', []):
        actual = day.get('reaction_adjusted') or {}
        vals = [actual.get(k) for k in keys]
        if not all(isinstance(v, (int, float)) and 0 <= v <= 100 for v in vals):
            continue
        date = day.get('date')
        if not date:
            continue
        out[date] = dict(date=date, tension=round(sum(vals)/len(vals), 2),
                         index_returns={k: ret.get(date) for k,ret in returns.items()},
                         components=len(vals))
    return [out[d] for d in sorted(out)]


def updown_stats(bars: list[list]) -> dict:
    """Descriptive close-to-close daily distribution; no normality assumption."""
    changes = [100 * (bars[i][4] / bars[i - 1][4] - 1)
               for i in range(1, len(bars))]
    up = [x for x in changes if x > 0]
    down = [x for x in changes if x < 0]
    return {'n': len(changes), 'up_n': len(up), 'down_n': len(down),
            'up_median_pct': round(statistics.median(up), 4) if up else None,
            'down_median_pct': round(statistics.median(down), 4) if down else None,
            'up_frequency_pct': round(100 * len(up) / len(changes), 3) if changes else None,
            'mean_pct': round(statistics.mean(changes), 4) if changes else None,
            'std_pct': round(statistics.stdev(changes), 4) if len(changes) > 1 else None}


def nonoverlap_forward_rates(bars: list[list], cutoff_date: str, horizon: int,
                             regime: str | None = None) -> dict:
    """Illustrative non-overlapping historical forward frequency, never a forecast.

    Regime uses *prior* 200 closes. No outcome at/after selected cutoff is used.
    """
    if horizon not in (1, 5, 20):
        raise ValueError('horizon must be 1, 5, or 20')
    wins = total = 0
    t = 200
    while t + horizon < len(bars) and bars[t + horizon][0] <= cutoff_date:
        prev_mean = sum(b[4] for b in bars[t-200:t]) / 200
        state = 'above200' if bars[t-1][4] >= prev_mean else 'below200'
        if regime is None or state == regime:
            total += 1
            wins += bars[t + horizon][4] > bars[t][4]
            t += horizon
        else:
            t += 1
    p = wins / total if total else None
    if total:
        z = 1.96
        center = (p + z*z/(2*total)) / (1+z*z/total)
        half = z * math.sqrt(p*(1-p)/total + z*z/(4*total*total)) / (1+z*z/total)
        interval = [round(max(0, center-half)*100, 1), round(min(1, center+half)*100, 1)]
    else:
        interval = None
    return {'horizon_sessions': horizon, 'regime': regime or 'all', 'n': total,
            'positive_pct': round(p*100, 1) if p is not None else None,
            'naive_wilson_95_pct': interval, 'usable': total >= 60,
            'caveat': '独立性未获保证；不是样本外预测或收益承诺'}
