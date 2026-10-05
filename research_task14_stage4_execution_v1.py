from __future__ import annotations

import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

import requests

ROOT = Path(__file__).resolve().parent
AUDIT = ROOT / 'docs/data/market_state_sequence_event_audit_v1.json'
OUT = ROOT / 'docs/data/task14_stage4_execution_v1.json'
FROZEN_THROUGH = '2026-10-02'
COST_BPS = (0, 5, 10, 25)
HORIZONS = (5, 10, 20)


def num(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def fetch_spy():
    headers = {'User-Agent': 'Mozilla/5.0 Market-Structure-Lab/Stage4-Execution-V1'}
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
                opens = q.get('open') or []
                closes = q.get('close') or []
                vols = q.get('volume') or []
                rows = []
                for t, o, c, v in zip(ts, opens, closes, vols):
                    o, c, v = num(o), num(c), num(v)
                    if o is None or c is None:
                        continue
                    d = datetime.fromtimestamp(int(t), tz=timezone.utc).strftime('%Y-%m-%d')
                    rows.append({'date': d, 'open': o, 'close': c, 'volume': v})
                if len(rows) < 1000:
                    raise RuntimeError(f'short SPY history: {len(rows)}')
                return rows, {'host': host, 'rows': len(rows), 'transport': 'yahoo_chart_range_10y'}
            except Exception as exc:
                errors.append(f'{host}:{type(exc).__name__}:{exc}')
                time.sleep(1 + attempt)
    raise RuntimeError(' | '.join(errors))


def summarize(vals):
    vals = [num(x) for x in vals]
    vals = [x for x in vals if x is not None]
    if not vals:
        return {'n': 0}
    return {
        'n': len(vals),
        'mean_pct': round(mean(vals), 6),
        'median_pct': round(median(vals), 6),
        'positive_pct': round(100.0 * sum(x > 0 for x in vals) / len(vals), 2),
        'min_pct': round(min(vals), 6),
        'max_pct': round(max(vals), 6),
    }


def ret(entry, exit_):
    if entry in (None, 0) or exit_ is None:
        return None
    return 100.0 * (exit_ / entry - 1.0)


def main():
    audit = json.loads(AUDIT.read_text(encoding='utf-8'))
    events = audit.get('events') or []
    if len(events) != 12:
        raise RuntimeError(f'expected 12 frozen events, got {len(events)}')

    spy, source = fetch_spy()
    idx = {r['date']: i for i, r in enumerate(spy)}
    records = []

    for event in events:
        d = event['date']
        if d not in idx:
            raise RuntimeError(f'SPY missing event date {d}')
        i = idx[d]
        if i + max(HORIZONS) >= len(spy) or i + 1 >= len(spy):
            raise RuntimeError(f'SPY history not mature for {d}')
        r0 = spy[i]
        r1 = spy[i + 1]

        adv_window = spy[max(0, i - 19):i + 1]
        dv = [r['close'] * r['volume'] for r in adv_window if r.get('volume') is not None]
        adv20 = mean(dv) if dv else None

        row = {
            'event_date': d,
            'signal_spy_close': round(r0['close'], 6),
            'next_session_date': r1['date'],
            'next_open': round(r1['open'], 6),
            'next_close': round(r1['close'], 6),
            'gap_signal_close_to_next_open_pct': round(ret(r0['close'], r1['open']), 6),
            'gap_signal_close_to_next_close_pct': round(ret(r0['close'], r1['close']), 6),
            'adv20_usd': None if adv20 is None else round(adv20, 2),
            'capacity_notional_usd': None if adv20 is None else {
                '1pct_adv': round(adv20 * 0.01, 2),
                '5pct_adv': round(adv20 * 0.05, 2),
                '10pct_adv': round(adv20 * 0.10, 2),
            },
            'horizons': {},
        }
        entries = {
            'signal_close': r0['close'],
            'next_open': r1['open'],
            'next_close': r1['close'],
        }
        for h in HORIZONS:
            exit_row = spy[i + h]
            hrow = {'exit_date': exit_row['date'], 'exit_close': round(exit_row['close'], 6), 'entry_modes': {}}
            for mode, px in entries.items():
                gross = ret(px, exit_row['close'])
                costs = {str(b): round(gross - b / 100.0, 6) for b in COST_BPS}
                hrow['entry_modes'][mode] = {
                    'gross_return_pct': round(gross, 6),
                    'net_return_pct_by_round_trip_cost_bps': costs,
                }
            base = hrow['entry_modes']['signal_close']['gross_return_pct']
            hrow['delay_drag_pp'] = {
                'next_open_minus_signal_close': round(hrow['entry_modes']['next_open']['gross_return_pct'] - base, 6),
                'next_close_minus_signal_close': round(hrow['entry_modes']['next_close']['gross_return_pct'] - base, 6),
            }
            row['horizons'][str(h)] = hrow
        records.append(row)

    summary = {'entry_modes': {}, 'delay_drag': {}, 'capacity': {}}
    for h in HORIZONS:
        hs = str(h)
        summary['entry_modes'][hs] = {}
        for mode in ('signal_close', 'next_open', 'next_close'):
            gross = [r['horizons'][hs]['entry_modes'][mode]['gross_return_pct'] for r in records]
            summary['entry_modes'][hs][mode] = {
                'gross': summarize(gross),
                'net_by_round_trip_cost_bps': {
                    str(b): summarize([r['horizons'][hs]['entry_modes'][mode]['net_return_pct_by_round_trip_cost_bps'][str(b)] for r in records])
                    for b in COST_BPS
                },
            }
        summary['delay_drag'][hs] = {
            'next_open_minus_signal_close': summarize([r['horizons'][hs]['delay_drag_pp']['next_open_minus_signal_close'] for r in records]),
            'next_close_minus_signal_close': summarize([r['horizons'][hs]['delay_drag_pp']['next_close_minus_signal_close'] for r in records]),
        }

    summary['entry_gap'] = {
        'next_open': summarize([r['gap_signal_close_to_next_open_pct'] for r in records]),
        'next_close': summarize([r['gap_signal_close_to_next_close_pct'] for r in records]),
    }
    advs = [r['adv20_usd'] for r in records if r['adv20_usd'] is not None]
    summary['capacity']['adv20_usd'] = {
        'n': len(advs), 'median': round(median(advs), 2), 'min': round(min(advs), 2), 'max': round(max(advs), 2)
    }
    for p, key in ((0.01, '1pct_adv'), (0.05, '5pct_adv'), (0.10, '10pct_adv')):
        vals = [x * p for x in advs]
        summary['capacity'][key] = {
            'median_notional_usd': round(median(vals), 2),
            'min_notional_usd': round(min(vals), 2),
            'max_notional_usd': round(max(vals), 2),
        }

    out = {
        'schema': 'TASK14-STAGE4-EXECUTION-V1',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'research_only': True,
        'diagnostic_only': True,
        'production_effect': 'none',
        'thresholds_changed': False,
        'frozen_through_market_date': FROZEN_THROUGH,
        'study_spec': 'research/task14_stage4_execution_v1/STUDY_SPEC.md',
        'instrument': 'SPY',
        'instrument_role': 'tradable execution proxy for the market-level Sequence signal; not a final production instrument decision',
        'source': source,
        'historical_event_count': len(records),
        'entry_modes': ['signal_close', 'next_open', 'next_close'],
        'horizons_sessions_from_signal': list(HORIZONS),
        'round_trip_cost_bps_scenarios': list(COST_BPS),
        'records': records,
        'summary': summary,
        'guardrails': {
            'may_change_production': False,
            'may_change_signal_definition': False,
            'historical_results_count_as_forward_oos': False,
            'automatic_promotion': False,
            'broker_orders_enabled': False,
        },
        'warnings': [
            'SPY raw daily OHLC is used for entry/exit mechanics; this is an execution proxy study.',
            'Cost scenarios are fixed stress assumptions and are not broker-specific fill estimates.',
            'Capacity is a simple ADV participation diagnostic and is not a sizing recommendation.',
        ],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'source': source, 'event_count': len(records), 'summary': summary}, ensure_ascii=False))


if __name__ == '__main__':
    main()
