"""Refresh the public, derived-only Market Structure Lab dataset.

No Frozen V4 private holdings, candidate lists, or raw all-stock bars enter this
public artifact. A failed vendor fetch never silently rewrites history.
"""
from __future__ import annotations

import csv
import io
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from structure_core import numbered_boxes, news_tension, sector_activity, sector_activity_history, updown_stats, validate_bars

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / 'docs/data/structure_lab.json'
NEWS = ROOT / 'docs/data/news_history.json'
S = requests.Session()
S.headers.update({'User-Agent': 'Mozilla/5.0 (compatible; Market-Structure-Lab/1.0; educational)'})

SYMBOLS = {
    '^GSPC': ('S&P 500', 'index'), '^IXIC': ('Nasdaq Composite', 'index'),
    '^DJI': ('Dow Jones', 'index'),
    'SPY': ('S&P 500 ETF', 'benchmark'), 'QQQ': ('Nasdaq-100 ETF', 'benchmark'),
    'DIA': ('Dow ETF', 'benchmark'),
    'XLB': ('Materials', 'sector'), 'XLC': ('Communication', 'sector'),
    'XLE': ('Energy', 'sector'), 'XLF': ('Financials', 'sector'),
    'XLI': ('Industrials', 'sector'), 'XLK': ('Technology', 'sector'),
    'XLP': ('Consumer Staples', 'sector'), 'XLRE': ('Real Estate', 'sector'),
    'XLU': ('Utilities', 'sector'), 'XLV': ('Healthcare', 'sector'),
    'XLY': ('Consumer Discretionary', 'sector'),
}

MACRO = {
    'T10Y3M': '10年-3个月国债期限利差',
    'UNRATE': '失业率',
    'INDPRO': '工业生产指数',
    'PERMIT': '新屋许可数量',
    'BAA10YM': 'BAA公司债相对10年国债利差',
    'NFCI': '芝加哥联储金融状况指数',
}


def get_json(url: str) -> dict:
    error = None
    for host in (url, url.replace('query1.finance.yahoo.com', 'query2.finance.yahoo.com')):
        for wait in (0, 2, 5):
            if wait:
                time.sleep(wait)
            try:
                r = S.get(host, timeout=25)
                if r.ok:
                    return r.json()
                error = f'HTTP {r.status_code}'
                if r.status_code not in (429, 502, 503, 504):
                    break
            except requests.RequestException as exc:
                error = repr(exc)
    raise RuntimeError(f'Yahoo history unavailable: {error}')


def yahoo_bars(sym: str, since: str | None) -> list[list]:
    start = int(pd.Timestamp(since or '1900-01-01', tz='UTC').timestamp())
    end = int(datetime.now(timezone.utc).timestamp()) + 86400
    q = quote(sym, safe='')
    url = (f'https://query1.finance.yahoo.com/v8/finance/chart/{q}'
           f'?period1={start}&period2={end}&interval=1d&events=history')
    data = get_json(url)
    results = (data.get('chart') or {}).get('result') or []
    if not results:
        raise ValueError(f'{sym}: {data.get("chart", {}).get("error", "empty")}')
    obj = results[0]
    stamps = obj.get('timestamp') or []
    qd = ((obj.get('indicators') or {}).get('quote') or [{}])[0]
    bars = []
    for i, unix in enumerate(stamps):
        try:
            date = pd.Timestamp(unix, unit='s', tz='UTC').tz_convert('America/New_York').date().isoformat()
            bars.append([date] + [qd.get(k, [None]*len(stamps))[i]
                                  for k in ('open', 'high', 'low', 'close', 'volume')])
        except (TypeError, ValueError, IndexError):
            continue

    # Yahoo can expose the current US session as a changing "daily" candle.
    # Never treat that incomplete candle as a completed daily observation. The
    # scheduled refresh runs after 18:00 New York time, when today's EOD bar is
    # allowed; manual/intraday refreshes keep only prior completed sessions.
    ny_now = datetime.now(timezone.utc).astimezone(ZoneInfo('America/New_York'))
    if (ny_now.hour, ny_now.minute) < (18, 0):
        today_ny = ny_now.date().isoformat()
        bars = [b for b in bars if b[0] < today_ny]

    return validate_bars(bars)


def merge_bars(previous: list[list], newer: list[list]) -> list[list]:
    return validate_bars(previous + newer)


def macro_monthly(series_id: str) -> list[list]:
    url = f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={quote(series_id)}&cosd=1900-01-01'
    r = S.get(url, timeout=22)
    r.raise_for_status()
    reader = csv.DictReader(io.StringIO(r.text))
    by_month = {}
    for row in reader:
        key = (row.get('DATE') or row.get('observation_date') or '')[:7]
        val = row.get(series_id, '')
        try:
            value = float(val)
            if key and value == value:
                by_month[key] = round(value, 4)
        except (ValueError, TypeError):
            continue
    if not by_month:
        raise RuntimeError(f'FRED {series_id} returned no parseable observations')
    return [[k, v] for k, v in sorted(by_month.items())]


def build(existing: dict | None = None) -> dict:
    existing = existing or {}
    old_symbols = existing.get('instruments') or {}
    instruments, errors = {}, {}
    for sym, (name, group) in SYMBOLS.items():
        old = old_symbols.get(sym, {})
        prev = validate_bars(old.get('bars') or [])
        since = (pd.Timestamp(prev[-1][0]) - pd.Timedelta(days=150)).date().isoformat() if prev else None
        try:
            bars = merge_bars(prev, yahoo_bars(sym, since))
            source_status = 'refreshed'
        except Exception as exc:
            errors[sym] = repr(exc)
            bars, source_status = prev, 'stale_cached' if prev else 'unavailable'
        if not bars:
            continue
        boxes = numbered_boxes(sym.replace('^', ''), bars)
        instruments[sym] = {'name': name, 'group': group, 'start': bars[0][0],
                            'end': bars[-1][0], 'source_status': source_status,
                            'bars': bars, 'boxes': boxes,
                            'updown_lifetime': updown_stats(bars),
                            'sector_activity': sector_activity(bars) if group == 'sector' else None,
                            'sector_history': sector_activity_history(bars) if group == 'sector' else []}
        print(sym, len(bars), len(boxes), source_status, flush=True)
        time.sleep(.4)

    if not instruments:
        raise RuntimeError('No historical prices available; old public dataset not overwritten.')

    macro = existing.get('macro') or {}
    for series_id, name in MACRO.items():
        try:
            history = macro_monthly(series_id)
            macro[series_id] = {'name': name, 'observations': history,
                                'start': history[0][0], 'end': history[-1][0],
                                'status': 'refreshed', 'point_in_time': False}
        except Exception as exc:
            errors[series_id] = repr(exc)
            if series_id in macro:
                macro[series_id]['status'] = 'stale_cached'
        time.sleep(.4)

    try:
        raw_news = json.loads(NEWS.read_text(encoding='utf-8'))
        news = news_tension(raw_news, {k: instruments.get(sym, {}).get('bars', [])
                for k,sym in {'sp500': '^GSPC','nasdaq': '^IXIC','dow': '^DJI'}.items()})
    except (OSError, json.JSONDecodeError) as exc:
        news = existing.get('news_tension', [])
        errors['news'] = repr(exc)

    return {
        'schema': 'STRUCTURE-LAB-V1',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'policy': {
            'price': 'Yahoo daily raw OHLCV when available; incomplete US intraday candles excluded; ETF inception limits coverage',
            'box_eligibility': 'ONLY next session after detected_at, never start_at',
            'box_scores': 'provisional descriptive 0-10; historical finalized scores are EX POST',
            'news': 'equal-weight reaction_adjusted components from recorded news_history only',
            'activity': 'current ETF dollar volume and high-low percent ranked vs prior 60 trading days',
            'macro': 'latest/revised FRED monthly observations; publication vintages not captured',
            'universe': 'benchmarks and sector ETFs only; NOT all US stocks; no delisted-stock coverage'
        },
        'instruments': instruments,
        'macro': macro,
        'news_tension': news,
        'news_status': 'exploratory_short_history' if len(news) < 60 else 'research_observations',
        'errors': errors,
    }


def main() -> None:
    try:
        existing = json.loads(TARGET.read_text(encoding='utf-8')) if TARGET.exists() else {}
    except json.JSONDecodeError:
        existing = {}
    result = build(existing)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    temp = TARGET.with_suffix('.tmp')
    temp.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    os.replace(temp, TARGET)
    print('Wrote', TARGET, 'instruments', len(result['instruments']),
          'news observations', len(result['news_tension']),
          'errors', len(result['errors']))


if __name__ == '__main__':
    main()
