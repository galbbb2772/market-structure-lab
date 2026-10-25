"""Shared feature helpers for the Entry Heat Extra Gate research line.

The standalone Entry Heat DCA strategy and its results remain in the central rejected archive.
This module intentionally contains reusable calculations only; it is not a strategy entry point.
"""
from __future__ import annotations

import math
from datetime import date
from statistics import mean, pstdev

RATIO_WINDOW = 20
Z_WINDOW = 60
CORR_WINDOW = 60
LAG_LOOKBACK = 180
MAX_LEAD = 20

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
