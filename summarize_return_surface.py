from __future__ import annotations

import json
from pathlib import Path

SRC = Path('docs/data/return_surface.json')
OUT = Path('docs/data/return_surface_summary.json')


def compact_cell(c):
    return {k: c.get(k) for k in [
        'i','j','n','x_bounds','y_bounds','up_pct','median','median_edge','up_edge_pp',
        'eligible_eras','positive_median_eras','positive_up_eras',
        'positive_median_era_frac','positive_up_era_frac',
        'adjacent_positive_median_neighbors','persistent_positive'
    ]}


def main():
    data = json.loads(SRC.read_text())
    out = {'schema':'RETURN-SURFACE-SUMMARY-V1','instruments':{}}
    for sym, inst in data['instruments'].items():
        by_key = {}
        for s in inst['surfaces']:
            key = f"{s['x']} × {s['y']} | T+{s['horizon']}"
            rec = by_key.setdefault(key, {'pair':[s['x'],s['y']], 'horizon':s['horizon'], 'grids':{}})
            persistent = [c for c in s['cells'] if c.get('persistent_positive')]
            persistent.sort(key=lambda c:(c.get('positive_median_era_frac') or 0,c.get('adjacent_positive_median_neighbors') or 0,c.get('median_edge') or -999), reverse=True)
            rec['grids'][str(s['grid'])] = {
                'persistent_positive_count': s['persistent_positive_count'],
                'persistent_cells': [compact_cell(c) for c in persistent[:6]],
            }
        out['instruments'][sym] = {'name':inst['name'],'n_D1':inst['n_D1'],'surfaces':by_key}
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2))

    # Print only T+5 for quick action-log inspection.
    quick = {}
    for sym, inst in out['instruments'].items():
        quick[sym] = {'name':inst['name'],'T5':{}}
        for k, s in inst['surfaces'].items():
            if s['horizon'] != 5:
                continue
            quick[sym]['T5'][k] = {
                g: {
                    'persistent_positive_count': z['persistent_positive_count'],
                    'persistent_cells': z['persistent_cells'][:2],
                } for g,z in s['grids'].items()
            }
    print(json.dumps(quick,ensure_ascii=False,indent=2))

if __name__ == '__main__':
    main()
