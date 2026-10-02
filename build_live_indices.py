from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / 'docs/data/live_indices.json'
S = requests.Session()
S.headers.update({'User-Agent': 'Mozilla/5.0 (compatible; Market-Structure-Lab-Live/1.0; educational)'})

CORE = {
    '^GSPC': 'S&P 500',
    '^IXIC': 'Nasdaq Composite',
    '^DJI': 'Dow Jones',
}


def market_state(now_ny: datetime) -> str:
    if now_ny.weekday() >= 5:
        return 'closed'
    hm = (now_ny.hour, now_ny.minute)
    if hm < (4, 0):
        return 'closed'
    if hm < (9, 30):
        return 'pre'
    if hm <= (16, 0):
        return 'regular'
    if hm <= (20, 0):
        return 'post'
    return 'closed'


def fetch_live(sym: str) -> dict:
    q = quote(sym, safe='')
    url = (
        f'https://query1.finance.yahoo.com/v8/finance/chart/{q}'
        '?range=5d&interval=5m&includePrePost=false&events=history'
    )
    error = None
    for host in (url, url.replace('query1.finance.yahoo.com', 'query2.finance.yahoo.com')):
        try:
            r = S.get(host, timeout=20)
            if not r.ok:
                error = f'HTTP {r.status_code}'
                continue
            data = r.json()
            result = ((data.get('chart') or {}).get('result') or [None])[0]
            if not result:
                error = repr((data.get('chart') or {}).get('error'))
                continue
            meta = result.get('meta') or {}
            stamps = result.get('timestamp') or []
            qd = ((result.get('indicators') or {}).get('quote') or [{}])[0]
            closes = qd.get('close') or []
            opens = qd.get('open') or []
            highs = qd.get('high') or []
            lows = qd.get('low') or []
            volumes = qd.get('volume') or []

            last_i = next((i for i in range(len(closes)-1, -1, -1) if closes[i] is not None), None)
            price = meta.get('regularMarketPrice')
            if price is None and last_i is not None:
                price = closes[last_i]
            if price is None:
                raise RuntimeError('no live price')

            prev_close = meta.get('chartPreviousClose') or meta.get('previousClose')
            if prev_close is None:
                tz = ZoneInfo('America/New_York')
                dates = [datetime.fromtimestamp(ts, timezone.utc).astimezone(tz).date().isoformat() for ts in stamps]
                current_date = dates[last_i] if last_i is not None and dates else None
                for i in range((last_i or 0)-1, -1, -1):
                    if closes[i] is not None and dates[i] != current_date:
                        prev_close = closes[i]
                        break
            if prev_close is None:
                raise RuntimeError('no previous close')

            market_time = meta.get('regularMarketTime')
            if market_time:
                asof_dt = datetime.fromtimestamp(market_time, timezone.utc)
            elif last_i is not None and last_i < len(stamps):
                asof_dt = datetime.fromtimestamp(stamps[last_i], timezone.utc)
            else:
                asof_dt = datetime.now(timezone.utc)
            ny = asof_dt.astimezone(ZoneInfo('America/New_York'))
            day = ny.date().isoformat()

            def last_val(arr, fallback=None):
                if last_i is not None and last_i < len(arr) and arr[last_i] is not None:
                    return arr[last_i]
                return fallback

            o = last_val(opens, price)
            h = last_val(highs, max(o, price))
            l = last_val(lows, min(o, price))
            v = last_val(volumes, 0) or 0
            now_ny = datetime.now(timezone.utc).astimezone(ZoneInfo('America/New_York'))
            state = market_state(now_ny)
            age_sec = max(0, int((datetime.now(timezone.utc) - asof_dt).total_seconds()))

            return {
                'date': day,
                'asof': asof_dt.isoformat(),
                'price': round(float(price), 6),
                'previous_close': round(float(prev_close), 6),
                'day_return_pct': round((float(price) / float(prev_close) - 1) * 100, 6),
                'open': round(float(o), 6),
                'high': round(float(h), 6),
                'low': round(float(l), 6),
                'volume': int(v),
                'session_state': state,
                'age_seconds': age_sec,
                'provisional': True,
                'source': 'Yahoo chart 5m snapshot',
            }
        except Exception as exc:
            error = repr(exc)
    raise RuntimeError(error or 'live fetch failed')


def main() -> None:
    out = {
        'schema': 'STRUCTURE-LAB-LIVE-V1',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'market_timezone': 'America/New_York',
        'refresh_target_seconds': 300,
        'instruments': {},
        'errors': {},
    }
    for sym, name in CORE.items():
        try:
            row = fetch_live(sym)
            row['name'] = name
            out['instruments'][sym] = row
            print(sym, row['asof'], row['price'], row['day_return_pct'], row['session_state'], flush=True)
        except Exception as exc:
            out['errors'][sym] = repr(exc)
            print(sym, 'ERROR', repr(exc), flush=True)

    if not out['instruments']:
        raise RuntimeError('No live index snapshots available')
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    temp = TARGET.with_suffix('.tmp')
    temp.write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    os.replace(temp, TARGET)
    print('Wrote', TARGET, flush=True)


if __name__ == '__main__':
    main()
