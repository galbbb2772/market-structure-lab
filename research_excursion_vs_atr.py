from __future__ import annotations

import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from research_pattern_edge_map import build_sp_state_map
from research_pattern_purged_validation import bh_adjust, nw_one_sided_p
from research_return_surface import HORIZONS, PAIRS, prepare

SRC = Path('docs/data/structure_lab.json')
OUT = Path('docs/data/excursion_vs_atr.json')
SYMS = ('^GSPC', '^IXIC', '^DJI')
BANDWIDTHS = (0.12, 0.20)
BOUNDARY_GAP = 10
MIN_TRAIN_N = 400
MIN_SELECTOR_YEARS = 8
MIN_SELECTOR_EVENTS = 200
FDR_LEVEL = 0.10
TARGETS = ('mfe', 'downside', 'range', 'balance')


def avg(xs):
    z = [float(x) for x in xs if x is not None and math.isfinite(float(x))]
    return statistics.fmean(z) if z else None


def pct_map(train_values, query_values):
    s = np.sort(np.asarray(train_values, dtype=float))
    q = np.asarray(query_values, dtype=float)
    return np.searchsorted(s, q, side='right') / max(len(s), 1)


def combo_name(pair, bw):
    return f'{pair[0]}×{pair[1]}|bw={bw:.2f}'


def target_value(row, h, target):
    mfe = float(row[f'h{h}_mfe'])
    mae = float(row[f'h{h}_mae'])
    if target == 'mfe': return mfe
    if target == 'downside': return -mae
    if target == 'range': return mfe - mae
    if target == 'balance': return mfe + mae
    raise KeyError(target)


def attach_atr_pct(bars, rows):
    close = np.asarray([float(b[4]) for b in bars], dtype=float)
    tr = np.full(len(bars), np.nan)
    for i in range(1, len(bars)):
        hi, lo = float(bars[i][2]), float(bars[i][3])
        tr[i] = max(hi - lo, abs(hi - close[i-1]), abs(lo - close[i-1]))
    atr = np.full(len(bars), np.nan)
    for i in range(14, len(bars)):
        atr[i] = np.nanmean(tr[i-13:i+1])
    out = []
    for r in rows:
        q = dict(r)
        i = r['idx']
        q['atr_pct'] = 100.0 * atr[i] / close[i]
        out.append(q)
    return out


def predict_pair(train, test, pair):
    xk, yk = pair
    tx = np.asarray([r[xk] for r in train], dtype=float)
    ty = np.asarray([r[yk] for r in train], dtype=float)
    qx = np.asarray([r[xk] for r in test], dtype=float)
    qy = np.asarray([r[yk] for r in test], dtype=float)
    train_x = pct_map(tx, tx); train_y = pct_map(ty, ty)
    test_x = pct_map(tx, qx); test_y = pct_map(ty, qy)
    d2 = (test_x[:, None] - train_x[None, :]) ** 2 + (test_y[:, None] - train_y[None, :]) ** 2
    vals = {(target,h):np.asarray([target_value(r,h,target) for r in train],dtype=float) for target in TARGETS for h in HORIZONS}
    out = {}
    for bw in BANDWIDTHS:
        w = np.exp(-0.5*d2/(bw*bw)); sw=np.maximum(w.sum(axis=1),1e-15)
        out[bw] = {(target,h):(w@arr)/sw for (target,h),arr in vals.items()}
    return out


def fit_atr_baseline(train, h, target):
    x = np.asarray([r['atr_pct'] for r in train], dtype=float)
    y = np.asarray([target_value(r,h,target) for r in train], dtype=float)
    X = np.column_stack([np.ones(len(x)), x])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return beta


def predict_atr(beta, test):
    x = np.asarray([r['atr_pct'] for r in test], dtype=float)
    return beta[0] + beta[1]*x


def score_year(test, surface_pred, atr_pred, h, target):
    actual=np.asarray([target_value(r,h,target) for r in test],dtype=float)
    se=np.abs(actual-np.asarray(surface_pred,dtype=float))
    ae=np.abs(actual-np.asarray(atr_pred,dtype=float))
    diff=ae-se
    return {'n':len(actual),'atr_mae':float(np.mean(ae)),'surface_mae':float(np.mean(se)),'mae_improvement':float(np.mean(diff)),'normalized_skill':float(np.mean(diff)/np.mean(ae)) if np.mean(ae)>0 else None,'_event_diff':diff}


def selector_score(history):
    if len(history)<MIN_SELECTOR_YEARS or sum(x['n'] for x in history)<MIN_SELECTOR_EVENTS: return None
    s=[x['normalized_skill'] for x in history if x.get('normalized_skill') is not None]
    if not s:return None
    return {'score':avg(s),'years':len(history),'events':sum(x['n'] for x in history)}


def precompute(rows):
    rows=sorted(rows,key=lambda r:r['idx']); years=sorted({int(r['year']) for r in rows})
    by_year={y:[r for r in rows if int(r['year'])==y] for y in years}
    metrics=defaultdict(dict); folds=[]
    for year in years:
        test=by_year[year]
        if not test: continue
        first_idx=min(r['idx'] for r in test); cutoff=first_idx-BOUNDARY_GAP-1
        train=[r for r in rows if r['idx']<=cutoff]
        if len(train)<MIN_TRAIN_N: continue
        atr_models={(target,h):fit_atr_baseline(train,h,target) for target in TARGETS for h in HORIZONS}
        atr_preds={(target,h):predict_atr(atr_models[(target,h)],test) for target in TARGETS for h in HORIZONS}
        folds.append({'year':year,'train_n':len(train),'test_n':len(test),'cutoff_idx':cutoff})
        for pair in PAIRS:
            pp=predict_pair(train,test,pair)
            for bw in BANDWIDTHS:
                cname=combo_name(pair,bw)
                for target in TARGETS:
                    for h in HORIZONS:
                        metrics[(cname,target,h)][year]=score_year(test,pp[bw][(target,h)],atr_preds[(target,h)],h,target)
    return metrics,folds,years


def nested_select(metrics,years,target,h):
    combos=sorted({k[0] for k in metrics if k[1]==target and k[2]==h})
    sels=[]; diffs=[]; year_edges=[]
    for year in years:
        cand=[]
        for c in combos:
            cur=metrics[(c,target,h)].get(year)
            if cur is None: continue
            hist=[metrics[(c,target,h)][y] for y in sorted(metrics[(c,target,h)]) if y<year]
            ss=selector_score(hist)
            if ss is not None:cand.append((c,ss,cur))
        if not cand: continue
        c,ss,cur=max(cand,key=lambda x:(x[1]['score'],x[1]['events'],x[0]))
        ed=[float(x) for x in cur['_event_diff']]; diffs.extend(ed); year_edges.append(avg(ed))
        sels.append({'year':year,'combo':c,'selector_score':ss['score'],'prior_validation_years':ss['years'],'prior_validation_events':ss['events'],'test_n':cur['n'],'atr_mae':cur['atr_mae'],'surface_mae':cur['surface_mae'],'mae_improvement':cur['mae_improvement'],'normalized_skill':cur['normalized_skill']})
    if not sels:return None
    p=nw_one_sided_p(diffs,lag=max(HORIZONS)); pos=sum(x>0 for x in year_edges)
    atr_mae=avg(s['atr_mae'] for s in sels); surf_mae=avg(s['surface_mae'] for s in sels)
    return {'target':target,'horizon':h,'outer_years':len(sels),'outer_event_n':sum(x['test_n'] for x in sels),'atr_mae':atr_mae,'surface_mae':surf_mae,'mae_improvement':avg(diffs),'skill_pct_vs_atr':100*avg(diffs)/atr_mae if atr_mae and atr_mae>0 else None,'positive_years':pos,'positive_year_rate':pos/len(year_edges),'p_value':p,'combo_frequency':dict(Counter(x['combo'] for x in sels).most_common()),'year_selections':sels}


def main():
    data=json.loads(SRC.read_text()); state_map=build_sp_state_map(data['instruments']['^GSPC']['bars'])
    result={'schema':'EXCURSION-VS-ATR-V1','note':'Harder nested walk-forward benchmark: selected 2D surface must beat a prior-only linear ATR%-based predictor, not a constant D1 mean. Historical Shadow research only.','method':{'event':'D1 only','pairs':PAIRS,'bandwidths':BANDWIDTHS,'baseline':'prior-only OLS target ~ intercept + current ATR14%','selector':'pair+bandwidth chosen only from earlier walk-forward years by normalized MAE skill vs ATR baseline','boundary_gap_sessions':BOUNDARY_GAP,'inference':'one-sided Newey-West/HAC paired MAE improvement; BH-FDR across 48 tests','fdr_level':FDR_LEVEL},'instruments':{}}
    tests=[]
    for sym in SYMS:
        bars=data['instruments'][sym]['bars']; rows=attach_atr_pct(bars,prepare(data,sym,state_map)); metrics,folds,years=precompute(rows); st=[]
        for target in TARGETS:
            for h in HORIZONS:
                t=nested_select(metrics,years,target,h)
                if t:
                    t['symbol']=sym;t['name']=data['instruments'][sym]['name'];st.append(t);tests.append(t)
        result['instruments'][sym]={'name':data['instruments'][sym]['name'],'n_D1':len(rows),'folds':folds,'tests':st}
    qrows=[{'p_value':t['p_value']} for t in tests];bh_adjust(qrows)
    for t,q in zip(tests,qrows):
        t['q_value']=q['q_value'];t['confirmed']=bool(t['q_value'] is not None and t['q_value']<=FDR_LEVEL and t['mae_improvement']>0 and t['positive_year_rate']>=0.60 and t['outer_event_n']>=500)
    ranked=sorted(tests,key=lambda t:(t['q_value'] if t['q_value'] is not None else 2,-float(t['skill_pct_vs_atr'] or -999)))
    result['summary']={'tested':len(tests),'confirmed':sum(t['confirmed'] for t in tests),'confirmed_tests':[{**{k:t[k] for k in ('symbol','name','target','horizon','outer_years','outer_event_n','atr_mae','surface_mae','mae_improvement','skill_pct_vs_atr','positive_year_rate','p_value','q_value','confirmed')},'top_combos':list(t['combo_frequency'].items())[:4]} for t in ranked if t['confirmed']],'best_tests':[{**{k:t[k] for k in ('symbol','name','target','horizon','outer_years','outer_event_n','atr_mae','surface_mae','mae_improvement','skill_pct_vs_atr','positive_year_rate','p_value','q_value','confirmed')},'top_combos':list(t['combo_frequency'].items())[:4]} for t in ranked[:16]]}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result['summary'],ensure_ascii=False,indent=2))

if __name__=='__main__':main()
