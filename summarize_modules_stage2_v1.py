from __future__ import annotations
import json
from pathlib import Path

SRC=Path('docs/data/modules_stage2_v1.json')
OUT=Path('docs/data/modules_stage2_v1_summary.json')


def slim_summary(x):
    return {k:v for k,v in x.items() if k in ('n','5d','10d','20d')}


def module(name,d):
    x=d[name]
    reg={}
    for rk,rv in (x.get('regime') or {}).items():
        reg[rk]={k:slim_summary(v) for k,v in rv.items()}
    stability=[]
    for c in x.get('stability_grid') or []:
        e=c.get('events') or {}
        stability.append({'label':c.get('label'),'n':e.get('n'),'clusters20':c.get('independent_clusters_20'),'5d':e.get('5d'),'10d':e.get('10d'),'20d':e.get('20d')})
    out={
        'center':slim_summary(x.get('center') or {}),
        'independent_clusters_20':x.get('independent_clusters_20'),
        'placebo_10d':x.get('placebo_10d'),
        'matched_control':(x.get('matched_control') or {}).get('aggregate'),
        'matched_control_unique_dates':(x.get('matched_control') or {}).get('unique_control_dates'),
        'regime':reg,
        'stability_grid':stability,
    }
    return out


def main():
    d=json.loads(SRC.read_text(encoding='utf-8'))
    out={
        'schema':'CROSS-MODULE-STAGE2-SUMMARY-V1',
        'source_schema':d.get('schema'),
        'generated_at':d.get('generated_at'),
        'research_only':True,
        'production_effect':'none',
        'coverage':d.get('coverage'),
        'box':module('box',d),
        'sentiment':module('sentiment',d),
        'breadth':module('breadth',d),
        'score':module('score',d),
        'concentration':{'results':[{k:r.get(k) for k in ('symbol','name','source_start','source_end','target_n','evaluated_n','5d','10d')} for r in d['concentration']['results']]},
    }
    out['score']['rank_ic']=d['score'].get('rank_ic')
    out['score']['score_percentile_deciles']={k:{'n':v.get('n'),'5d':v.get('5d'),'10d':v.get('10d'),'20d':v.get('20d')} for k,v in (d['score'].get('score_percentile_deciles') or {}).items()}
    out['breadth']['existing_independent_divergence_validation']=d['breadth'].get('existing_independent_divergence_validation')
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:{'n':out[k]['center']['n'],'10d':out[k]['center']['10d'],'placebo':out[k]['placebo_10d'],'matched':out[k]['matched_control']['10d']} for k in ('box','sentiment','breadth','score')},ensure_ascii=False))

if __name__=='__main__':main()
