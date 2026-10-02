from __future__ import annotations

import json, math, statistics
from collections import defaultdict
from pathlib import Path

import numpy as np

from research_pattern_edge_map import build_sp_state_map, feature_rows
from research_sp500_survivor_diagnostic import enrich

SRC = Path('docs/data/structure_lab.json')
OUT = Path('docs/data/alternative_retest_validation.json')
H = 5
K = 40
FEATURES = ['pre1','pre5','pre10','dd20','dd60','ma20_dist','ma50_dist','ma200_dist','rsi14','atr_rank','pos60']


def avg(xs):
    xs=[float(x) for x in xs if x is not None and math.isfinite(float(x))]
    return statistics.fmean(xs) if xs else None


def quantile(xs,p):
    s=sorted(float(x) for x in xs if x is not None and math.isfinite(float(x)))
    if not s:return None
    z=(len(s)-1)*p;i=int(z);f=z-i
    return s[i]+(s[min(i+1,len(s)-1)]-s[i])*f


def summary(rows):
    if not rows:return {'n':0}
    rs=[r['t5_ret'] for r in rows]
    return {'n':len(rows),'up_pct':100*sum(x>0 for x in rs)/len(rs),'mean':avg(rs),'median':quantile(rs,.5),'p25':quantile(rs,.25),'p75':quantile(rs,.75)}


def continuous_knn(rows):
    by_year=defaultdict(list)
    for r in rows: by_year[r['year']].append(r)
    train=[]; rec=[]
    for y in sorted(by_year):
        test=by_year[y]
        if len(train)>=120 and test:
            # Freeze the candidate pool before the test year and apply a 10-session
            # boundary embargo. This makes the candidate matrix constant within year.
            first_idx=min(r['idx'] for r in test)
            cand=[x for x in train if x['idx']+10 < first_idx]
            if len(cand)>=K:
                X=np.asarray([[float(r[k]) for k in FEATURES] for r in cand],dtype=float)
                med=np.nanmedian(X,axis=0)
                q1=np.nanpercentile(X,25,axis=0); q3=np.nanpercentile(X,75,axis=0)
                scale=q3-q1
                sd=np.nanstd(X,axis=0)
                scale=np.where(scale>1e-12,scale,np.where(sd>1e-12,sd,1.0))
                Xz=(X-med)/scale
                cand_up=np.asarray([1.0 if r['t5_up'] else 0.0 for r in cand])
                cand_ret=np.asarray([r['t5_ret'] for r in cand],dtype=float)
                base_p=float(np.mean(cand_up))
                base_med=float(np.median(cand_ret))
                for r in test:
                    z=(np.asarray([float(r[k]) for k in FEATURES])-med)/scale
                    d=np.nanmean((Xz-z)**2,axis=1)
                    idx=np.argpartition(d,K-1)[:K]
                    p=float(np.mean(cand_up[idx])); medret=float(np.median(cand_ret[idx]))
                    rec.append({'year':y,'actual':r['t5_up'],'ret':r['t5_ret'],'base_p':base_p,'knn_p':p,'base_med':base_med,'knn_med':medret})
        train.extend(test)
    if not rec:return {'n':0}
    b0=avg((r['base_p']-(1 if r['actual'] else 0))**2 for r in rec)
    b1=avg((r['knn_p']-(1 if r['actual'] else 0))**2 for r in rec)
    m0=avg(abs(r['ret']-r['base_med']) for r in rec);m1=avg(abs(r['ret']-r['knn_med']) for r in rec)
    yearly={}
    years=sorted(set(r['year'] for r in rec))
    for y in years:
        z=[r for r in rec if r['year']==y]
        yearly[str(y)]={'n':len(z),'brier_improvement':avg((r['base_p']-(1 if r['actual'] else 0))**2-(r['knn_p']-(1 if r['actual'] else 0))**2 for r in z),'median_mae_improvement':avg(abs(r['ret']-r['base_med'])-abs(r['ret']-r['knn_med']) for r in z)}
    return {'n':len(rec),'k':K,'base_brier':b0,'knn_brier':b1,'brier_improvement':b0-b1,'base_median_mae':m0,'knn_median_mae':m1,'median_mae_improvement':m0-m1,'positive_brier_years':sum(v['brier_improvement']>0 for v in yearly.values()),'years':len(yearly),'yearly':yearly}


def target_state(r):
    return r['market_state']=='bull' and r['pos60']<33.333333 and 33.333333<=r['atr_rank']<66.666667


def matched_control(rows):
    # Target vs non-target D1 controls. Match only on background/context variables,
    # not on pos60 / MA20 / MA50 / RSI that characterize the pullback itself.
    targets=[r for r in rows if target_state(r)]
    controls=[r for r in rows if not target_state(r)]
    match_keys=['day_ret','pre1','atr_rank','ma200_dist']
    pairs=[]
    for t in targets:
        pool=[c for c in controls if abs(c['year']-t['year'])<=5 and c['market_state']=='bull' and abs(c['idx']-t['idx'])>10]
        if len(pool)<3: continue
        sc={}
        for k in match_keys:
            xs=[c[k] for c in pool]; q1=quantile(xs,.25);q3=quantile(xs,.75);sc[k]=max((q3-q1) if q3>q1 else 1.0,1e-9)
        def d(c):return math.sqrt(sum(((t[k]-c[k])/sc[k])**2 for k in match_keys)/len(match_keys))
        nn=sorted(pool,key=d)[:3]
        ctrl=avg(c['t5_ret'] for c in nn)
        pairs.append({'date':t['date'],'target_ret':t['t5_ret'],'control_ret':ctrl,'diff':t['t5_ret']-ctrl})
    diffs=[p['diff'] for p in pairs]
    if diffs:
        obs=avg(diffs); n=len(diffs); sd=statistics.stdev(diffs) if n>1 else 0
        se=sd/math.sqrt(n) if n else None; z=obs/se if se and se>0 else None
    else: obs=se=z=None
    return {'n_pairs':len(pairs),'mean_paired_edge':obs,'median_paired_edge':quantile(diffs,.5) if diffs else None,'positive_pair_pct':100*sum(x>0 for x in diffs)/len(diffs) if diffs else None,'se_mean':se,'z_descriptive':z}


def retest_score(r):
    # Broad monotone mechanism score; no optimized single cutoff.
    s=0.0
    if r['market_state']=='bull': s+=1.0
    if r['pre1']>0: s+=1.0
    s += max(0.0,min(1.5,(40-r['pos60'])/25))
    s += max(0.0,min(1.5,(-r['ma50_dist'])/3.0))
    s += max(0.0,min(1.0,(45-r['rsi14'])/20.0))
    s += max(0.0,1.0-abs(r['atr_rank']-50)/35)
    return s


def score_gradient(rows):
    z=[dict(r,score=retest_score(r)) for r in rows]
    cuts=[quantile([r['score'] for r in z],p) for p in (.2,.4,.6,.8)]
    groups=defaultdict(list)
    for r in z:
        s=r['score']
        b=1 if s<=cuts[0] else 2 if s<=cuts[1] else 3 if s<=cuts[2] else 4 if s<=cuts[3] else 5
        groups[f'Q{b}'].append(r)
    out={k:{**summary(v),'score_median':quantile([r['score'] for r in v],.5)} for k,v in sorted(groups.items())}
    meds=[out[f'Q{i}']['median'] for i in range(1,6)]
    ups=[out[f'Q{i}']['up_pct'] for i in range(1,6)]
    return {'quintiles':out,'median_monotone_non_decreasing':all(meds[i]>=meds[i-1] for i in range(1,5)),'up_prob_monotone_non_decreasing':all(ups[i]>=ups[i-1] for i in range(1,5)),'q5_minus_q1_median':meds[-1]-meds[0],'q5_minus_q1_up_pp':ups[-1]-ups[0]}


def prepare(data,sym,state_map):
    bars=data['instruments'][sym]['bars']
    rr=[r for r in feature_rows(bars,state_map) if r['streak_bucket']=='D1']
    return enrich(bars,rr)


def main():
    data=json.loads(SRC.read_text())
    spbars=data['instruments']['^GSPC']['bars']
    state_map=build_sp_state_map(spbars)
    result={'schema':'ALTERNATIVE-RETEST-VALIDATION-V1','note':'Alternative formulations to reduce dependence on hard bins. Still research-stage; no method is an independent future sample.','instruments':{}}
    for sym in ['^GSPC','^IXIC','^DJI']:
        rows=prepare(data,sym,state_map)
        result['instruments'][sym]={'name':data['instruments'][sym]['name'],'n_D1':len(rows),'continuous_knn':continuous_knn(rows),'matched_control':matched_control(rows) if sym=='^GSPC' else None,'retest_score_gradient':score_gradient(rows)}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    printable={s:{'name':x['name'],'n_D1':x['n_D1'],'knn':{k:v for k,v in x['continuous_knn'].items() if k!='yearly'},'matched_control':x['matched_control'],'score_gradient':x['retest_score_gradient']} for s,x in result['instruments'].items()}
    print(json.dumps(printable,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
