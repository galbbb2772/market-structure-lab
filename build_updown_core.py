"""Fast refresh path for the three-index up/down-ratio page.

This keeps the existing public dataset intact but only refreshes S&P 500,
Nasdaq Composite, and Dow Jones. It deliberately skips FRED and sector ETF
refreshes so the core page is not blocked by unrelated providers.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from build_structure_lab import TARGET, yahoo_bars, merge_bars, _drop_incomplete_session
from structure_core import numbered_boxes, updown_stats, validate_bars

CORE = {
    '^GSPC': ('S&P 500', 'index'),
    '^IXIC': ('Nasdaq Composite', 'index'),
    '^DJI': ('Dow Jones', 'index'),
}


def main() -> None:
    path = Path(TARGET)
    data = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {
        'schema': 'STRUCTURE-LAB-V1', 'instruments': {}, 'macro': {},
        'news_tension': [], 'errors': {}, 'policy': {}
    }
    instruments = data.setdefault('instruments', {})
    errors = data.setdefault('errors', {})

    for sym, (name, group) in CORE.items():
        old = instruments.get(sym, {})
        prev = validate_bars(old.get('bars') or [])
        since = (pd.Timestamp(prev[-1][0]) - pd.Timedelta(days=150)).date().isoformat() if prev else None
        try:
            bars = merge_bars(prev, yahoo_bars(sym, since))
            source_status = 'refreshed'
            errors.pop(sym, None)
        except Exception as exc:
            bars = _drop_incomplete_session(prev)
            source_status = 'stale_cached' if bars else 'unavailable'
            errors[sym] = repr(exc)
        if not bars:
            raise RuntimeError(f'{sym}: no usable cached or refreshed bars')

        instruments[sym] = {
            'name': name,
            'group': group,
            'start': bars[0][0],
            'end': bars[-1][0],
            'source_status': source_status,
            'bars': bars,
            'boxes': numbered_boxes(sym.replace('^', ''), bars),
            'updown_lifetime': updown_stats(bars),
            'sector_activity': None,
            'sector_history': [],
        }
        print(sym, len(bars), bars[0][0], bars[-1][0], source_status, flush=True)

    data['generated_at'] = datetime.now(timezone.utc).isoformat()
    data.setdefault('policy', {})['core_refresh'] = (
        'Three-index fast path: ^GSPC, ^IXIC, ^DJI refreshed independently; '
        'macro and sector providers do not block this page.'
    )
    data['errors'] = errors

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    os.replace(tmp, path)
    print('Wrote', path, 'core indices refreshed', flush=True)


if __name__ == '__main__':
    main()
