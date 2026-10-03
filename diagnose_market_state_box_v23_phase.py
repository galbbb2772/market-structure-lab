"""V2.3: test whether market phase explains regime-dependent environment-filter effects.

The key diagnostic from V2.2 is that the same Breadth 20-40 percentile bucket was
positive before 2022 and negative after 2022. This script tests whether that sign
flip is better understood after conditioning on a simple point-in-time S&P 500
200-day market phase.

Phase uses only current/past closes:
- bull_rising: close >= MA200 and MA200 20-session slope > 0
- bull_weakening: close >= MA200 and slope <= 0
- bear_falling: close < MA200 and slope < 0
- bear_recovery: close < MA200 and slope >= 0

Research diagnostic only; no phase or bucket is promoted to a trading rule here.
"""
from __future__ import annotations

import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "docs/data/market_state_box_v1.json"
OUT = ROOT / "docs/data/market_state_box_v23_phase.json"
H = (3, 5, 10)
PHASES = ("bull_rising", "bull_weakening", "bear_falling", "bear_recovery")


def num(x):
    try:
        z = float(x)
        return z if math.isfinite(z) else None
    except (TypeError, ValueError):
        return None


def q5(v):
    x = num(v)
    if x is None:
        return None
    return min(4, max(0, int(min(99.999, max(0.0, x)) // 20)))


def moving_average(vals, n):
    out = [None] * len(vals)
    s = 0.0
    valid = 0
    window = []
    for i, v in enumerate(vals):
        window.append(v)
        if v is not None:
            s += v
            valid += 1
        if len(window) > n:
            old = window.pop(0)
            if old is not None:
                s -= old
                valid -= 1
        if len(window) == n and valid == n:
            out[i] = s / n
    return out


def decluster(rows, gap=5):
    out, last = [], -10**9
    for r in sorted(rows, key=lambda x: int(x["_i"])):
        i = int(r["_i"])
        if i - last >= gap:
            out.append(r)
            last = i
    return out


def boot95(vals, seed=23, rounds=1000):
    vals = [float(x) for x in vals if num(x) is not None]
    if len(vals) < 5:
        return None
    rng = random.Random(seed + len(vals))
    n = len(vals)
    a = sorted(mean(vals[rng.randrange(n)] for _ in range(n)) for _ in range(rounds))
    return [round(a[int(.025*(rounds-1))],3), round(a[int(.975*(rounds-1))],3)]


def summary(rows):
    rows = decluster(rows)
    out = {"n": len(rows)}
    for h in H:
        a = [num(r.get(f"fwd_{h}d")) for r in rows]
        a = [x for x in a if x is not None]
        out[f"fwd_{h}d_mean"] = round(mean(a),3) if a else None
        out[f"fwd_{h}d_median"] = round(median(a),3) if a else None
        out[f"fwd_{h}d_positive_pct"] = round(100*sum(x>0 for x in a)/len(a),1) if a else None
        out[f"fwd_{h}d_mean_bootstrap95"] = boot95(a) if a else None
    mfe=[num(r.get('mfe_10d')) for r in rows]; mae=[num(r.get('mae_10d')) for r in rows]
    mfe=[x for x in mfe if x is not None]; mae=[x for x in mae if x is not None]
    out['mfe_10d_mean']=round(mean(mfe),3) if mfe else None
    out['mae_10d_mean']=round(mean(mae),3) if mae else None
    return out


def enrich(rows):
    closes = [num(r.get("sp500_close")) for r in rows]
    ma200 = moving_average(closes, 200)
    out=[]
    for i, src in enumerate(rows):
        r=dict(src); r['_i']=i
        r['breadth_q']=q5(r.get('breadth_20d_pct'))
        m=ma200[i]; c=closes[i]
        slope = (m - ma200[i-20]) / ma200[i-20] * 100 if i>=20 and m is not None and ma200[i-20] not in (None,0) else None
        r['ma200']=round(m,4) if m is not None else None
        r['ma200_slope20_pct']=round(slope,4) if slope is not None else None
        phase=None
        if c is not None and m is not None and slope is not None:
            if c >= m and slope > 0: phase='bull_rising'
            elif c >= m and slope <= 0: phase='bull_weakening'
            elif c < m and slope < 0: phase='bear_falling'
            else: phase='bear_recovery'
        r['market_phase_200']=phase
        out.append(r)
    return out


def period(events,start=None,end=None):
    return [r for r in events if (start is None or r['date']>=start) and (end is None or r['date']<=end)]


def phase_map(events):
    overall=summary(events)
    by_phase={}
    cells=[]
    for ph in PHASES:
        prs=[r for r in events if r.get('market_phase_200')==ph]
        by_phase[ph]=summary(prs)
        for q in range(5):
            rs=[r for r in prs if r.get('breadth_q')==q]
            s=summary(rs)
            s.update({'phase':ph,'breadth_q':q,'breadth_range':[q*20,(q+1)*20],'sample_ok':s['n']>=5})
            base5=by_phase[ph].get('fwd_5d_mean')
            s['fwd_5d_delta_vs_phase_box']=round(s['fwd_5d_mean']-base5,3) if s.get('fwd_5d_mean') is not None and base5 is not None else None
            cells.append(s)
    return {'overall_box':overall,'by_phase':by_phase,'phase_x_breadth':cells}


def q1_cross_period(payload):
    out=[]
    for pname,p in payload.items():
        for cell in p['phase_x_breadth']:
            if cell['breadth_q']==1:
                out.append({'period':pname, **cell})
    return out


def main():
    src=json.loads(SRC.read_text(encoding='utf-8'))
    rows=enrich(src.get('daily') or [])
    events=[r for r in rows if r.get('box_bottom') and r.get('fwd_10d') is not None and r.get('market_phase_200')]
    periods={
        'full':period(events),
        'pre_2022':period(events,end='2021-12-31'),
        'post_2022':period(events,start='2022-01-03'),
        'recent_2024_plus':period(events,start='2024-01-02'),
    }
    maps={k:phase_map(v) for k,v in periods.items()}
    out={
        'schema':'MARKET-STATE-BOX-V2.3-PHASE',
        'generated_at':datetime.now(timezone.utc).isoformat(),
        'diagnostic_only':True,
        'purpose':'Test whether a past-only SP500 MA200 phase explains V2.2 time-regime sign reversals, especially Breadth 20-40 percentile conditional on box-bottom events.',
        'phase_definition':'close vs trailing MA200 plus trailing MA200 20-session slope; no future data.',
        'selection_warning':'Phase conditioning follows observed V2.2 instability and is diagnostic, not fresh model selection.',
        'periods':maps,
        'breadth_q1_cross_period':q1_cross_period(maps),
    }
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(out['breadth_q1_cross_period'],ensure_ascii=False))

if __name__=='__main__':
    main()
