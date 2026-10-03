"""Continuous Market State × Box V2 research engine.

V2 keeps Box as the structural requirement, while sentiment, three-index breadth
and Market Score remain continuous state variables. No V1-style hard gates are
used. Walk-forward validation only uses earlier neighbors whose forward outcomes
were already known before each target date.
"""
from __future__ import annotations
import json, math
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

ROOT=Path(__file__).resolve().parent
SRC=ROOT/'docs/data/market_state_box_v1.json'
OUT=ROOT/'docs/data/market_state_box_v2.json'
H=(3,5,10); KS=(20,40,80)
F=('box_state','sentiment_level','sentiment_velocity','breadth_level','breadth_velocity','score_level','score_d1_rank','score_d3_rank')

def num(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except (TypeError,ValueError): return None

def q(a,p):
    a=sorted(x for x in (num(v) for v in a) if x is not None)
    if not a:return None
    z=(len(a)-1)*p;i=int(z);j=min(i+1,len(a)-1);f=z-i
    return a[i]+(a[j]-a[i])*f

def pct_hist(vals,min_n=60):
    seen=[];out=[]
    for v in vals:
        v=num(v)
        if v is None:out.append(None);continue
        seen.append(v)
        out.append(None if len(seen)<min_n else 100*sum(x<=v for x in seen)/len(seen))
    return out

def lag(rows,key,n):
    out=[]
    for i,r in enumerate(rows):
        a=num(r.get(key));b=num(rows[i-n].get(key)) if i>=n else None
        out.append(a-b if a is not None and b is not None else None)
    return out

def ranks(vals):
    pairs=sorted((num(v),i) for i,v in enumerate(vals) if num(v) is not None);out=[None]*len(vals);k=0
    while k<len(pairs):
        j=k+1
        while j<len(pairs) and pairs[j][0]==pairs[k][0]:j+=1
        r=((k+j-1)/2)/max(1,len(pairs)-1)
        for _,i in pairs[k:j]:out[i]=r
        k=j
    return out

def pearson(a,b):
    p=[(num(x),num(y)) for x,y in zip(a,b)];p=[z for z in p if None not in z]
    if len(p)<3:return None
    x,y=zip(*p);mx,my=mean(x),mean(y);dx=math.sqrt(sum((v-mx)**2 for v in x));dy=math.sqrt(sum((v-my)**2 for v in y))
    return sum((u-mx)*(v-my) for u,v in p)/(dx*dy) if dx and dy else None

def spearman(a,b):return pearson(ranks(a),ranks(b))

def vec(r):
    v=[num(r.get(k)) for k in F];return v if all(x is not None for x in v) else None

def dist(a,b):
    x,y=vec(a),vec(b)
    return None if x is None or y is None else math.sqrt(sum((u-v)**2 for u,v in zip(x,y))/len(x))

def neighbors(rows,t,k=80,gap=11):
    ti=int(t['_i']);s=[]
    for r in rows:
        if int(r['_i'])>=ti-gap or r.get('fwd_10d') is None:continue
        d=dist(r,t)
        if d is not None:s.append((d,r))
    s.sort(key=lambda z:z[0]);out=[];idx=[]
    for d,r in s:
        i=int(r['_i'])
        if any(abs(i-j)<5 for j in idx):continue
        out.append((d,r));idx.append(i)
        if len(out)>=k:break
    return out

def distribution(nn,h):
    a=[num(r.get(f'fwd_{h}d')) for _,r in nn];a=[v for v in a if v is not None]
    if not a:return {'n':0}
    return {'n':len(a),'mean':round(mean(a),4),'median':round(median(a),4),'positive_pct':round(100*sum(v>0 for v in a)/len(a),2),'p10':round(q(a,.1),4),'p25':round(q(a,.25),4),'p75':round(q(a,.75),4),'p90':round(q(a,.9),4)}

def baseline(rows,ti,h):
    a=[num(r.get(f'fwd_{h}d')) for r in rows if int(r['_i'])+h<ti and num(r.get(f'fwd_{h}d')) is not None]
    return None if not a else {'median':median(a),'prob':sum(v>0 for v in a)/len(a)}

def heat(rows,lo=None,hi=None):
    c={}
    for r in rows:
        bp,s,b,y=map(num,(r.get('box_position'),r.get('sentiment_stress_pct'),r.get('breadth_20d_pct'),r.get('fwd_5d')))
        if None in (bp,s,b,y) or (lo is not None and bp<lo) or (hi is not None and bp>=hi):continue
        key=(min(9,max(0,int(s//10))),min(9,max(0,int(b//10))));c.setdefault(key,[]).append(y)
    out=[]
    for si in range(10):
        for bi in range(10):
            a=c.get((si,bi),[]);out.append({'sentiment_bin':[si*10,(si+1)*10],'breadth_bin':[bi*10,(bi+1)*10],'n':len(a),'fwd5_mean':round(mean(a),4) if a else None,'fwd5_median':round(median(a),4) if a else None,'fwd5_positive_pct':round(100*sum(v>0 for v in a)/len(a),1) if a else None})
    return out

def main():
    d=json.loads(SRC.read_text(encoding='utf-8'));rows=d.get('daily') or []
    if len(rows)<500:raise RuntimeError('V1 daily state table missing')
    sd3=lag(rows,'sentiment_stress_pct',3);bd3=lag(rows,'breadth_20d_pct',3)
    svr=pct_hist(sd3);bvr=pct_hist(bd3);d1r=pct_hist([r.get('market_score_d1') for r in rows]);d3r=pct_hist([r.get('market_score_d3') for r in rows])
    e=[]
    for i,s in enumerate(rows):
        r=dict(s);r['_i']=i;r['sentiment_d3']=round(sd3[i],3) if sd3[i] is not None else None;r['breadth_d3']=round(bd3[i],3) if bd3[i] is not None else None
        bp=num(r.get('box_position'));sp=num(r.get('sentiment_stress_pct'));br=num(r.get('breadth_20d_pct'));ms=num(r.get('market_score_pct'))
        r['box_state']=round((max(-.2,min(1.2,bp))+.2)/1.4,6) if bp is not None else None
        r['sentiment_level']=round(sp/100,6) if sp is not None else None;r['breadth_level']=round(br/100,6) if br is not None else None;r['score_level']=round(ms/100,6) if ms is not None else None
        r['sentiment_velocity']=round(svr[i]/100,6) if svr[i] is not None else None;r['breadth_velocity']=round(bvr[i]/100,6) if bvr[i] is not None else None;r['score_d1_rank']=round(d1r[i]/100,6) if d1r[i] is not None else None;r['score_d3_rank']=round(d3r[i]/100,6) if d3r[i] is not None else None;e.append(r)
    eligible=[r for r in e if vec(r) is not None and r.get('fwd_10d') is not None]
    latest=[r for r in e if vec(r) is not None][-1];nn=neighbors(e,latest,max(KS))
    hood={str(k):{'distance_max':round(nn[:k][-1][0],5) if len(nn)>=k else None,**{f'fwd_{h}d':distribution(nn[:k],h) for h in H}} for k in KS}
    analogs=[{'date':r['date'],'distance':round(x,5),'box_position':r.get('box_position'),'sentiment_pct':r.get('sentiment_stress_pct'),'sentiment_d3':r.get('sentiment_d3'),'breadth_pct':r.get('breadth_20d_pct'),'breadth_d3':r.get('breadth_d3'),'market_score':r.get('market_score'),'market_score_d1':r.get('market_score_d1'),'market_score_d3':r.get('market_score_d3'),'fwd_3d':r.get('fwd_3d'),'fwd_5d':r.get('fwd_5d'),'fwd_10d':r.get('fwd_10d'),'mfe_10d':r.get('mfe_10d'),'mae_10d':r.get('mae_10d')} for x,r in nn[:30]]
    bps=[r.get('box_position') for r in eligible];cuts=[q(bps,.25),q(bps,.5),q(bps,.75)];bands=[(None,cuts[0]),(cuts[0],cuts[1]),(cuts[1],cuts[2]),(cuts[2],None)]
    hm={f'box_q{i+1}':{'box_range':[round(lo,4) if lo is not None else None,round(hi,4) if hi is not None else None],'cells':heat(eligible,lo,hi)} for i,(lo,hi) in enumerate(bands)}
    wf=[]
    for t in e:
        if t['date']<'2022-01-03' or vec(t) is None or t.get('fwd_10d') is None:continue
        z=neighbors(e,t,40)
        if len(z)<20:continue
        rec={'date':t['date'],'n_neighbors':len(z)}
        for h in H:
            ds=distribution(z,h);ba=baseline(e,int(t['_i']),h);a=num(t.get(f'fwd_{h}d'))
            if ds.get('n',0)>=20 and ba and a is not None:
                rec[f'pred_{h}d_median']=ds['median'];rec[f'pred_{h}d_prob']=ds['positive_pct']/100;rec[f'base_{h}d_median']=ba['median'];rec[f'base_{h}d_prob']=ba['prob'];rec[f'actual_{h}d']=a
        wf.append(rec)
    val={}
    for h in H:
        u=[r for r in wf if r.get(f'actual_{h}d') is not None];pred=[r[f'pred_{h}d_median'] for r in u];base=[r[f'base_{h}d_median'] for r in u];act=[r[f'actual_{h}d'] for r in u];pp=[r[f'pred_{h}d_prob'] for r in u];bp=[r[f'base_{h}d_prob'] for r in u]
        if not u:val[f'{h}d']={'n':0};continue
        km=mean(abs(a-b) for a,b in zip(pred,act));bm=mean(abs(a-b) for a,b in zip(base,act));y=[1 if a>0 else 0 for a in act];kb=mean((a-b)**2 for a,b in zip(pp,y));bb=mean((a-b)**2 for a,b in zip(bp,y));sp=spearman(pred,act)
        val[f'{h}d']={'n':len(u),'pred_actual_spearman':round(sp,4) if sp is not None else None,'direction_accuracy_pct':round(100*sum((a>0)==(b>0) for a,b in zip(pred,act))/len(u),2),'knn_mae':round(km,4),'baseline_mae':round(bm,4),'mae_improvement':round(bm-km,4),'knn_brier':round(kb,5),'baseline_brier':round(bb,5),'brier_improvement':round(bb-kb,5)}
    out={'schema':'MARKET-STATE-BOX-V2','generated_at':datetime.now(timezone.utc).isoformat(),'research_only':True,'model':{'type':'continuous nearest-neighbor state retrieval','hard_entry_thresholds':False,'structural_requirement':'eligible point-in-time S&P 500 box exists','feature_weighting':'equal after normalization; no optimized weights','features':list(F),'neighbor_sizes':list(KS),'neighbor_decluster_sessions':5,'target_exclusion_sessions':11},'warnings':['Sentiment and Market Score histories include reconstructed non-publication-time observations.','Walk-forward prevents future outcome leakage, but source reconstruction still limits strict point-in-time claims.','Heatmap box quartiles are descriptive bins, not strategy thresholds.'],'coverage':{'start':eligible[0]['date'],'end':eligible[-1]['date'],'complete_states':len(eligible),'walk_forward_start':wf[0]['date'] if wf else None,'walk_forward_n':len(wf)},'latest':{'date':latest['date'],'box_position':latest.get('box_position'),'sentiment_stress_pct':latest.get('sentiment_stress_pct'),'sentiment_d3':latest.get('sentiment_d3'),'breadth_20d_pct':latest.get('breadth_20d_pct'),'breadth_d3':latest.get('breadth_d3'),'market_score':latest.get('market_score'),'market_score_pct':latest.get('market_score_pct'),'market_score_d1':latest.get('market_score_d1'),'market_score_d3':latest.get('market_score_d3'),'state_vector':{k:latest.get(k) for k in F}},'neighborhoods':hood,'analogs':analogs,'heatmaps':hm,'walk_forward_validation':val,'walk_forward_predictions_tail':wf[-120:]}
    OUT.write_text(json.dumps(out,ensure_ascii=False,separators=(',',':')),encoding='utf-8');print('Wrote',OUT,out['coverage']);print(json.dumps(val,ensure_ascii=False))
if __name__=='__main__':main()
