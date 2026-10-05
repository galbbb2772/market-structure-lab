from __future__ import annotations

import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'docs/data/task14_challenger_forward_oos_v1.json'
OUT = ROOT / 'docs/data/task14_paper_execution_ledger_v1.json'
FROZEN_THROUGH = '2026-10-02'
BASE_COST_BPS = 10
HORIZONS = (5, 10, 20)


def num(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def fetch_spy():
    headers = {'User-Agent': 'Mozilla/5.0 Market-Structure-Lab/Paper-Execution-V1'}
    errors = []
    for host in ('query1.finance.yahoo.com', 'query2.finance.yahoo.com'):
        url = f'https://{host}/v8/finance/chart/SPY?range=10y&interval=1d&events=history&includeAdjustedClose=true'
        for attempt in range(2):
            try:
                r = requests.get(url, headers=headers, timeout=20)
                r.raise_for_status()
                obj = r.json()['chart']['result'][0]
                ts = obj.get('timestamp') or []
                q = ((obj.get('indicators') or {}).get('quote') or [{}])[0]
                rows = []
                for t, o, c, v in zip(ts, q.get('open') or [], q.get('close') or [], q.get('volume') or []):
                    o, c, v = num(o), num(c), num(v)
                    if o is None or c is None:
                        continue
                    rows.append({
                        'date': datetime.fromtimestamp(int(t), tz=timezone.utc).strftime('%Y-%m-%d'),
                        'open': o, 'close': c, 'volume': v,
                    })
                if len(rows) < 1000:
                    raise RuntimeError(f'short SPY history: {len(rows)}')
                return rows, {'host': host, 'rows': len(rows), 'transport': 'yahoo_chart_range_10y'}
            except Exception as exc:
                errors.append(f'{host}:{type(exc).__name__}:{exc}')
                time.sleep(1 + attempt)
    raise RuntimeError(' | '.join(errors))


def pct(a, b):
    if a in (None, 0) or b is None:
        return None
    return 100.0 * (b / a - 1.0)


def load_existing():
    if not OUT.exists():
        return None
    d = json.loads(OUT.read_text(encoding='utf-8'))
    if d.get('schema') != 'TASK14-PAPER-EXECUTION-LEDGER-V1':
        raise RuntimeError('paper ledger schema mismatch')
    if d.get('frozen_through_market_date') != FROZEN_THROUGH:
        raise RuntimeError('paper ledger freeze boundary mismatch')
    return d


def main():
    src = json.loads(SOURCE.read_text(encoding='utf-8'))
    if src.get('schema') != 'TASK14-CHALLENGER-FORWARD-OOS-V1':
        raise RuntimeError('unexpected challenger ledger schema')
    if src.get('frozen_through_market_date') != FROZEN_THROUGH:
        raise RuntimeError('upstream freeze boundary mismatch')

    # Full Sequence future event stream: RMD2 is only used as the immutable event carrier.
    upstream = ((src.get('challengers') or {}).get('rmd2_price_score') or {}).get('events') or []
    upstream = [e for e in upstream if e.get('event_date') and e['event_date'] > FROZEN_THROUGH]

    spy, source = fetch_spy()
    idx = {r['date']: i for i, r in enumerate(spy)}
    existing = load_existing()
    old = {e['event_date']: e for e in (existing or {}).get('events', [])}
    discrepancies = []
    now = datetime.now(timezone.utc).isoformat()

    for u in upstream:
        d = u['event_date']
        if d not in old:
            old[d] = {
                'event_date': d,
                'signal_family': 'full_sequence',
                'upstream_carrier': 'rmd2_price_score',
                'upstream_first_seen_at': u.get('first_seen_at'),
                'paper_first_seen_at': now,
                'instrument': 'SPY',
                'execution_policy': 'next_regular_session_open',
                'base_round_trip_cost_bps': BASE_COST_BPS,
                'signal_close': None,
                'entry_date': None,
                'entry_open': None,
                'adv20_usd_at_signal': None,
                'outcomes': {str(h): {'mature': False, 'exit_date': None, 'exit_close': None, 'gross_return_pct': None, 'net_return_pct': None} for h in HORIZONS},
            }
        rec = old[d]
        if rec.get('signal_family') != 'full_sequence' or rec.get('instrument') != 'SPY':
            discrepancies.append({'event_date': d, 'field': 'identity', 'stored': {'signal_family': rec.get('signal_family'), 'instrument': rec.get('instrument')}})
            continue
        i = idx.get(d)
        if i is None:
            continue
        signal_close = round(spy[i]['close'], 6)
        if rec.get('signal_close') is None:
            rec['signal_close'] = signal_close
        elif abs(float(rec['signal_close']) - signal_close) > 1e-8:
            discrepancies.append({'event_date': d, 'field': 'signal_close', 'stored': rec['signal_close'], 'recompute': signal_close})

        dv = [r['close'] * r['volume'] for r in spy[max(0, i - 19):i + 1] if r.get('volume') is not None]
        adv20 = None if not dv else round(sum(dv) / len(dv), 2)
        if rec.get('adv20_usd_at_signal') is None and adv20 is not None:
            rec['adv20_usd_at_signal'] = adv20

        if i + 1 < len(spy):
            entry = spy[i + 1]
            entry_date = entry['date']
            entry_open = round(entry['open'], 6)
            if rec.get('entry_date') is None:
                rec['entry_date'] = entry_date
                rec['entry_open'] = entry_open
            elif rec.get('entry_date') != entry_date or abs(float(rec['entry_open']) - entry_open) > 1e-8:
                discrepancies.append({'event_date': d, 'field': 'entry', 'stored': {'date': rec.get('entry_date'), 'open': rec.get('entry_open')}, 'recompute': {'date': entry_date, 'open': entry_open}})

        if rec.get('entry_open') is not None:
            for h in HORIZONS:
                out = rec['outcomes'][str(h)]
                if i + h < len(spy):
                    ex = spy[i + h]
                    gross = pct(float(rec['entry_open']), ex['close'])
                    net = gross - BASE_COST_BPS / 100.0
                    if not out.get('mature'):
                        out.update({
                            'mature': True,
                            'exit_date': ex['date'],
                            'exit_close': round(ex['close'], 6),
                            'gross_return_pct': round(gross, 6),
                            'net_return_pct': round(net, 6),
                        })
                    else:
                        recompute = {'exit_date': ex['date'], 'exit_close': round(ex['close'], 6), 'gross_return_pct': round(gross, 6), 'net_return_pct': round(net, 6)}
                        for k, v in recompute.items():
                            if out.get(k) != v:
                                discrepancies.append({'event_date': d, 'horizon': h, 'field': k, 'stored': out.get(k), 'recompute': v})

    events = [old[k] for k in sorted(old)]
    out = {
        'schema': 'TASK14-PAPER-EXECUTION-LEDGER-V1',
        'generated_at': now,
        'research_only': True,
        'diagnostic_only': True,
        'paper_only': True,
        'production_effect': 'none',
        'broker_orders_enabled': False,
        'frozen_through_market_date': FROZEN_THROUGH,
        'study_spec': 'research/task14_stage4_execution_v1/STUDY_SPEC.md',
        'instrument': 'SPY',
        'execution_policy': 'next_regular_session_open',
        'base_round_trip_cost_bps': BASE_COST_BPS,
        'source': source,
        'upstream_forward_event_count': len(upstream),
        'paper_event_count': len(events),
        'entry_available_count': sum(e.get('entry_open') is not None for e in events),
        'mature_10d_count': sum(bool((e.get('outcomes') or {}).get('10', {}).get('mature')) for e in events),
        'events': events,
        'immutable_recompute_discrepancies': discrepancies,
        'guardrails': {
            'may_change_production': False,
            'may_change_signal_definition': False,
            'historical_results_count_as_forward_oos': False,
            'automatic_promotion': False,
            'broker_orders_enabled': False,
        },
        'warnings': [
            'This ledger observes paper execution only and is not a brokerage order system.',
            'Full Sequence future events are carried from the frozen RMD2 challenger event stream; RMD2 score magnitude does not change paper eligibility.',
            'The execution proxy is SPY V1 and may be expanded only in a separately versioned study.',
        ],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'upstream': len(upstream), 'paper': len(events), 'entries': out['entry_available_count'], 'mature10': out['mature_10d_count'], 'discrepancies': len(discrepancies)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
