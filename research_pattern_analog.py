from __future__ import annotations
import json, math, statistics
from pathlib import Path

SRC=Path('docs/data/structure_lab.json')
OUT=Path('docs/data/analog_latest.json')
SYMS=['^GSPC','^IXIC','^DJI']
H=(1,3,5,10)
FEATURES=[('streak',2.0,2.0),('r1',1.0,2.0),('r3',1.0,4.0),('r5',1.0,6.0),('rsi',1.0,15.0),('atr_rank',.8,25.0),('vol_ratio',.4,.8),('ma20_dist',1.0,5.0),('pos60',.8,25.0),('market5',1.0,6.0)]

def q(a,p):
    s=sorted(float(x) for x in a if x is not None and math.isfinite(float(x)))
    if not s:return None
    z=(len(s)-1)*p;i=int(z);f=z-i
    return s[i]+(s[min(i+1,len(s)-1)]-s[i])*f

def avg(a):
    s=[float(x) for x in a if x is not None and math.isfinite(float(x))]
    return statistics.fmean(s) if s else None

def rows(bars,market5):
    n=len(bars);cl=[float(b[4]) for b in bars];vol=[float(b[5] or 0) for b in bars]
    pref=[0.0];vp=[0.0]
    for x,v in zip(cl,vol):pref.append(pref[-1]+x);vp.append(vp[-1]+v)
    streak=[0]*n;tr=[None]*n;atr=[None]*n;rsi=[None]*n
    for i in range(1,n):
        d=1 if cl[i]>cl[i-1] else -1 if cl[i]<cl[i-1] else 0
        streak[i]=0 if d==0 else (streak[i-1]+d if streak[i-1] and (1 if streak[i-1]>0 else -1)==d else d)
        tr[i]=max(float(bars[i][2])-float(bars[i][3]),abs(float(bars[i][2])-cl[i-1]),abs(float(bars[i][3])-cl[i-1]))
    gains=losses=0.0
    for i in range(1,n):
        d=cl[i]-cl[i-1];gains+=max(d,0);losses+=max(-d,0)
        if i>14:
            old=cl[i-14]-cl[i-15];gains-=max(old,0);losses-=max(-old,0)
        if i>=14:
            ag,al=gains/14,losses/14;rsi[i]=100 if al==0 else 100-100/(1+ag/al)
    tsum=0.0
    for i in range(1,n):
        tsum+=tr[i] or 0
        if i>14:tsum-=tr[i-14] or 0
        if i>=14:atr[i]=100*(tsum/14)/cl[i]
    out=[]
    for i in range(252,n):
        ma20=(pref[i+1]-pref[i-19])/20;ma200=(pref[i+1]-pref[i-199])/200
        seg=bars[i-59:i+1];lo=min(float(b[3]) for b in seg);hi=max(float(b[2]) for b in seg)
        ah=[x for x in atr[max(14,i-251):i+1] if x is not None];ar=atr[i];rank=100*sum(x<=ar for x in ah)/len(ah) if ah else None
        av=(vp[i]-vp[max(0,i-20)])/min(20,i);vr=vol[i]/av if av>0 else None
        out.append(dict(idx=i,date=bars[i][0],streak=streak[i],r1=100*(cl[i]/cl[i-1]-1),r3=100*(cl[i]/cl[i-3]-1),r5=100*(cl[i]/cl[i-5]-1),rsi=rsi[i],atr_rank=rank,vol_ratio=vr,ma20_dist=100*(cl[i]/ma20-1),pos60=100*(cl[i]-lo)/(hi-lo) if hi>lo else 50,market5=market5.get(bars[i][0]),regime='above200' if cl[i]>=ma200 else 'below200',close=cl[i]))
    return out

def dist(a,b):
    s=w=0.0
    for k,wt,scale in FEATURES:
        x,y=a.get(k),b.get(k)
        if x is None or y is None:continue
        d=(float(x)-float(y))/scale;s+=wt*d*d;w+=wt
    return math.sqrt(s/w) if w else math.inf

def outcome(bars,row,h):
    i=row['idx'];base=float(bars[i][4]);future=bars[i+1:i+h+1]
    return dict(ret=100*(float(bars[i+h][4])/base-1),mfe=100*(max(float(b[2]) for b in future)/base-1),mae=100*(min(float(b[3]) for b in future)/base-1))

def summary(bars,rs,h):
    o=[outcome(bars,r,h) for r in rs];rets=[x['ret'] for x in o]
    return dict(n=len(rets),up_pct=100*sum(x>0 for x in rets)/len(rets) if rets else None,mean=avg(rets),p10=q(rets,.1),p25=q(rets,.25),median=q(rets,.5),p75=q(rets,.75),p90=q(rets,.9),avg_mfe=avg([x['mfe'] for x in o]),avg_mae=avg([x['mae'] for x in o]))

def main():
    data=json.loads(SRC.read_text())
    sp=data['instruments']['^GSPC']['bars'];market5={sp[i][0]:100*(float(sp[i][4])/float(sp[i-5][4])-1) for i in range(5,len(sp))}
    result={'schema':'ANALOG-LATEST-V1','settings':{'top_k':40,'streak_tolerance':1,'same_direction':True,'same_ma200_regime':True,'decluster_sessions':5},'instruments':{}}
    for sym in SYMS:
        inst=data['instruments'][sym];bars=inst['bars'];rr=rows(bars,market5);target=rr[-1]
        cand=[r for r in rr if r['idx']+10<target['idx'] and r['streak'] and target['streak'] and (1 if r['streak']>0 else -1)==(1 if target['streak']>0 else -1) and abs(abs(r['streak'])-abs(target['streak']))<=1 and r['regime']==target['regime']]
        cand=sorted((dict(r,distance=dist(target,r)) for r in cand),key=lambda x:x['distance'])
        sel=[]
        for r in cand:
            if any(abs(r['idx']-x['idx'])<5 for x in sel):continue
            r['similarity']=100/(1+r['distance']);sel.append(r)
            if len(sel)>=40:break
        exact=[r for r in rr if r['idx']+10<target['idx'] and r['streak']==target['streak']]
        result['instruments'][sym]={'name':inst['name'],'target':target,'candidate_pool':len(cand),'matches':len(sel),'analog':{str(h):summary(bars,sel,h) for h in H},'exact_streak':{str(h):summary(bars,exact,h) for h in H},'top_matches':[{k:r[k] for k in ('date','similarity','streak','r1','r3','r5','rsi','atr_rank','ma20_dist','pos60')}|{'forward':{str(h):outcome(bars,r,h)['ret'] for h in H}} for r in sel[:10]]}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
