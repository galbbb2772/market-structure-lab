"""Event study for index price-vs-up/down-ratio divergence.

Tests whether the 20-session up/down ratio tends to lead index direction when
price remains strong/weak but the internal ratio has diverged. Signal construction
uses only information available at close t; forward data are evaluation only.
"""
from __future__ import annotations
import json, math
from pathlib import Path
from statistics import mean, median, pstdev

ROOT=Path(__file__).resolve().parent
DATA_PATH=ROOT/'docs/data/structure_lab.json'
OUT_PATH=ROOT/'docs/data/updown_divergence_event_study.json'
SYMBOLS=['^GSPC','^IXIC','^DJI']
RATIO_WINDOW=20; Z_WINDOW=60; CORR_WINDOW=60; LAG_LOOKBACK=180; MAX_LEAD=20
HORIZONS=[5,10,20,40]; THRESHOLDS=[1.0,1.5,2.0]; COOLDOWN=20


def finite(x):
    try:return x is not None and math.isfinite(float(x))
    except (TypeError,ValueError):return False


def load_bars(obj):
    out=[]
    for b in obj.get('bars',[]):
        if len(b)<5 or not all(finite(b[j]) for j in (1,2,3,4)):continue
        out.append({'date':str(b[0]),'open':float(b[1]),'high':float(b[2]),'low':float(b[3]),'close':float(b[4])})
    out.sort(key=lambda x:x['date']); return out


def pearson(xs,ys):
    p=[(float(a),float(b)) for a,b in zip(xs,ys) if finite(a) and finite(b)]
    if len(p)<8:return None
    mx=mean(a for a,_ in p); my=mean(b for _,b in p)
    sxx=sum((a-mx)**2 for a,_ in p); syy=sum((b-my)**2 for _,b in p)
    if sxx<=0 or syy<=0:return None
    return sum((a-mx)*(b-my) for a,b in p)/math.sqrt(sxx*syy)


def z_last(vals):
    v=[float(x) for x in vals if finite(x)]
    if len(v)<20:return None
    sd=pstdev(v); return (v[-1]-mean(v))/sd if sd>0 else 0.0


def features(bars):
    n=len(bars); close=[b['close'] for b in bars]
    dirs=[None]+[1 if close[i]>close[i-1] else -1 if close[i]<close[i-1] else 0 for i in range(1,n)]
    ratio=[None]*n; ratio_sig=[None]*n; ret20=[None]*n; near_high=[False]*n; near_low=[False]*n
    for i in range(RATIO_WINDOW,n):
        w=dirs[i-RATIO_WINDOW+1:i+1]; up=sum(v==1 for v in w); dn=sum(v==-1 for v in w)
        ratio[i]=math.inf if dn==0 and up else (up/dn if dn else None)
        ratio_sig[i]=math.log((up+0.5)/(dn+0.5))
        ret20[i]=close[i]/close[i-RATIO_WINDOW]-1
        tr=close[i-RATIO_WINDOW+1:i+1]
        near_high[i]=close[i]>=0.97*max(tr); near_low[i]=close[i]<=1.03*min(tr)
    price_z=[None]*n; ratio_z=[None]*n; div=[None]*n; corr=[None]*n
    for i in range(RATIO_WINDOW+Z_WINDOW-1,n):
        a=max(RATIO_WINDOW,i-Z_WINDOW+1)
        price_z[i]=z_last(ret20[a:i+1]); ratio_z[i]=z_last(ratio_sig[a:i+1])
        if finite(price_z[i]) and finite(ratio_z[i]):div[i]=price_z[i]-ratio_z[i]
        ca=max(RATIO_WINDOW,i-CORR_WINDOW+1)
        corr[i]=pearson(ret20[ca:i+1],ratio_sig[ca:i+1])
    return {'ratio':ratio,'ratio_sig':ratio_sig,'ret20':ret20,'price_z':price_z,'ratio_z':ratio_z,'div':div,'corr':corr,
            'best_lead':[None]*n,'best_lead_corr':[None]*n,'lead_done':[False]*n,'near_high':near_high,'near_low':near_low}


def ensure_best_lead(f,i):
    if f['lead_done'][i]:return f['best_lead'][i],f['best_lead_corr'][i]
    la=max(RATIO_WINDOW,i-LAG_LOOKBACK+1); best=None
    for k in range(1,MAX_LEAD+1):
        xs=[]; ys=[]
        for j in range(la,i-k+1):
            if finite(f['ratio_sig'][j]) and finite(f['ret20'][j+k]):
                xs.append(f['ratio_sig'][j]); ys.append(f['ret20'][j+k])
        c=pearson(xs,ys)
        if c is not None and (best is None or abs(c)>abs(best[1])):best=(k,c)
    if best:f['best_lead'][i],f['best_lead_corr'][i]=best
    f['lead_done'][i]=True
    return f['best_lead'][i],f['best_lead_corr'][i]


def forward_stats(bars,indices,side):
    out={}
    for h in HORIZONS:
        vals=[]; adverse=[]; favorable=[]
        for i in indices:
            if i+h>=len(bars):continue
            base=bars[i]['close']; path=bars[i+1:i+h+1]; vals.append(bars[i+h]['close']/base-1)
            if side=='bear':
                adverse.append(max(b['high'] for b in path)/base-1); favorable.append(min(b['low'] for b in path)/base-1)
            else:
                adverse.append(min(b['low'] for b in path)/base-1); favorable.append(max(b['high'] for b in path)/base-1)
        if not vals:out[str(h)]={'n':0};continue
        hit=sum((r<0 if side=='bear' else r>0) for r in vals)/len(vals)
        out[str(h)]={'n':len(vals),'avg_return_pct':round(mean(vals)*100,3),'median_return_pct':round(median(vals)*100,3),
                     'direction_hit_rate_pct':round(hit*100,2),'avg_adverse_excursion_pct':round(mean(adverse)*100,3),
                     'avg_favorable_excursion_pct':round(mean(favorable)*100,3)}
    return out


def baseline_stats(bars,start_idx=0):
    out={}; idx=range(start_idx,len(bars)-max(HORIZONS))
    for h in HORIZONS:
        vals=[bars[i+h]['close']/bars[i]['close']-1 for i in idx if i+h<len(bars)]
        out[str(h)]={'n':len(vals),'avg_return_pct':round(mean(vals)*100,3),'median_return_pct':round(median(vals)*100,3),
                     'up_rate_pct':round(sum(r>0 for r in vals)/len(vals)*100,2)} if vals else {'n':0}
    return out


def extract_events(bars,f,side,threshold,require_corr=False,require_lead=False,start_date=None):
    idx=[]; last=-10**9
    for i,b in enumerate(bars):
        if start_date and b['date']<start_date:continue
        if i-last<COOLDOWN:continue
        d=f['div'][i]; r20=f['ret20'][i]; c=f['corr'][i]
        if not finite(d) or not finite(r20):continue
        ok=(d>=threshold and r20>0 and f['near_high'][i]) if side=='bear' else (d<=-threshold and r20<0 and f['near_low'][i])
        if not ok:continue
        if require_corr and not (finite(c) and c>=0.25):continue
        if require_lead:
            lag,lc=ensure_best_lead(f,i)
            if not (lag and finite(lc) and lc>=0.25):continue
        idx.append(i); last=i
    return idx


def sample_events(bars,f,idx):
    rows=[]
    for i in idx[-12:]:
        lag,lc=ensure_best_lead(f,i)
        rr=f['ratio'][i]
        rows.append({'date':bars[i]['date'],'close':round(bars[i]['close'],4),'divergence':round(f['div'][i],3) if finite(f['div'][i]) else None,
                     'ret20_pct':round(f['ret20'][i]*100,3) if finite(f['ret20'][i]) else None,
                     'ratio':'inf' if rr is not None and math.isinf(rr) else round(rr,4) if finite(rr) else None,
                     'rolling_corr':round(f['corr'][i],3) if finite(f['corr'][i]) else None,
                     'best_ratio_lead_days':lag,'best_ratio_lead_corr':round(lc,3) if finite(lc) else None})
    return rows


def study_period(bars,f,start_date=None):
    configs={}
    for side in ('bear','bull'):
        for th in THRESHOLDS:
            for tag,rc,rl in [('DIV',False,False),('DIV_CORR',True,False),('DIV_LEAD',False,True),('DIV_BOTH',True,True)]:
                name=f'{side.upper()}_{tag}_{th:.1f}'; idx=extract_events(bars,f,side,th,rc,rl,start_date)
                configs[name]={'side':side,'threshold':th,'require_corr_gte':0.25 if rc else None,
                               'require_positive_ratio_lead_corr_gte':0.25 if rl else None,'events':len(idx),
                               'forward':forward_stats(bars,idx,side),'recent_events':sample_events(bars,f,idx)}
    start_idx=next((i for i,b in enumerate(bars) if not start_date or b['date']>=start_date),0)
    return {'baseline':baseline_stats(bars,start_idx),'configs':configs}


def main():
    raw=json.loads(DATA_PATH.read_text(encoding='utf-8'))
    out={'schema':'UPDOWN-DIVERGENCE-EVENT-STUDY-V1','method':{
        'universe':SYMBOLS,'ratio_window':RATIO_WINDOW,'z_window':Z_WINDOW,'rolling_corr_window':CORR_WINDOW,
        'lag_lookback':LAG_LOOKBACK,'tested_positive_ratio_lead_days':[1,MAX_LEAD],'forward_horizons':HORIZONS,
        'divergence':'z(20d index return over trailing 60) - z(log-smoothed 20d up/down ratio over trailing 60)',
        'bear_event':'positive divergence + positive 20d return + close within 3% of trailing 20d high',
        'bull_event':'negative divergence + negative 20d return + close within 3% of trailing 20d low',
        'corr_filter':'60-period contemporaneous corr >= 0.25',
        'lead_filter':'strongest absolute positive-lag corr over prior 180 periods is positive and >=0.25; positive lag means ratio leads future 20d return',
        'cooldown_trading_days':COOLDOWN,'lookahead':'none in signal construction; future data only for event evaluation'},'results':{}}
    for sym in SYMBOLS:
        inst=raw.get('instruments',{}).get(sym)
        if not inst:out['results'][sym]={'error':'missing'};continue
        bars=load_bars(inst); f=features(bars)
        out['results'][sym]={'name':inst.get('name',sym),'start':bars[0]['date'],'end':bars[-1]['date'],
                             'full_history':study_period(bars,f,None),'common_1992_plus':study_period(bars,f,'1992-01-02')}
        for k in ['BEAR_DIV_1.5','BEAR_DIV_CORR_1.5','BEAR_DIV_LEAD_1.5','BEAR_DIV_BOTH_1.5','BULL_DIV_1.5','BULL_DIV_BOTH_1.5']:
            c=out['results'][sym]['common_1992_plus']['configs'][k]; print(sym,k,c['events'],c['forward'],flush=True)
    OUT_PATH.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8'); print('Wrote',OUT_PATH)

if __name__=='__main__':main()
