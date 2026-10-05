from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
UPSTREAM = ROOT / 'docs/data/task14_challenger_forward_oos_v1.json'
FEED = ROOT / 'docs/data/stock_candidate_feed_v1.json'
OUT = ROOT / 'docs/data/task14_stage4_stock_candidate_adapter_v1.json'
SPEC = 'research/task14_stage4_stock_candidate_adapter_v1/STUDY_SPEC.md'
FROZEN_THROUGH = '2026-10-02'

FORBIDDEN_KEY_TOKENS = (
    'future_return', 'forward_return', 'fwd_return', 'future_pnl', 'forward_pnl',
    'realized_pnl', 'realized_return', 'future_outcome', 'forward_outcome',
    'outcome_label', 'target_return', 'future_label',
)


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def iso_date(value):
    if not isinstance(value, str) or len(value) != 10:
        raise RuntimeError(f'invalid market date: {value!r}')
    datetime.strptime(value, '%Y-%m-%d')
    return value


def event_date(event):
    if not isinstance(event, dict):
        return None
    for key in ('signal_date', 'event_date', 'date', 'onset_date'):
        v = event.get(key)
        if isinstance(v, str) and len(v) == 10:
            return v
    return None


def challenger_snapshot(upstream):
    challengers = upstream.get('challengers') or {}
    out = {}
    aligned_dates = set()
    for name in ('early_sequence', 'rmd2_price_score', 'dplus1_entry', 'dual_severity_hazard'):
        block = challengers.get(name) or {}
        events = block.get('events') or []
        dates = sorted({d for d in (event_date(x) for x in events) if d})
        aligned_dates.update(dates)
        out[name] = {
            'forward_event_count': int(block.get('forward_event_count') or 0),
            'mature_10d_event_count': int(block.get('mature_10d_event_count') or 0),
            'event_dates': dates,
            'source_recompute_discrepancy_count': len(block.get('source_recompute_discrepancies') or []),
        }
    return out, aligned_dates


def find_forbidden_keys(obj, prefix=''):
    bad = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = str(k).lower()
            path = f'{prefix}.{k}' if prefix else str(k)
            if any(tok in key for tok in FORBIDDEN_KEY_TOKENS):
                bad.append(path)
            bad.extend(find_forbidden_keys(v, path))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            bad.extend(find_forbidden_keys(v, f'{prefix}[{i}]'))
    return bad


def validate_feed(feed, latest_market_date, aligned_dates):
    if feed.get('schema') != 'STOCK-CANDIDATE-FEED-V1':
        raise RuntimeError('candidate feed schema must be STOCK-CANDIDATE-FEED-V1')
    for key in ('generated_at', 'as_of_market_date', 'source_name', 'source_version', 'candidates'):
        if key not in feed:
            raise RuntimeError(f'missing feed field: {key}')
    as_of = iso_date(feed['as_of_market_date'])
    if latest_market_date and as_of > latest_market_date:
        raise RuntimeError(f'candidate snapshot {as_of} is later than upstream market-state date {latest_market_date}')
    candidates = feed.get('candidates')
    if not isinstance(candidates, list):
        raise RuntimeError('candidates must be an array')

    symbols, ids, standardized = set(), set(), []
    for i, c in enumerate(candidates):
        if not isinstance(c, dict):
            raise RuntimeError(f'candidate[{i}] must be an object')
        for key in ('symbol', 'candidate_id', 'first_seen_at', 'rank', 'trigger_reasons'):
            if key not in c:
                raise RuntimeError(f'candidate[{i}] missing field: {key}')
        symbol = str(c['symbol']).strip().upper()
        cid = str(c['candidate_id']).strip()
        if not symbol or not cid:
            raise RuntimeError(f'candidate[{i}] has empty symbol/candidate_id')
        if symbol in symbols:
            raise RuntimeError(f'duplicate candidate symbol: {symbol}')
        if cid in ids:
            raise RuntimeError(f'duplicate candidate_id: {cid}')
        reasons = c.get('trigger_reasons')
        if not isinstance(reasons, list) or not reasons:
            raise RuntimeError(f'candidate[{i}] trigger_reasons must be non-empty array')
        bad = find_forbidden_keys(c)
        if bad:
            raise RuntimeError(f'candidate[{i}] contains future/outcome fields: {bad}')
        symbols.add(symbol)
        ids.add(cid)
        standardized.append({
            **c,
            'symbol': symbol,
            'candidate_id': cid,
            'adapter_forward_eligible': as_of > FROZEN_THROUGH,
            'adapter_signal_aligned': as_of in aligned_dates,
        })

    return {
        'status': 'READY' if candidates else 'EMPTY_FEED',
        'as_of_market_date': as_of,
        'source_name': feed['source_name'],
        'source_version': feed['source_version'],
        'source_generated_at': feed['generated_at'],
        'candidate_count': len(standardized),
        'forward_eligible_count': sum(bool(x['adapter_forward_eligible']) for x in standardized),
        'signal_aligned_count': sum(bool(x['adapter_signal_aligned']) for x in standardized),
        'candidates': standardized,
    }


def main():
    if not UPSTREAM.exists():
        raise RuntimeError('missing Task 1/4 forward-OOS upstream file')
    upstream = load_json(UPSTREAM)
    if upstream.get('schema') != 'TASK14-CHALLENGER-FORWARD-OOS-V1':
        raise RuntimeError('unexpected Task 1/4 forward-OOS schema')
    if upstream.get('frozen_through_market_date') != FROZEN_THROUGH:
        raise RuntimeError('Task 1/4 freeze boundary changed')
    latest_market_date = upstream.get('latest_market_date')
    if latest_market_date:
        iso_date(latest_market_date)
    challengers, aligned_dates = challenger_snapshot(upstream)

    if FEED.exists():
        adapter = validate_feed(load_json(FEED), latest_market_date, aligned_dates)
    else:
        adapter = {
            'status': 'AWAITING_UPSTREAM_FEED',
            'as_of_market_date': None,
            'source_name': None,
            'source_version': None,
            'source_generated_at': None,
            'candidate_count': 0,
            'forward_eligible_count': 0,
            'signal_aligned_count': 0,
            'candidates': [],
        }

    out = {
        'schema': 'TASK14-STAGE4-STOCK-CANDIDATE-ADAPTER-V1',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'research_only': True,
        'paper_only': True,
        'production_effect': 'none',
        'broker_orders_enabled': False,
        'frozen_through_market_date': FROZEN_THROUGH,
        'latest_upstream_market_date': latest_market_date,
        'study_spec': SPEC,
        'upstream_forward_oos': challengers,
        'adapter': adapter,
        'guardrails': {
            'historical_results_count_as_forward_oos': False,
            'automatic_stock_selection': False,
            'automatic_sector_exclusion': False,
            'automatic_policy_promotion': False,
            'rank_recomputed_by_adapter': False,
            'future_outcome_fields_allowed': False,
        },
        'warnings': [
            'This adapter standardizes an upstream candidate feed; it does not create or optimize stock candidates.',
            'Historical/backfilled candidates cannot become forward evidence.',
            'Individual-stock execution requires a separately frozen candidate-generation rule and prospective validation.',
        ],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({
        'status': adapter['status'],
        'candidate_count': adapter['candidate_count'],
        'forward_eligible_count': adapter['forward_eligible_count'],
        'signal_aligned_count': adapter['signal_aligned_count'],
        'latest_upstream_market_date': latest_market_date,
        'challenger_counts': {k: v['forward_event_count'] for k, v in challengers.items()},
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
