"""Index-only short V2: 20-day up/down ratio >= 5.5 to short, <= 1.2 to cover, 10% stop."""
from __future__ import annotations
import json, math
from datetime import date
from pathlib import Path
from statistics import mean, pstdev

ROOT=Path(__file__).resolve().parent
DATA_PATH=ROOT/'docs/data/structure_lab.json'
OUT_PATH=ROOT/'docs/data/updown_short_v2.json'
SYMBOLS=['^GSPC','^IXIC','^DJI']
WINDOW=20
ENTRY_RATIO=5.5
EXIT_RATIO=1.2
STOP_PCT=0.10

def finite(x):
    try:return x is not None and math.isfinite(float(x))
    except (TypeError,ValueError):return False

def load_bars(obj):
    out=[]
    for b in obj.get('bars',[]):
        if len(b)<5 or not all(finite(b[j]) for j in (1,2,3,4)):continue
        out.append({'date':str(b[0]),'open':float(b[1]),'high':float(b[2]),'low':float(b[3]),'close':float(b[4])})
    out.sort(key=lambda x:x['date'])
    return out

def rolling_ratio(bars):
    dirs=[None]
    for i in range(1,len(bars)):
        a,b=bars[i-1]['close'],bars[i]['close']
        dirs.append(1 if b>a else -1 if b<a else 0)
    ratios=[None]*len(bars)
    for i in range(WINDOW,len(bars)):
        w=dirs[i-WINDOW+1:i+1]
        up=sum(x==1 for x in w); dn=sum(x==-1 for x in w)
        ratios[i]=math.inf if dn==0 and up else (up/dn if dn else None)
    return ratios

def years_between(a,b):
    return max((date.fromisoformat(b)-date.fromisoformat(a)).days/365.2425,1/365.2425)

def max_drawdown(eq):
    peak=0.0; worst=0.0
    for v in eq:
        peak=max(peak,v)
        if peak>0: worst=min(worst,v/peak-1.0)
    return worst

def summarize(eq,dates,daily,trades,exposure):
    total=eq[-1]/eq[0]-1 if eq else 0.0
    yrs=years_between(dates[0],dates[-1]) if len(dates)>1 else 0
    cagr=(eq[-1]/eq[0])**(1/yrs)-1 if yrs>0 and eq[-1]>0 and eq[0]>0 else None
    sd=pstdev(daily) if len(daily)>1 else 0
    sh=mean(daily)/sd*math.sqrt(252) if sd>0 else None
    rets=[t['return_pct']/100 for t in trades]; maes=[t['mae_pct'] for t in trades]
    wins=sum(r>0 for r in rets); holds=sorted(t['holding_days'] for t in trades)
    reasons={}
    for t in trades:reasons[t['exit_reason']]=reasons.get(t['exit_reason'],0)+1
    return {
        'total_return_pct':round(total*100,3),'cagr_pct':round(cagr*100,3) if cagr is not None else None,
        'max_drawdown_pct':round(max_drawdown(eq)*100,3),'sharpe':round(sh,3) if sh is not None else None,
        'trades':len(trades),'win_rate_pct':round(wins/len(trades)*100,2) if trades else None,
        'avg_trade_pct':round(mean(rets)*100,3) if rets else None,
        'median_holding_days':holds[len(holds)//2] if holds else None,
        'exposure_pct':round(exposure/len(dates)*100,2) if dates else 0.0,
        'avg_mae_pct':round(mean(maes),3) if maes else None,'worst_mae_pct':round(max(maes),3) if maes else None,
        'exit_reasons':reasons,'terminal_equity':round(eq[-1],6) if eq else None,'blown_up':any(v<=0 for v in eq)
    }

def close_trade(trades,entry_date,entry_price,entry_equity,entry_idx,exit_date,exit_price,exit_idx,max_high,reason):
    units=entry_equity/entry_price
    exit_equity=entry_equity+units*(entry_price-exit_price)
    trades.append({'entry_date':entry_date,'exit_date':exit_date,'entry_price':round(entry_price,6),'exit_price':round(exit_price,6),
                   'return_pct':round((exit_equity/entry_equity-1)*100,4),'holding_days':exit_idx-entry_idx,
                   'mae_pct':round((max_high/entry_price-1)*100,4),'exit_reason':reason})
    return exit_equity

def backtest(bars):
    ratios=rolling_ratio(bars); start=WINDOW+1
    cash=1.0; pos=False; entry_price=entry_equity=entry_date=entry_idx=max_high=None
    pending_entry=False; pending_exit=False
    eq=[]; dates=[]; daily=[]; trades=[]; exposure=0; prev_eq=1.0
    for i in range(start,len(bars)):
        b=bars[i]; op,hi,cl=b['open'],b['high'],b['close']
        stopped_today=False
        if pos and pending_exit:
            cash=close_trade(trades,entry_date,entry_price,entry_equity,entry_idx,b['date'],op,i,max_high,'ratio')
            pos=False; entry_price=entry_equity=entry_date=entry_idx=max_high=None; pending_exit=False
        if (not pos) and pending_entry:
            entry_equity=cash; entry_price=op; entry_date=b['date']; entry_idx=i; max_high=hi; pos=True; pending_entry=False
        if pos:
            max_high=max(max_high,hi)
            stop_price=entry_price*(1+STOP_PCT)
            if op>=stop_price:
                exit_price=op; reason='stop_gap'
            elif hi>=stop_price:
                exit_price=stop_price; reason='stop_intraday'
            else:
                exit_price=None; reason=None
            if exit_price is not None:
                cash=close_trade(trades,entry_date,entry_price,entry_equity,entry_idx,b['date'],exit_price,i,max_high,reason)
                pos=False; entry_price=entry_equity=entry_date=entry_idx=max_high=None; pending_exit=False; stopped_today=True
        if pos:
            units=entry_equity/entry_price
            value=entry_equity+units*(entry_price-cl); exposure+=1
        else:value=cash
        eq.append(value); dates.append(b['date']); daily.append(value/prev_eq-1 if prev_eq else 0.0); prev_eq=value
        r=ratios[i]
        if pos:
            if r is not None and r<=EXIT_RATIO: pending_exit=True
        elif (not stopped_today) and r is not None and r>=ENTRY_RATIO:
            pending_entry=True
    if pos:
        f=bars[-1]
        cash=close_trade(trades,entry_date,entry_price,entry_equity,entry_idx,f['date'],f['close'],len(bars)-1,max_high,'forced_end')
        eq[-1]=cash
    last=ratios[-1]
    return {'start':bars[start]['date'],'end':bars[-1]['date'],'bars':len(eq),
            'last_ratio':None if last is None else ('inf' if math.isinf(last) else round(last,4)),
            'current_close_signal':'SHORT' if pos or pending_entry else 'CASH',
            'strategy':summarize(eq,dates,daily,trades,exposure),'recent_trades':trades[-20:]}

def main():
    raw=json.loads(DATA_PATH.read_text(encoding='utf-8'))
    out={'schema':'UPDOWN-SHORT-V2','rules':{'universe':SYMBOLS,'window':WINDOW,'entry_ratio_gte':ENTRY_RATIO,'exit_ratio_lte':EXIT_RATIO,
         'execution':'signal at close t; execute at open t+1; 10% short stop is gap-aware with daily OHLC',
         'side':'short_or_cash_only','notional':'1x equity at entry','stop_loss_pct':STOP_PCT*100,'max_holding':None,
         'fees_borrow_slippage':0.0,'note':'Fixed Short V2 before reviewing results. No stock selection.'},'results':{}}
    for sym in SYMBOLS:
        inst=raw.get('instruments',{}).get(sym)
        if not inst: out['results'][sym]={'error':'missing instrument'}; continue
        res=backtest(load_bars(inst)); res['name']=inst.get('name',sym); out['results'][sym]=res
        print(sym,res['strategy'],flush=True)
    OUT_PATH.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Wrote',OUT_PATH)
if __name__=='__main__':main()
