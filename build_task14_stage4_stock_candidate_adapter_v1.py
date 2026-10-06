from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
UPSTREAM = ROOT / 'docs/data/task14_challenger_forward_oos_v1.json'
FEED = ROOT / 'docs/data/stock_candidate_feed_v1.json'
OUT = ROOT / 'docs/data/task14_stage4_stock_candidate_adapter_v1.json'
SPEC = 'research/task14_stage4_stock_candidate_adapter_v1/STUDY_SPEC.md'
FROZEN_THROUGH = '2026-10-02'

CANONICAL_FEED_URL = 'https://api.github.com/repos/galbbb2772/frozen-v4/contents/docs/data/stock_candidate_feed_v1.json?ref=main'
MIRROR_FEED_URL = 'https://raw.githubusercontent.com/galbbb2772/frozen-v4-dashboard/main/data/stock_candidate_feed_v1.json'
REMOTE_FEED_URLS = (CANONICAL_FEED_URL, MIRROR_FEED_URL)
EXPECTED_SOURCE_NAME = 'frozen-v4'
EXPECTED_SOURCE_VERSION = 'FROZEN-V4-STRICT-V3-MASSIVE-EOD-V1'

FORBIDDEN_KEY_TOKENS = (
    'future_return', 'forward_return', 'fwd_return', 'future_pnl', 'forward_pnl',
    'realized_pnl', 'realized_return', 'future_outcome', 'forward_outcome',
    'outcome_label', 'target_return', 'future_label',
)


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def atomic_write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def refresh_remote_feed():
    errors = []
    for i, url in enumerate(REMOTE_FEED_URLS):
        req = Request(url, headers={'User-Agent': 'market-structure-lab-task14-adapter-v1'})
        try:
            with urlopen(req, timeout=20) as r:
                raw = r.read().decode('utf-8')
            if 'api.github.com/repos/' in url and '/contents/' in url:
                meta = json.loads(raw)
                if meta.get('encoding') != 'base64' or not meta.get('content'):
                    raise RuntimeError('canonical GitHub contents response missing base64 content')
                raw = base64.b64decode(meta['content']).decode('utf-8')
            obj = json.loads(raw)
            if obj.get('schema') != 'STOCK-CANDIDATE-FEED-V1':
                raise RuntimeError(f"unexpected remote feed schema: {obj.get('schema')!r}")
            atomic_write_json(FEED, obj)
            status = 'REMOTE_CANONICAL_REFRESHED' if i == 0 else 'REMOTE_MIRROR_REFRESHED'
            prior_errors = ' | '.join(errors) if errors else None
            return status, prior_errors, url
        except Exception as exc:
            errors.append(f'{url}: {type(exc).__name__}: {exc}')
    detail = ' | '.join(errors)
    if FEED.exists():
        return 'CACHED_LOCAL_FALLBACK', detail, None
    return 'REMOTE_UNAVAILABLE_NO_CACHE', detail, None


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


def validate_feed(feed, latest_market_date, aligned_dates, fetch_status, fetch_error, fetched_from_url):
    if feed.get('schema') != 'STOCK-CANDIDATE-FEED-V1':
        raise RuntimeError('candidate feed schema must be STOCK-CANDIDATE-FEED-V1')
    for key in ('generated_at', 'source_name', 'source_version', 'future_outcomes_included', 'snapshots'):
        if key not in feed:
            raise RuntimeError(f'missing feed field: {key}')
    if feed['source_name'] != EXPECTED_SOURCE_NAME:
        raise RuntimeError(f"unexpected candidate source: {feed['source_name']!r}")
    if feed['source_version'] != EXPECTED_SOURCE_VERSION:
        raise RuntimeError(f"candidate source version changed: {feed['source_version']!r}")
    if feed.get('future_outcomes_included') is not False:
        raise RuntimeError('candidate feed must explicitly exclude future outcomes')

    snapshots = feed.get('snapshots')
    if not isinstance(snapshots, list):
        raise RuntimeError('feed snapshots must be an array')
    if int(feed.get('snapshot_count') or 0) != len(snapshots):
        raise RuntimeError('feed snapshot_count mismatch')

    standardized_snapshots = []
    usable_flat = []
    deferred_snapshot_count = 0
    global_ids = set()
    last_day = None

    for si, snap in enumerate(snapshots):
        if not isinstance(snap, dict):
            raise RuntimeError(f'snapshot[{si}] must be an object')
        as_of = iso_date(snap.get('as_of_market_date'))
        if last_day and as_of <= last_day:
            raise RuntimeError('candidate snapshots must be strictly increasing by as_of_market_date')
        last_day = as_of

        candidates = snap.get('candidates')
        if not isinstance(candidates, list):
            raise RuntimeError(f'snapshot[{si}] candidates must be an array')
        if int(snap.get('candidate_count') or 0) != len(candidates):
            raise RuntimeError(f'snapshot[{si}] candidate_count mismatch')

        canon = json.dumps(candidates, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
        digest = hashlib.sha256(canon.encode('utf-8')).hexdigest()
        if snap.get('snapshot_sha256') != digest:
            raise RuntimeError(f'snapshot[{si}] sha256 mismatch')

        usable = latest_market_date is None or as_of <= latest_market_date
        if not usable:
            deferred_snapshot_count += 1

        symbols = set()
        ranks = set()
        std_candidates = []
        for i, c in enumerate(candidates):
            if not isinstance(c, dict):
                raise RuntimeError(f'snapshot[{si}] candidate[{i}] must be an object')
            for key in ('symbol', 'candidate_id', 'first_seen_at', 'rank', 'trigger_reasons'):
                if key not in c:
                    raise RuntimeError(f'snapshot[{si}] candidate[{i}] missing field: {key}')

            symbol = str(c['symbol']).strip().upper()
            cid = str(c['candidate_id']).strip()
            if not symbol or not cid:
                raise RuntimeError(f'snapshot[{si}] candidate[{i}] has empty symbol/candidate_id')
            if symbol in symbols:
                raise RuntimeError(f'duplicate symbol inside {as_of}: {symbol}')
            if cid in global_ids:
                raise RuntimeError(f'duplicate immutable candidate_id across feed: {cid}')
            try:
                rank = int(c['rank'])
            except Exception:
                raise RuntimeError(f'invalid upstream rank for {cid}: {c.get("rank")!r}')
            if rank <= 0 or rank in ranks:
                raise RuntimeError(f'duplicate/invalid upstream rank in {as_of}: {rank}')
            reasons = c.get('trigger_reasons')
            if not isinstance(reasons, list) or not reasons:
                raise RuntimeError(f'candidate {cid} trigger_reasons must be non-empty array')
            bad = find_forbidden_keys(c)
            if bad:
                raise RuntimeError(f'candidate {cid} contains future/outcome fields: {bad}')

            symbols.add(symbol)
            ranks.add(rank)
            global_ids.add(cid)
            forward_eligible = usable and as_of > FROZEN_THROUGH
            signal_aligned = forward_eligible and as_of in aligned_dates
            std = {
                **c,
                'symbol': symbol,
                'candidate_id': cid,
                'rank': rank,
                'as_of_market_date': as_of,
                'adapter_snapshot_usable': usable,
                'adapter_forward_eligible': forward_eligible,
                'adapter_signal_aligned': signal_aligned,
                'adapter_trade_pool_eligible': bool(signal_aligned and c.get('upstream_eligible') is True),
            }
            std_candidates.append(std)
            if usable:
                usable_flat.append(std)

        standardized_snapshots.append({
            'as_of_market_date': as_of,
            'entry_date': snap.get('entry_date'),
            'first_published_at': snap.get('first_published_at'),
            'snapshot_sha256': snap.get('snapshot_sha256'),
            'candidate_count': len(std_candidates),
            'frozen_gate_eligible_count': int(snap.get('frozen_gate_eligible_count') or 0),
            'adapter_snapshot_usable': usable,
            'adapter_signal_aligned': bool(usable and as_of > FROZEN_THROUGH and as_of in aligned_dates),
            'candidates': std_candidates,
        })

    usable_snaps = [s for s in standardized_snapshots if s['adapter_snapshot_usable']]
    status = 'EMPTY_FEED'
    if snapshots and not usable_snaps:
        status = 'FEED_AHEAD_OF_UPSTREAM'
    elif usable_snaps:
        status = 'READY'

    aligned_candidates = [x for x in usable_flat if x['adapter_signal_aligned']]
    trade_pool = [x for x in usable_flat if x['adapter_trade_pool_eligible']]
    return {
        'status': status,
        'feed_fetch_status': fetch_status,
        'feed_fetch_error': fetch_error,
        'source_url': fetched_from_url or CANONICAL_FEED_URL,
        'source_name': feed['source_name'],
        'source_version': feed['source_version'],
        'source_generated_at': feed['generated_at'],
        'source_contract': feed.get('source_contract'),
        'feed_latest_as_of_market_date': feed.get('latest_as_of_market_date'),
        'snapshot_count': len(standardized_snapshots),
        'usable_snapshot_count': len(usable_snaps),
        'deferred_snapshot_count': deferred_snapshot_count,
        'candidate_count': len(usable_flat),
        'forward_eligible_count': sum(bool(x['adapter_forward_eligible']) for x in usable_flat),
        'signal_aligned_count': len(aligned_candidates),
        'trade_pool_eligible_count': len(trade_pool),
        'latest_usable_snapshot_date': usable_snaps[-1]['as_of_market_date'] if usable_snaps else None,
        'snapshots': standardized_snapshots,
        'candidates': usable_flat,
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

    fetch_status, fetch_error, fetched_from_url = refresh_remote_feed()
    if FEED.exists():
        adapter = validate_feed(load_json(FEED), latest_market_date, aligned_dates, fetch_status, fetch_error, fetched_from_url)
    else:
        adapter = {
            'status': 'AWAITING_UPSTREAM_FEED',
            'feed_fetch_status': fetch_status,
            'feed_fetch_error': fetch_error,
            'source_url': CANONICAL_FEED_URL,
            'source_name': None,
            'source_version': None,
            'source_generated_at': None,
            'source_contract': None,
            'feed_latest_as_of_market_date': None,
            'snapshot_count': 0,
            'usable_snapshot_count': 0,
            'deferred_snapshot_count': 0,
            'candidate_count': 0,
            'forward_eligible_count': 0,
            'signal_aligned_count': 0,
            'trade_pool_eligible_count': 0,
            'latest_usable_snapshot_date': None,
            'snapshots': [],
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
            'nearest_date_alignment_allowed': False,
            'upstream_source_version_pinned': True,
        },
        'warnings': [
            'Frozen V4 Strict V3 is the upstream source of truth; this adapter never re-ranks or regenerates stock candidates.',
            'Feed snapshots later than the Task 1/4 upstream market date are retained but deferred and cannot align early.',
            'Historical/backfilled candidates cannot become Forward-OOS evidence.',
            'adapter_trade_pool_eligible means exact-date alignment plus Frozen V4 upstream eligibility; it is not authorization to trade.',
        ],
    }
    atomic_write_json(OUT, out)
    print(json.dumps({
        'status': adapter['status'],
        'feed_fetch_status': adapter['feed_fetch_status'],
        'snapshot_count': adapter['snapshot_count'],
        'usable_snapshot_count': adapter['usable_snapshot_count'],
        'candidate_count': adapter['candidate_count'],
        'forward_eligible_count': adapter['forward_eligible_count'],
        'signal_aligned_count': adapter['signal_aligned_count'],
        'trade_pool_eligible_count': adapter['trade_pool_eligible_count'],
        'latest_upstream_market_date': latest_market_date,
        'challenger_counts': {k: v['forward_event_count'] for k, v in challengers.items()},
    }, ensure_ascii=False, indent=2))


# CI trigger: refresh public Frozen V4 candidate mirror bridge
if __name__ == '__main__':
    main()
