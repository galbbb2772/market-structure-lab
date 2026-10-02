"""Clean ablation study for the index-only up/down-ratio strategy.

All variants use the SAME sample start and SAME execution engine. Only three
controls are toggled: SMA200 entry filter, 10-session max hold, and 5% stop.
Universe is strictly ^GSPC, ^IXIC, ^DJI; no stocks.
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
WINDOW, MA_WINDOW, MAX_HOLD = 20, 200, 10
ENTRY_RATIO, EXIT_RATIO, STOP_PCT = 2/3, 1.0, 0.05
CONFIGS = {
    "BASE":      {"ma":False,"time":False,"stop":False},
    "MA_ONLY":   {"ma":True, "time":False,"stop":False},
    "TIME_ONLY": {"ma":False,"time":True, "stop":False},
    "STOP_ONLY": {"ma":False,"time":False,"stop":True},
    "MA_TIME":   {"ma":True, "time":True, "stop":False},
    "MA_STOP":   {"ma":True, "time":False,"stop":True},
    "TIME_STOP": {"ma":False,"time":True, "stop":True},
    "ALL_V2":    {"ma":True, "time":True, "stop":True},
}

def finite(x):
    try: return x is not None and math.isfinite(float(x))
    except (TypeError, ValueError): return False

def load_bars(obj):
    out=[]
    for b in obj.get("bars",[]):
        if len(b)<5 or not all(finite(b[j]) for j in (1,2,3,4)): continue
        out.append({"date":str(b[0]),"open":float(b[1]),"high":float(b[2]),"low":float(b[3]),"close":float(b[4])})
    out.sort(key=lambda x:x["date"])
    return out

def rolling_ratio(bars):
    dirs=[None]
    for i in range(1,len(bars)):
        a,b=bars[i-1]["close"],bars[i]["close"]
        dirs.append(1 if b>a else -1 if b<a else 0)
    out=[None]*len(bars)
    for i in range(WINDOW,len(bars)):
        w=dirs[i-WINDOW+1:i+1]; up=sum(x==1 for x in w); dn=sum(x==-1 for x in w)
        out[i]=math.inf if dn==0 and up else (up/dn if dn else None)
    return out

def sma200(bars):
    out=[None]*len(bars); acc=0.0
    for i,b in enumerate(bars):
        acc+=b["close"]
        if i>=MA_WINDOW: acc-=bars[i-MA_WINDOW]["close"]
        if i>=MA_WINDOW-1: out[i]=acc/MA_WINDOW
    return out

def years(a,b): return max((date.fromisoformat(b)-date.fromisoformat(a)).days/365.2425,1/365.2425)
def maxdd(eq):
    peak=0.0; worst=0.0
    for v in eq:
        peak=max(peak,v)
        if peak>0: worst=min(worst,v/peak-1)
    return worst

def summarize(eq,dates,drets,trades,exposure):
    total=eq[-1]/eq[0]-1 if eq else 0.0; yrs=years(dates[0],dates[-1])
    cagr=(eq[-1]/eq[0])**(1/yrs)-1 if yrs>0 else 0.0
    sd=pstdev(drets) if len(drets)>1 else 0.0; sh=mean(drets)/sd*math.sqrt(252) if sd>0 else None
    rs=[t["return_pct"]/100 for t in trades]; wins=sum(x>0 for x in rs); reasons={}
    for t in trades: reasons[t["exit_reason"]]=reasons.get(t["exit_reason"],0)+1
    holds=sorted(t["holding_days"] for t in trades)
    return {"total_return_pct":round(total*100,3),"cagr_pct":round(cagr*100,3),
            "max_drawdown_pct":round(maxdd(eq)*100,3),"sharpe":round(sh,3) if sh is not None else None,
            "trades":len(trades),"win_rate_pct":round(wins/len(trades)*100,2) if trades else None,
            "avg_trade_pct":round(mean(rs)*100,3) if rs else None,
            "median_holding_days":holds[len(holds)//2] if holds else None,
            "exposure_pct":round(exposure/len(dates)*100,2),"exit_reasons":reasons}

def add_trade(trades,entry_date,entry_px,entry_i,exit_date,exit_px,exit_i,reason):
    trades.append({"entry_date":entry_date,"exit_date":exit_date,"entry_price":entry_px,"exit_price":exit_px,
                   "return_pct":round((exit_px/entry_px-1)*100,4),"holding_days":max(0,exit_i-entry_i),"exit_reason":reason})

def backtest(bars,cfg):
    rr=rolling_ratio(bars); ma=sma200(bars)
    # COMMON start for every variant: exactly the V2 start, after SMA200 is available.
    start=(MA_WINDOW-1)+1
    cash=1.0; units=0.0; pos=False
    entry_px=entry_date=entry_i=None; pending_entry=False; pending_exit=False; pending_reason=None
    eq=[]; dates=[]; drets=[]; trades=[]; exposure=0; prev_eq=1.0

    for i in range(start,len(bars)):
        b=bars[i]; op,lo,cl=b["open"],b["low"],b["close"]

        if pos and pending_exit:
            cash=units*op; add_trade(trades,entry_date,entry_px,entry_i,b["date"],op,i,pending_reason)
            units=0.0; pos=False; entry_px=entry_date=entry_i=None
        pending_exit=False; pending_reason=None

        if (not pos) and pending_entry:
            units=cash/op; cash=0.0; pos=True; entry_px=op; entry_date=b["date"]; entry_i=i
        pending_entry=False

        stopped_today=False
        if pos and cfg["stop"]:
            stop=entry_px*(1-STOP_PCT); exit_px=None; reason=None
            if op<=stop: exit_px=op; reason="stop_gap"
            elif lo<=stop: exit_px=stop; reason="stop_intraday"
            if exit_px is not None:
                cash=units*exit_px; add_trade(trades,entry_date,entry_px,entry_i,b["date"],exit_px,i,reason)
                units=0.0; pos=False; entry_px=entry_date=entry_i=None; pending_exit=False; stopped_today=True

        value=cash if not pos else units*cl
        if pos: exposure+=1
        eq.append(value); dates.append(b["date"]); drets.append(value/prev_eq-1); prev_eq=value

        r=rr[i]
        if not pos:
            ma_ok=(not cfg["ma"]) or (ma[i] is not None and cl>=ma[i])
            # Match V2: a stop-out cannot create another entry signal on the same close.
            if (not stopped_today) and r is not None and r<=ENTRY_RATIO and ma_ok: pending_entry=True
        else:
            ratio_exit=(r is not None and r>=EXIT_RATIO)
            held=i-entry_i+1
            time_exit=cfg["time"] and held>=MAX_HOLD
            if ratio_exit or time_exit:
                pending_exit=True
                pending_reason="ratio" if ratio_exit else "time"

    if pos:
        px=bars[-1]["close"]
        add_trade(trades,entry_date,entry_px,entry_i,bars[-1]["date"],px,len(bars)-1,"forced_end")
        if eq: eq[-1]=units*px
    return {"start":bars[start]["date"],"end":bars[-1]["date"],"metrics":summarize(eq,dates,drets,trades,exposure)}

def main():
    raw=json.loads(DATA_PATH.read_text(encoding="utf-8"))
    out={"schema":"UPDOWN-INDEX-ABLATION-V2","fixed_signal":{"window":WINDOW,"entry_ratio_lte":round(ENTRY_RATIO,6),
         "exit_ratio_gte":EXIT_RATIO,"execution":"close signal -> next open","universe":SYMBOLS,
         "common_start":"first session after SMA200 becomes available for every variant"},
         "controls":{"ma":"close >= SMA200 at entry signal","time":"max 10 held sessions; exit next open",
                     "stop":"5% gap-aware daily OHLC; no same-close re-entry after stop"},"results":{}}
    for sym in SYMBOLS:
        bars=load_bars(raw["instruments"][sym]); node={"name":raw["instruments"][sym].get("name",sym),"configs":{}}
        for name,cfg in CONFIGS.items():
            res=backtest(bars,cfg); node["configs"][name]=res; print(sym,name,res["metrics"],flush=True)
        out["results"][sym]=node
    OUT_PATH.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Wrote",OUT_PATH)

if __name__=="__main__": main()
