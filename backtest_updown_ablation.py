"""Ablation study for the index-only up/down-ratio strategy.

Keeps the signal fixed and toggles only three risk controls:
1) MA200 entry filter
2) 10-session maximum holding period
3) 5% stop loss

Universe is strictly ^GSPC, ^IXIC, ^DJI. No stock selection.
Signal: 20-session up/down K-line ratio <= 2/3 to enter, >= 1.0 to exit.
Close-confirmed signals execute at next session open. Stop is gap-aware using daily OHLC.
"""
from __future__ import annotations

import json, math
from datetime import date
from pathlib import Path
from statistics import mean, pstdev

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "docs/data/structure_lab.json"
OUT_PATH = ROOT / "docs/data/updown_index_ablation.json"
SYMBOLS = ["^GSPC", "^IXIC", "^DJI"]
WINDOW = 20
ENTRY_RATIO = 2 / 3
EXIT_RATIO = 1.0
MA_WINDOW = 200
MAX_HOLD = 10
STOP_PCT = 0.05

CONFIGS = {
    "BASE":      {"ma": False, "time": False, "stop": False},
    "MA_ONLY":   {"ma": True,  "time": False, "stop": False},
    "TIME_ONLY": {"ma": False, "time": True,  "stop": False},
    "STOP_ONLY": {"ma": False, "time": False, "stop": True},
    "MA_TIME":   {"ma": True,  "time": True,  "stop": False},
    "MA_STOP":   {"ma": True,  "time": False, "stop": True},
    "TIME_STOP": {"ma": False, "time": True,  "stop": True},
    "ALL_V2":    {"ma": True,  "time": True,  "stop": True},
}

def finite(x):
    try: return x is not None and math.isfinite(float(x))
    except (TypeError, ValueError): return False

def load_bars(obj):
    out=[]
    for b in obj.get("bars", []):
        if len(b) < 5 or not all(finite(b[i]) for i in (1,2,3,4)):
            continue
        out.append({"date":str(b[0]),"open":float(b[1]),"high":float(b[2]),"low":float(b[3]),"close":float(b[4])})
    out.sort(key=lambda x:x["date"])
    return out

def rolling_ratio(bars):
    dirs=[None]
    for i in range(1,len(bars)):
        a,b=bars[i-1]["close"],bars[i]["close"]
        dirs.append(1 if b>a else -1 if b<a else 0)
    r=[None]*len(bars)
    for i in range(WINDOW,len(bars)):
        w=dirs[i-WINDOW+1:i+1]
        up=sum(x==1 for x in w); dn=sum(x==-1 for x in w)
        r[i]=math.inf if dn==0 and up else (up/dn if dn else None)
    return r

def sma200(bars):
    out=[None]*len(bars); s=0.0
    for i,b in enumerate(bars):
        s += b["close"]
        if i>=MA_WINDOW: s -= bars[i-MA_WINDOW]["close"]
        if i>=MA_WINDOW-1: out[i]=s/MA_WINDOW
    return out

def years(a,b):
    return max((date.fromisoformat(b)-date.fromisoformat(a)).days/365.2425,1/365.2425)

def maxdd(eq):
    peak=0.0; worst=0.0
    for v in eq:
        peak=max(peak,v)
        if peak>0: worst=min(worst,v/peak-1)
    return worst

def summarize(eq, dates, drets, trades, exposure):
    total=eq[-1]/eq[0]-1 if eq else 0
    yrs=years(dates[0],dates[-1]) if len(dates)>1 else 0
    cagr=(eq[-1]/eq[0])**(1/yrs)-1 if yrs>0 else 0
    sd=pstdev(drets) if len(drets)>1 else 0
    sh=mean(drets)/sd*math.sqrt(252) if sd>0 else None
    rets=[t["return_pct"]/100 for t in trades]
    wins=sum(x>0 for x in rets)
    reasons={}
    for t in trades: reasons[t["exit_reason"]]=reasons.get(t["exit_reason"],0)+1
    return {
        "total_return_pct":round(total*100,3),"cagr_pct":round(cagr*100,3),
        "max_drawdown_pct":round(maxdd(eq)*100,3),
        "sharpe":round(sh,3) if sh is not None else None,
        "trades":len(trades),"win_rate_pct":round(wins/len(trades)*100,2) if trades else None,
        "avg_trade_pct":round(mean(rets)*100,3) if rets else None,
        "median_holding_days":sorted(t["holding_days"] for t in trades)[len(trades)//2] if trades else None,
        "exposure_pct":round(exposure/len(dates)*100,2) if dates else 0.0,
        "exit_reasons":reasons,
    }

def backtest(bars,cfg):
    rr=rolling_ratio(bars); ma=sma200(bars)
    first=max(WINDOW,MA_WINDOW-1 if cfg["ma"] else WINDOW)
    start=first+1
    cash=1.0; units=0.0; pos=False
    entry_px=entry_i=None; entry_date=None
    eq=[]; dates=[]; drets=[]; trades=[]; exposure=0; prev=1.0
    pending_entry=False; pending_exit=False; pending_reason=None

    for i in range(start,len(bars)):
        today=bars[i]; prev_i=i-1

        # Execute previous-close decisions at today's open.
        if pending_exit and pos:
            px=today["open"]
            cash=units*px
            trades.append({"entry_date":entry_date,"exit_date":today["date"],"entry_price":entry_px,
                           "exit_price":px,"return_pct":round((px/entry_px-1)*100,4),
                           "holding_days":i-entry_i,"exit_reason":pending_reason})
            units=0.0; pos=False; entry_px=entry_i=entry_date=None
        pending_exit=False; pending_reason=None

        if pending_entry and not pos:
            px=today["open"]
            units=cash/px; cash=0.0; pos=True
            entry_px=px; entry_i=i; entry_date=today["date"]
        pending_entry=False

        # Intraday stop on an already-open position, including gap through stop.
        if pos and cfg["stop"]:
            stop=entry_px*(1-STOP_PCT)
            if today["open"] <= stop:
                px=today["open"]; cash=units*px
                trades.append({"entry_date":entry_date,"exit_date":today["date"],"entry_price":entry_px,
                               "exit_price":px,"return_pct":round((px/entry_px-1)*100,4),
                               "holding_days":i-entry_i,"exit_reason":"stop_gap"})
                units=0.0; pos=False; entry_px=entry_i=entry_date=None
            elif today["low"] <= stop:
                px=stop; cash=units*px
                trades.append({"entry_date":entry_date,"exit_date":today["date"],"entry_price":entry_px,
                               "exit_price":px,"return_pct":round((px/entry_px-1)*100,4),
                               "holding_days":i-entry_i,"exit_reason":"stop_intraday"})
                units=0.0; pos=False; entry_px=entry_i=entry_date=None

        value=cash if not pos else units*today["close"]
        if pos: exposure+=1
        eq.append(value); dates.append(today["date"]); drets.append(value/prev-1); prev=value

        # Decide at today's close for next open.
        r=rr[i]
        if pos:
            if r is not None and r >= EXIT_RATIO:
                pending_exit=True; pending_reason="ratio"
            elif cfg["time"] and i-entry_i >= MAX_HOLD-1:
                pending_exit=True; pending_reason="time"
        else:
            ma_ok=(not cfg["ma"]) or (ma[i] is not None and today["close"] >= ma[i])
            if r is not None and r <= ENTRY_RATIO and ma_ok:
                pending_entry=True

    if pos:
        px=bars[-1]["close"]; cash=units*px
        trades.append({"entry_date":entry_date,"exit_date":bars[-1]["date"],"entry_price":entry_px,
                       "exit_price":px,"return_pct":round((px/entry_px-1)*100,4),
                       "holding_days":len(bars)-1-entry_i,"exit_reason":"forced_end"})
    return summarize(eq,dates,drets,trades,exposure)

def main():
    raw=json.loads(DATA_PATH.read_text(encoding="utf-8"))
    out={"schema":"UPDOWN-INDEX-ABLATION-V1","fixed_signal":{"window":WINDOW,"entry_ratio_lte":round(ENTRY_RATIO,6),
         "exit_ratio_gte":EXIT_RATIO,"execution":"close signal -> next open","universe":SYMBOLS},
         "controls":{"ma":"close >= SMA200 at entry signal","time":f"max {MAX_HOLD} sessions","stop":"5% gap-aware daily OHLC"},
         "results":{}}
    for sym in SYMBOLS:
        bars=load_bars(raw["instruments"][sym]); out["results"][sym]={"name":raw["instruments"][sym].get("name",sym),"configs":{}}
        for name,cfg in CONFIGS.items():
            m=backtest(bars,cfg); out["results"][sym]["configs"][name]=m
            print(sym,name,m,flush=True)
    OUT_PATH.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Wrote",OUT_PATH)

if __name__=="__main__": main()
