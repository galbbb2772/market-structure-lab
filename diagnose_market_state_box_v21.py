"""V2.1 diagnostic: test state variables without nearest-neighbor geometry.

Single features use fixed deciles on normalized point-in-time state variables.
Selected pairs use fixed 5x5 bins. Predictions are walk-forward and only use
historical observations whose forward outcomes were already fully realized.
This is diagnostic after V2 inspection, not fresh model selection.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
import build_market_state_box_v2 as v2
import diagnose_market_state_box_v2 as d2

ROOT=Path(__file__).resolve().parent
SRC=ROOT/'docs/data/market_state_box_v1.json'
OUT=ROOT/'docs/data/market_state_box_v21_diagnostics.json'
FEATURES=('box_state','sentiment_level','sentiment_velocity','breadth_level','breadth_velocity','score_level','score_d1_rank','score_d3_rank')
PAIRS=(
 ('box_state','breadth_level'),
 ('box_state','score_level'),
 ('breadth_level','score_level'),
 ('breadth_level','score_d3_rank'),
 ('box_state','score_d3_rank'),
)

def bin_id(x,bins):
    z=v2.num(x)
    if z is None:return None
    z=max(0.0,min(0.999999,z))
    return int(z*bins)

def hist_pool(rows,ti,h):
    return [r for r in rows if int(r['_i'])+h<ti and r.get(f'fwd_{h}d') is not None]

def pred_from(pool,h,selector,min_n):
    a=[v2.num(r.get(f'fwd_{h}d')) for r in pool if selector(r)]
    a=[x for x in a if x is not None]
    if len(a)<min_n:return None
    return median(a),sum(x>0 for x in a)/len(a),len(a)

def base_from(pool,h):
    a=[v2.num(r.get(f'fwd_{h}d')) for r in pool]
    a=[x for x in a if x is not None]
    if not a:return None
    return median(a),sum(x>0 for x in a)/len(a)

def metrics(records):
    if not records:return {'n':0}
    pred=[x['pred'] for x in records];prob=[x['prob'] for x in records];base=[x['base'] for x in records];bprob=[x['base_prob'] for x in records];act=[x['actual'] for x in records];y=[1 if x>0 else 0 for x in act]
    km=mean(abs(x-z) for x,z in zip(pred,act));bm=mean(abs(x-z) for x,z in zip(base,act));kb=mean((x-z)**2 for x,z in zip(prob,y));bb=mean((x-z)**2 for x,z in zip(bprob,y));sp=v2.spearman(pred,act)
    return {'n':len(records),'spearman':round(sp,4) if sp is not None else None,'direction_accuracy_pct':round(100*sum((x>0)==(z>0) for x,z in zip(pred,act))/len(records),2),'mae_improvement':round(bm-km,4),'brier_improvement':round(bb-kb,5)}

def validate_single(rows,f,bins=10,min_n=20):
    out={}
    for h in v2.H:
        rec=[]
        for t in rows:
            if t['date']<'2022-01-03' or t.get('fwd_10d') is None:continue
            b=bin_id(t.get(f),bins)
            if b is None:continue
            ti=int(t['_i']);pool=hist_pool(rows,ti,h);p=pred_from(pool,h,lambda r:bin_id(r.get(f),bins)==b,min_n);base=base_from(pool,h);a=v2.num(t.get(f'fwd_{h}d'))
            if p and base and a is not None:rec.append({'pred':p[0],'prob':p[1],'base':base[0],'base_prob':base[1],'actual':a,'cell_n':p[2]})
        out[f'{h}d']=metrics(rec)
    return out

def validate_pair(rows,a,b,bins=5,min_n=15):
    out={}
    for h in v2.H:
        rec=[]
        for t in rows:
            if t['date']<'2022-01-03' or t.get('fwd_10d') is None:continue
            ba,bb=bin_id(t.get(a),bins),bin_id(t.get(b),bins)
            if ba is None or bb is None:continue
            ti=int(t['_i']);pool=hist_pool(rows,ti,h);p=pred_from(pool,h,lambda r:bin_id(r.get(a),bins)==ba and bin_id(r.get(b),bins)==bb,min_n);base=base_from(pool,h);actual=v2.num(t.get(f'fwd_{h}d'))
            if p and base and actual is not None:rec.append({'pred':p[0],'prob':p[1],'base':base[0],'base_prob':base[1],'actual':actual,'cell_n':p[2]})
        out[f'{h}d']=metrics(rec)
    return out

def main():
    src=json.loads(SRC.read_text(encoding='utf-8'));rows=d2.enrich(src.get('daily') or [])
    singles={f:validate_single(rows,f) for f in FEATURES}
    pairs={f'{a}__{b}':{'features':[a,b],'validation':validate_pair(rows,a,b)} for a,b in PAIRS}
    out={'schema':'MARKET-STATE-BOX-V2.1-DIAGNOSTICS','generated_at':datetime.now(timezone.utc).isoformat(),'diagnostic_only':True,'selection_warning':'Buckets/pairs are inspected after V2 results; positives require later fresh OOS confirmation.','single_feature_bins':10,'pair_bins':5,'single_features':singles,'pairs':pairs}
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False))
if __name__=='__main__':main()
