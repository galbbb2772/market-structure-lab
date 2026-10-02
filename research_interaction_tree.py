from __future__ import annotations

import json, math, statistics
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.tree import DecisionTreeClassifier, export_text

from research_pattern_edge_map import build_sp_state_map, feature_rows
from research_sp500_survivor_diagnostic import enrich

SRC = Path('docs/data/structure_lab.json')
OUT = Path('docs/data/interaction_tree_validation.json')
H = 5
FEATURES = [
    'day_ret','pre1','pre3','pre5','pre10','dd20','dd60',
    'ma20_dist','ma50_dist','ma200_dist','rsi14','atr_rank','pos60',
    'range60_width','bull_flag','weak_flag'
]
DEPTHS = (2, 3)
MIN_LEAF = 80
PURGE = 10
MIN_TRAIN = 500


def avg(xs):
    z=[float(x) for x in xs if x is not None and math.isfinite(float(x))]
    return statistics.fmean(z) if z else None


def med(xs):
    z=sorted(float(x) for x in xs if x is not None and math.isfinite(float(x)))
    if not z:return None
    n=len(z)
    return z[n//2] if n%2 else (z[n//2-1]+z[n//2])/2


def prepare(data, sym, state_map):
    bars=data['instruments'][sym]['bars']
    rows=[r for r in feature_rows(bars,state_map) if r['streak_bucket']=='D1']
    rows=enrich(bars,rows)
    out=[]
    for r in rows:
        q=dict(r)
        q['bull_flag']=1.0 if r['market_state']=='bull' else 0.0
        q['weak_flag']=1.0 if r['market_state']=='weak' else 0.0
        if all(q.get(k) is not None and math.isfinite(float(q[k])) for k in FEATURES):
            out.append(q)
    return out


def matrix(rows):
    X=np.array([[float(r[k]) for k in FEATURES] for r in rows],dtype=float)
    y=np.array([1 if r['t5_up'] else 0 for r in rows],dtype=int)
    ret=np.array([float(r['t5_ret']) for r in rows],dtype=float)
    return X,y,ret


def tree_paths(model):
    t=model.tree_
    names=np.array(FEATURES,dtype=object)
    paths=[]
    def walk(node, conds):
        if t.feature[node] < 0:
            paths.append({'leaf':int(node),'n':int(t.n_node_samples[node]),'path':' AND '.join(conds) if conds else 'ALL'})
            return
        f=names[t.feature[node]]; th=float(t.threshold[node])
        walk(t.children_left[node], conds+[f'{f} <= {th:.4f}'])
        walk(t.children_right[node], conds+[f'{f} > {th:.4f}'])
    walk(0,[])
    return paths


def evaluate(rows, depth):
    years=sorted(set(r['year'] for r in rows))
    rec=[]; split_counts=Counter(); pair_counts=Counter(); yearly={}
    for y in years:
        test=[r for r in rows if r['year']==y]
        if not test: continue
        start_idx=min(r['idx'] for r in test)
        train=[r for r in rows if r['year']<y and r['idx']+PURGE < start_idx]
        if len(train)<MIN_TRAIN: continue
        Xtr,ytr,rtr=matrix(train); Xte,yte,rte=matrix(test)
        model=DecisionTreeClassifier(max_depth=depth,min_samples_leaf=MIN_LEAF,criterion='log_loss',random_state=7)
        model.fit(Xtr,ytr)
        p=model.predict_proba(Xte)[:,1]
        base_p=float(np.mean(ytr)); base_med=float(np.median(rtr))
        tr_leaf=model.apply(Xtr); te_leaf=model.apply(Xte)
        leaf_med={int(l):float(np.median(rtr[tr_leaf==l])) for l in np.unique(tr_leaf)}
        pred_med=np.array([leaf_med[int(l)] for l in te_leaf],dtype=float)
        b0=(base_p-yte)**2; b1=(p-yte)**2
        m0=np.abs(rte-base_med); m1=np.abs(rte-pred_med)
        yearly[str(y)]={
            'n':len(test),'brier_improvement':float(np.mean(b0-b1)),
            'median_mae_improvement':float(np.mean(m0-m1)),
        }
        for i,r in enumerate(test):
            rec.append({'year':y,'b0':float(b0[i]),'b1':float(b1[i]),'m0':float(m0[i]),'m1':float(m1[i])})
        # count which features and parent-child feature interactions recur across yearly fits
        tt=model.tree_
        for node,fidx in enumerate(tt.feature):
            if fidx>=0:
                split_counts[FEATURES[int(fidx)]]+=1
                for ch in (tt.children_left[node],tt.children_right[node]):
                    cf=tt.feature[ch]
                    if cf>=0:
                        pair_counts[f'{FEATURES[int(fidx)]} -> {FEATURES[int(cf)]}']+=1
    if not rec:return {'n':0}
    bimp=avg(r['b0']-r['b1'] for r in rec); mimp=avg(r['m0']-r['m1'] for r in rec)
    return {
        'n':len(rec),'depth':depth,'min_leaf':MIN_LEAF,'purge_sessions':PURGE,
        'brier_improvement':bimp,'median_mae_improvement':mimp,
        'positive_brier_years':sum(v['brier_improvement']>0 for v in yearly.values()),
        'positive_mae_years':sum(v['median_mae_improvement']>0 for v in yearly.values()),
        'years':len(yearly),
        'top_split_features':split_counts.most_common(8),
        'top_feature_interactions':pair_counts.most_common(8),
        'yearly':yearly,
    }


def descriptive_final_tree(rows, depth):
    X,y,ret=matrix(rows)
    model=DecisionTreeClassifier(max_depth=depth,min_samples_leaf=MIN_LEAF,criterion='log_loss',random_state=7)
    model.fit(X,y)
    leaves=model.apply(X)
    base_up=100*float(np.mean(y)); base_med=float(np.median(ret))
    path_map={x['leaf']:x['path'] for x in tree_paths(model)}
    leaf_rows=[]
    for leaf in sorted(np.unique(leaves)):
        mask=leaves==leaf; n=int(mask.sum()); up=100*float(np.mean(y[mask])); mr=float(np.median(ret[mask]));
        leaf_rows.append({'leaf':int(leaf),'n':n,'path':path_map[int(leaf)],'up_pct':up,'median_ret':mr,'up_edge_pp':up-base_up,'median_edge_pct':mr-base_med})
    leaf_rows.sort(key=lambda x:(x['median_edge_pct'],x['up_edge_pp']),reverse=True)
    return {'depth':depth,'base_up_pct':base_up,'base_median_ret':base_med,'text_tree':export_text(model,feature_names=FEATURES),'leaves':leaf_rows}


def main():
    data=json.loads(SRC.read_text())
    state_map=build_sp_state_map(data['instruments']['^GSPC']['bars'])
    result={'schema':'INTERACTION-TREE-VALIDATION-V1','note':'Shallow CART interaction test on D1 only. Year-by-year expanding walk-forward, 10-session purge, large leaves. Final tree is descriptive only, not OOS evidence.','config':{'features':FEATURES,'depths':DEPTHS,'min_leaf':MIN_LEAF,'purge_sessions':PURGE,'horizon':H},'instruments':{}}
    for sym in ['^GSPC','^IXIC','^DJI']:
        rows=prepare(data,sym,state_map)
        result['instruments'][sym]={
            'name':data['instruments'][sym]['name'],'n_D1':len(rows),
            'oos':{str(d):evaluate(rows,d) for d in DEPTHS},
            'descriptive_final_tree':{str(d):descriptive_final_tree(rows,d) for d in DEPTHS},
        }
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    compact={}
    for sym,x in result['instruments'].items():
        compact[sym]={'name':x['name'],'n_D1':x['n_D1'],'oos':{d:{k:v for k,v in z.items() if k!='yearly'} for d,z in x['oos'].items()},'top_leaves_depth3':x['descriptive_final_tree']['3']['leaves'][:4]}
    print(json.dumps(compact,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
