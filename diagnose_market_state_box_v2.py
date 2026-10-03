"""Diagnostic feature-set ablation for Market State × Box V2.

This is deliberately labelled diagnostic, not fresh OOS model selection: feature
sets are inspected after seeing the first full-8D V2 result. No weights or numeric
thresholds are optimized here; each set uses equal-weight normalized distance.
"""
import json, math
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
import build_market_state_box_v2 as v2

ROOT=Path(__file__).resolve().parent
SRC=ROOT/'docs/data/market_state_box_v1.json'
OUT=ROOT/'docs/data/market_state_box_v2_diagnostics.json'
SETS={
 'box_only':('box_state',),
 'box_breadth_level':('box_state','breadth_level'),
 'box_breadth_level_velocity':('box_state','breadth_level','breadth_velocity'),
 'box_breadth_score_levels':('box_state','breadth_level','score_level'),
 'box_breadth_score_momentum':('box_state','breadth_level','breadth_velocity','score_level','score_d1_rank','score_d3_rank'),
 'box_sentiment_breadth_levels':('box_state','sentiment_level','breadth_level'),
 'all_levels':('box_state','sentiment_level','breadth_level','score_level'),
 'full_8d':v2.F,
}

def vector(r,keys):
    x=[v2.num(r.get(k)) for k in keys];return x if all(z is not None for z in x) else None

def distance(a,b,keys):
    x,y=vector(a,keys),vector(b,keys)
    return None if x is None or y is None else math.sqrt(sum((u-v)**2 for u,v in zip(x,y))/len(x))

def neighbors(rows,t,keys,k=40,gap=11):
    ti=int(t['_i']);s=[]
    for r in rows:
        if int(r['_i'])>=ti-gap or r.get('fwd_10d') is None:continue
        z=distance(r,t,keys)
        if z is not None:s.append((z,r))
    s.sort(key=lambda z:z[0]);out=[];idx=[]
    for z,r in s:
        i=int(r['_i'])
        if any(abs(i-j)<5 for j in idx):continue
        out.append((z,r));idx.append(i)
        if len(out)>=k:break
    return out

def distout(nn,h):
    a=[v2.num(r.get(f'fwd_{h}d')) for _,r in nn];a=[x for x in a if x is not None]
    return None if not a else (median(a),sum(x>0 for x in a)/len(a))

def enrich(rows):
    sd3=v2.lag(rows,'sentiment_stress_pct',3);bd3=v2.lag(rows,'breadth_20d_pct',3)
    svr=v2.pct_hist(sd3);bvr=v2.pct_hist(bd3);d1r=v2.pct_hist([r.get('market_score_d1') for r in rows]);d3r=v2.pct_hist([r.get('market_score_d3') for r in rows])
    out=[]
    for i,s in enumerate(rows):
        r=dict(s);r['_i']=i;bp=v2.num(r.get('box_position'));sp=v2.num(r.get('sentiment_stress_pct'));br=v2.num(r.get('breadth_20d_pct'));ms=v2.num(r.get('market_score_pct'))
        r['box_state']=(max(-.2,min(1.2,bp))+.2)/1.4 if bp is not None else None;r['sentiment_level']=sp/100 if sp is not None else None;r['breadth_level']=br/100 if br is not None else None;r['score_level']=ms/100 if ms is not None else None
        r['sentiment_velocity']=svr[i]/100 if svr[i] is not None else None;r['breadth_velocity']=bvr[i]/100 if bvr[i] is not None else None;r['score_d1_rank']=d1r[i]/100 if d1r[i] is not None else None;r['score_d3_rank']=d3r[i]/100 if d3r[i] is not None else None;out.append(r)
    return out

def baseline(rows,ti,h):
    a=[v2.num(r.get(f'fwd_{h}d')) for r in rows if int(r['_i'])+h<ti and v2.num(r.get(f'fwd_{h}d')) is not None]
    return None if not a else (median(a),sum(x>0 for x in a)/len(a))

def validate(rows,keys):
    rec=[]
    for t in rows:
        if t['date']<'2022-01-03' or vector(t,keys) is None or t.get('fwd_10d') is None:continue
        nn=neighbors(rows,t,keys)
        if len(nn)<20:continue
        x={'date':t['date']}
        for h in v2.H:
            p=distout(nn,h);b=baseline(rows,int(t['_i']),h);a=v2.num(t.get(f'fwd_{h}d'))
            if p and b and a is not None:x[h]=(p[0],p[1],b[0],b[1],a)
        rec.append(x)
    out={}
    for h in v2.H:
        a=[r[h] for r in rec if h in r]
        if not a:out[f'{h}d']={'n':0};continue
        pred=[x[0] for x in a];pp=[x[1] for x in a];base=[x[2] for x in a];bp=[x[3] for x in a];act=[x[4] for x in a];y=[1 if x>0 else 0 for x in act]
        km=mean(abs(x-z) for x,z in zip(pred,act));bm=mean(abs(x-z) for x,z in zip(base,act));kb=mean((x-z)**2 for x,z in zip(pp,y));bb=mean((x-z)**2 for x,z in zip(bp,y));sp=v2.spearman(pred,act)
        out[f'{h}d']={'n':len(a),'spearman':round(sp,4) if sp is not None else None,'direction_accuracy_pct':round(100*sum((x>0)==(z>0) for x,z in zip(pred,act))/len(a),2),'mae_improvement':round(bm-km,4),'brier_improvement':round(bb-kb,5)}
    return out

def main():
    src=json.loads(SRC.read_text(encoding='utf-8'));rows=enrich(src.get('daily') or [])
    results={name:{'features':list(keys),'validation':validate(rows,keys)} for name,keys in SETS.items()}
    out={'schema':'MARKET-STATE-BOX-V2-DIAGNOSTICS','generated_at':datetime.now(timezone.utc).isoformat(),'diagnostic_only':True,'selection_warning':'Feature sets are inspected after the first full-8D result; do not treat the best row as fresh OOS model selection.','k':40,'feature_weighting':'equal; no optimized weights','results':results}
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(results,ensure_ascii=False))
if __name__=='__main__':main()
