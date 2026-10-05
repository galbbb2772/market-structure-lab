"""Task 1/4 cross-market confirmation V1 using Yahoo chart API.

Diagnostic-only repair/fallback for the Stage-2 cross-market block when Stooq is
unavailable from GitHub Actions. No production or frozen OOS behavior changes.
"""
from __future__ import annotations

import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

import requests

ROOT = Path(__file__).resolve().parent
AUDIT = ROOT / "docs/data/market_state_sequence_event_audit_v1.json"
BOX = ROOT / "docs/data/market_state_box_v1.json"
OUT = ROOT / "docs/data/task14_crossmarket_confirmation_v1.json"
TICKERS = {"QQQ":"QQQ","IWM":"IWM","HYG":"HYG","LQD":"LQD","VIX":"^VIX"}


def num(x):
    try:
        v=float(x)
        return v if math.isfinite(v) else None
    except (TypeError,ValueError):
        return None


def qtile(vals,p):
    a=sorted(x for x in (num(v) for v in vals) if x is not None)
    if not a: return None
    z=(len(a)-1)*p; i=int(z); j=min(i+1,len(a)-1); f=z-i
    return a[i]+(a[j]-a[i])*f


def fetch_yahoo(ticker):
    params={"period1":1451606400,"period2":1791244800,"interval":"1d","events":"history","includeAdjustedClose":"true"}
    headers={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130 Safari/537.36"}
    errors=[]
    for host in ("query1.finance.yahoo.com","query2.finance.yahoo.com"):
        url=f"https://{host}/v8/finance/chart/{requests.utils.quote(ticker,safe='')}"
        for attempt in range(2):
            try:
                r=requests.get(url,params=params,headers=headers,timeout=15)
                r.raise_for_status()
                obj=r.json()["chart"]["result"][0]
                ts=obj.get("timestamp") or []
                quote=((obj.get("indicators") or {}).get("quote") or [{}])[0]
                closes=quote.get("close") or []
                out=[]
                for t,c in zip(ts,closes):
                    c=num(c)
                    if c is None: continue
                    d=datetime.fromtimestamp(int(t),tz=timezone.utc).strftime("%Y-%m-%d")
                    out.append((d,c))
                if len(out)>=1000:
                    return out,{"host":host,"rows":len(out)}
                errors.append(f"{host}: short series {len(out)}")
            except Exception as e:
                errors.append(f"{host}: {type(e).__name__}: {e}")
                time.sleep(1+attempt)
    raise RuntimeError(" | ".join(errors))


def ret_n(series,date,n=5):
    arr=[x for x in series if x[0]<=date]
    if len(arr)<=n: return None
    a=arr[-1][1]; b=arr[-1-n][1]
    return None if b in (None,0) else 100*(a/b-1)


def spx_forward_map():
    src=json.loads(BOX.read_text(encoding="utf-8"))
    rows=src.get("daily") or []
    c=[num(r.get("sp500_close")) for r in rows]
    out={}
    for i,r in enumerate(rows):
        d={}
        for h in (5,10,20):
            d[f"fwd_{h}d"]=None if i+h>=len(rows) or c[i] in (None,0) or c[i+h] is None else 100*(c[i+h]/c[i]-1)
        out[r["date"]]=d
    return out


def summarize(recs):
    out={"n":len(recs)}
    for h in (5,10,20):
        vals=[num(r.get(f"fwd_{h}d")) for r in recs]; vals=[x for x in vals if x is not None]
        out[f"{h}d"]={"n":len(vals)} if not vals else {"n":len(vals),"mean_pct":round(mean(vals),4),"median_pct":round(median(vals),4),"positive_pct":round(100*sum(x>0 for x in vals)/len(vals),2),"p10_pct":round(qtile(vals,.1),4),"p90_pct":round(qtile(vals,.9),4)}
    return out


def main():
    audit=json.loads(AUDIT.read_text(encoding="utf-8"))
    events=audit.get("events") or []
    fwd=spx_forward_map()
    series={}; sources={}; errors={}
    for name,ticker in TICKERS.items():
        try:
            series[name],sources[name]=fetch_yahoo(ticker)
        except Exception as e:
            errors[name]=str(e)
    recs=[]
    for e in events:
        d=e["date"]; conf=0; avail=0; row={"date":d}
        for name in ("QQQ","IWM","HYG","LQD"):
            v=ret_n(series[name],d,5) if name in series else None
            row[f"{name}_ret5_pct"]=None if v is None else round(v,4)
            if v is not None:
                avail+=1; conf+=int(v>0)
        v=ret_n(series["VIX"],d,5) if "VIX" in series else None
        row["VIX_ret5_pct"]=None if v is None else round(v,4)
        if v is not None:
            avail+=1; conf+=int(v<0)
        row["confirmation_count"]=conf
        row["available_components"]=avail
        row.update(fwd.get(d,{}))
        recs.append(row)
    complete=[r for r in recs if r["available_components"]==5]
    groups={
        "confirm_0_2":summarize([r for r in complete if r["confirmation_count"]<=2]),
        "confirm_3_plus":summarize([r for r in complete if r["confirmation_count"]>=3]),
        "confirm_4_plus":summarize([r for r in complete if r["confirmation_count"]>=4]),
    }
    by_count={str(k):summarize([r for r in complete if r["confirmation_count"]==k]) for k in range(6)}
    out={
        "schema":"TASK14-CROSSMARKET-CONFIRMATION-V1",
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "research_only":True,"diagnostic_only":True,"production_effect":"none",
        "event_definition":"frozen D_TO_BOTH_REBOUND_SCORE historical event set",
        "feature_definition":"5-session direction at/on event date: QQQ/IWM/HYG/LQD positive and VIX negative each count +1; no optimized weights or thresholds",
        "source":"Yahoo Finance chart API fallback",
        "sources":sources,"errors":errors,
        "event_count":len(events),"complete_crossmarket_event_count":len(complete),
        "records":recs,"groups":groups,"by_confirmation_count":by_count,
        "decision":{"may_change_production":False,"may_change_existing_forward_oos":False,"status":"historical_diagnostic_only","promotion_requirement":"Any confirmation gate inspired by this table requires separate preregistration and Forward OOS."},
        "warnings":["This is post-discovery historical evidence, not Forward OOS.","Twelve Sequence events are heavily concentrated in 2022.","Five-session direction and the 3+/4+ groupings are fixed diagnostics, not optimized production gates."],
    }
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"complete":len(complete),"sources":sources,"errors":errors,"groups":groups},ensure_ascii=False))


if __name__=="__main__":
    main()
