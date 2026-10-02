"""Test positive price-vs-up/down-ratio divergence as a DCA entry-heat filter.

Index-only research. Monthly contribution on the first trading day of each month,
using only information available at the prior close. A skipped/halved contribution
remains as cash (0% interest); it is not backfilled later.
"""
from __future__ import annotations

import json, math
from pathlib import Path
from statistics import mean, pstdev
from datetime import date

ROOT=Path(__file__).resolve().parent
DATA_PATH=ROOT/'docs/data/structure_lab.json'
OUT_PATH=ROOT/'docs/data/updown_entry_heat_dca.json'
SYMBOLS=['^GSPC','^IXIC','^DJI']
START='1992-01-02'
END=None
MONTHLY_CONTRIBUTION=1000.0
RATIO_WINDOW=20
Z_WINDOW=60
CORR_WINDOW=60
LAG_LOOKBACK=180
MAX_LEAD=20
THRESHOLDS=[1.0,1.5,2.0]
FORWARD_H=[20,40]


def finite(x):
    try:return x is not None and math.isfinite(float(x))
    except:return False

def pearson(xs,ys):
    p=[(float(a),float(b)) for a,b in zip(xs,ys) if finite(a) and finite(b)]
    if len(p)<8:return None
    x=[a for a,_ in p];y=[b for _,b in p];mx,my=mean(x),mean(y)
    dx=[a-mx for a in x];dy=[b-my for b in y]
    den=math.sqrt(sum(v*v for v in dx)*sum(v*v for v in dy))
    return sum(a*b for a,b in zip(dx,dy))/den if den>0 else None

def z_last(vals):
    v=[float(x) for x in vals if finite(x)]
    if len(v)<20:return None
    sd=pstdev(v)
    return (v[-1]-mean(v))/sd if sd>0 else 0.0

def load_bars(inst):
    out=[]
    for b in inst.get('bars',[]):
        if len(b)<5 or not all(finite(b[j]) for j in (1,2,3,4)):continue
        out.append({'date':str(b[0]),'open':float(b[1]),'high':float(b[2]),'low':float(b[3]),'close':float(b[4])})
    out.sort(key=lambda x:x['date'])
    return out

def features(bars):
    n=len(bars);close=[b['close'] for b in bars];dirs=[None]
    for i in range(1,n):dirs.append(1 if close[i]>close[i-1] else -1 if close[i]<close[i-1] else 0)
    ratio_sig=[None]*n;ratio_raw=[None]*n;ret20=[None]*n;near_high=[False]*n
    for i in range(RATIO_WINDOW,n):
        w=dirs[i-RATIO_WINDOW+1:i+1];up=sum(v==1 for v in w);dn=sum(v==-1 for v in w)
        ratio_raw[i]=math.inf if dn==0 and up else (up/dn if dn else None)
        ratio_sig[i]=math.log((up+.5)/(dn+.5));ret20[i]=close[i]/close[i-RATIO_WINDOW]-1
        tw=close[i-RATIO_WINDOW+1:i+1];near_high[i]=close[i]>=.97*max(tw)
    price_z=[None]*n;ratio_z=[None]*n;div=[None]*n;corr=[None]*n
    for i in range(RATIO_WINDOW+Z_WINDOW-1,n):
        a=max(RATIO_WINDOW,i-Z_WINDOW+1)
        price_z[i]=z_last(ret20[a:i+1]);ratio_z[i]=z_last(ratio_sig[a:i+1])
        if finite(price_z[i]) and finite(ratio_z[i]):div[i]=price_z[i]-ratio_z[i]
        ca=max(RATIO_WINDOW,i-CORR_WINDOW+1);corr[i]=pearson(ret20[ca:i+1],ratio_sig[ca:i+1])
    return {'ratio_sig':ratio_sig,'ratio_raw':ratio_raw,'ret20':ret20,'near_high':near_high,'div':div,'corr':corr}

def best_positive_lead(f,i):
    la=max(RATIO_WINDOW,i-LAG_LOOKBACK+1);best=None
    for k in range(1,MAX_LEAD+1):
        xs=[];ys=[]
        for j in range(la,i-k+1):
            if finite(f['ratio_sig'][j]) and finite(f['ret20'][j+k]):xs.append(f['ratio_sig'][j]);ys.append(f['ret20'][j+k])
        c=pearson(xs,ys)
        if c is not None and (best is None or abs(c)>abs(best[1])):best=(k,c)
    return best

def is_heat(f,i,threshold,mode,lead_cache):
    if i<0:return False
    d=f['div'][i];r=f['ret20'][i]
    base=finite(d) and finite(r) and d>=threshold and r>0 and f['near_high'][i]
    if not base:return False
    if mode=='DIV':return True
    c=f['corr'][i]
    if not finite(c) or c<.25:return False
    if i not in lead_cache:lead_cache[i]=best_positive_lead(f,i)
    best=lead_cache[i]
    return bool(best and best[1]>=.25)

def xirr(flows):
    # flows: [(date_string, cashflow)] negative contributions, positive terminal liquidation.
    if not flows:return None
    d0=date.fromisoformat(flows[0][0]);arr=[((date.fromisoformat(d)-d0).days/365.2425,float(v)) for d,v in flows]
    def npv(r):
        if r<=-0.999999:return float('inf')
        return sum(v/((1+r)**t) for t,v in arr)
    lo,hi=-.9999,10.0
    flo,fhi=npv(lo),npv(hi)
    for _ in range(20):
        if flo*fhi<=0:break
        hi*=2;fhi=npv(hi)
    if flo*fhi>0:return None
    for _ in range(200):
        mid=(lo+hi)/2;fm=npv(mid)
        if abs(fm)<1e-8:return mid
        if flo*fm<=0:hi=mid
        else:lo=mid;flo=fm
    return (lo+hi)/2

def first_trading_days(bars,start):
    out=[];seen=set()
    for i,b in enumerate(bars):
        if b['date']<start:continue
        ym=b['date'][:7]
        if ym not in seen:seen.add(ym);out.append(i)
    return out

def run_strategy(bars,f,monthly_idx,threshold=None,mode='BASE',action='FULL'):
    cash=0.0;shares=0.0;contrib=0.0;flows=[];heat_count=0;half_count=0;skip_count=0;allocated=0.0
    alloc_events=[];lead_cache={};monthly_set=set(monthly_idx)
    twr=1.0;peak=1.0;maxdd=0.0;prev_value=None
    for i,b in enumerate(bars):
        flow=0.0
        if i in monthly_set:
            flow=MONTHLY_CONTRIBUTION;cash+=flow;contrib+=flow;flows.append((b['date'],-flow))
            heat=False
            if mode!='BASE':heat=is_heat(f,i-1,threshold,mode,lead_cache)
            frac=1.0
            if heat:
                heat_count+=1
                if action=='SKIP':frac=0.0;skip_count+=1
                elif action=='HALF':frac=.5;half_count+=1
            buy=flow*frac
            if buy>0:
                px=b['open'];shares+=buy/px;cash-=buy;allocated+=buy
                alloc_events.append((i,buy,heat))
        value=shares*b['close']+cash
        if prev_value is None:
            twr=1.0
        else:
            denom=prev_value+flow
            if denom>0:twr*=value/denom
        peak=max(peak,twr);maxdd=min(maxdd,twr/peak-1)
        prev_value=value
    terminal=shares*bars[-1]['close']+cash;flows.append((bars[-1]['date'],terminal))
    irr=xirr(flows)
    fw={}
    for h in FORWARD_H:
        vals=[];weights=[]
        for i,amt,_ in alloc_events:
            if i+h<len(bars):
                vals.append(bars[i+h]['close']/bars[i]['open']-1);weights.append(amt)
        wavg=sum(v*w for v,w in zip(vals,weights))/sum(weights) if weights else None
        fw[str(h)]={'n':len(vals),'weighted_avg_forward_return_pct':round(wavg*100,3) if wavg is not None else None}
    return {
        'ending_value':round(terminal,2),'total_contributed':round(contrib,2),'cash_ending':round(cash,2),
        'index_allocated_total':round(allocated,2),'allocation_rate_pct':round(100*allocated/contrib,2) if contrib else None,
        'xirr_pct':round(irr*100,3) if irr is not None else None,'twr_total_return_pct':round((twr-1)*100,3),
        'twr_max_drawdown_pct':round(maxdd*100,3),'heat_months':heat_count,'skipped_months':skip_count,'half_months':half_count,
        'forward_entry_quality':fw
    }

def main():
    raw=json.loads(DATA_PATH.read_text(encoding='utf-8'));out={'schema':'UPDOWN-ENTRY-HEAT-DCA-V1','method':{
        'universe':SYMBOLS,'sample_start':START,'monthly_contribution':MONTHLY_CONTRIBUTION,
        'contribution_timing':'first trading day open; heat uses prior close only','cash_interest_pct':0.0,'fees_slippage_pct':0.0,
        'heat_base':'positive divergence + positive 20d return + prior close within 3% of prior 20d high',
        'divergence':'z(20d return over trailing 60)-z(log-smoothed 20d up/down ratio over trailing 60)',
        'DIV':'base heat only','BOTH':'base heat + 60d corr>=0.25 + strongest positive-lag(1..20d) corr over prior 180d >=0.25',
        'actions':['FULL','HALF','SKIP'],'thresholds':THRESHOLDS,'skipped_cash':'remains cash permanently; no later backfill',
        'max_drawdown':'drawdown of contribution-adjusted time-weighted portfolio index'
    },'results':{}}
    for sym in SYMBOLS:
        inst=raw.get('instruments',{}).get(sym)
        if not inst:continue
        bars=load_bars(inst);bars=[b for b in bars if b['date']>=START and (END is None or b['date']<=END)]
        # retain pre-start history is ideal for features, so reload all then subset via monthly dates on all bars
        allbars=load_bars(inst);f=features(allbars);monthly=first_trading_days(allbars,START)
        if END:monthly=[i for i in monthly if allbars[i]['date']<=END]
        result={'name':inst.get('name',sym),'start':allbars[monthly[0]]['date'],'end':allbars[-1]['date'],'months':len(monthly),'baseline':run_strategy(allbars,f,monthly),'tests':{}}
        base=result['baseline']['ending_value']
        for th in THRESHOLDS:
            for mode in ('DIV','BOTH'):
                for action in ('HALF','SKIP'):
                    k=f'{mode}_{action}_{th:.1f}';r=run_strategy(allbars,f,monthly,th,mode,action)
                    r['ending_value_vs_baseline_pct']=round((r['ending_value']/base-1)*100,3)
                    result['tests'][k]=r
        out['results'][sym]=result
        print('\n',sym,result['name'],'BASE',result['baseline'],flush=True)
        for k in ['DIV_HALF_1.5','DIV_SKIP_1.5','BOTH_HALF_1.5','BOTH_SKIP_1.5']:
            print(sym,k,result['tests'][k],flush=True)
    OUT_PATH.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print('Wrote',OUT_PATH)
if __name__=='__main__':main()
