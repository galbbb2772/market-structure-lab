#!/usr/bin/env python3
from __future__ import annotations
import json, math
from pathlib import Path
import numpy as np
import pandas as pd

SRC=Path("research/pure_box_liquid_leaders_v1/structure_decay_v1/episode_observations.csv.gz")
OUT=Path("research/pure_box_liquid_leaders_v1/structure_decay_v1/cliff_v1_1")
OUT.mkdir(parents=True,exist_ok=True)

x=pd.read_csv(SRC)
x["signal_date"]=x.signal_date.astype(str)
x["period"]=np.where(x.signal_date<="2022-12-31","discovery","validation")
x["three_plus"]=(x.touch_episodes>=3).astype(int)
x["stop20"]=(x.first_hit20=="stop").astype(int)

disc=x[x.period=="discovery"]
fresh_th={}
width_cuts={}
for s in ("small","large"):
    g=disc[disc.scale==s]
    fresh_th[s]={"age_median":float(g.age_sessions.median()),"width_median":float(g.box_width_pct.median())}
    width_cuts[s]=[float(g.box_width_pct.quantile(q)) for q in (.25,.5,.75)]

def sleeve_mask(df,name):
    if name=="all": return pd.Series(True,index=df.index)
    age=np.array([fresh_th[str(s)]["age_median"] for s in df.scale])
    fresh=df.age_sessions.to_numpy(float)<=age
    if name=="fresh": return pd.Series(fresh,index=df.index)
    width=np.array([fresh_th[str(s)]["width_median"] for s in df.scale])
    return pd.Series(fresh & (df.box_width_pct.to_numpy(float)>=width),index=df.index)

def ols(g,ycol):
    z=g[[ycol,"three_plus","age_sessions","box_width_pct","scale"]].dropna().copy()
    if len(z)<50 or z.three_plus.nunique()<2:
        return {"n":int(len(z)),"three_plus_coef":None}
    y=z[ycol].to_numpy(float)
    X=np.column_stack([np.ones(len(z)),z.three_plus.to_numpy(float),
                       np.log1p(z.age_sessions.to_numpy(float)),
                       z.box_width_pct.to_numpy(float),
                       (z.scale.astype(str)=="large").astype(float).to_numpy()])
    b=np.linalg.lstsq(X,y,rcond=None)[0]
    return {"n":int(len(z)),"three_plus_coef":float(b[1]),
            "log_age_coef":float(b[2]),"width_coef":float(b[3]),"large_coef":float(b[4])}

def age_band(v):
    v=float(v)
    if v<=4:return "0_4"
    if v<=8:return "5_8"
    if v<=12:return "9_12"
    if v<=18:return "13_18"
    return "19_plus"

def width_q(scale,v):
    cuts=width_cuts[str(scale)]
    return 1+sum(float(v)>c for c in cuts)

def matched(g):
    z=g.dropna(subset=["fwd10"]).copy()
    z["age_band"]=z.age_sessions.map(age_band)
    z["width_q"]=[width_q(s,v) for s,v in zip(z.scale,z.box_width_pct)]
    diffs=[]
    for _,c in z.groupby(["scale","age_band","width_q"]):
        a=c[c.three_plus==1];b=c[c.three_plus==0]
        if len(a)==0 or len(b)==0:continue
        w=min(len(a),len(b))
        diffs.append((w,float(a.fwd10.mean()-b.fwd10.mean()),float(a.stop20.mean()-b.stop20.mean()),len(a),len(b)))
    if not diffs:return {"matched_weight":0,"cells":0,"fwd10_diff":None,"stop_rate_diff":None}
    W=sum(d[0] for d in diffs)
    return {"matched_weight":int(W),"cells":len(diffs),
            "fwd10_diff":sum(d[0]*d[1] for d in diffs)/W,
            "stop_rate_diff":sum(d[0]*d[2] for d in diffs)/W,
            "three_plus_n":int(sum(d[3] for d in diffs)),
            "reference_n":int(sum(d[4] for d in diffs))}

result={"schema":"STRUCTURE-DECAY-CLIFF-V1.1","fresh_thresholds":fresh_th,"width_quartiles":width_cuts,"lanes":{}}
rows=[]
for cap in (300,500):
    result["lanes"][f"top{cap}"]={}
    for period in ("discovery","validation"):
        result["lanes"][f"top{cap}"][period]={}
        base=x[(x.liquidity_rank<=cap)&(x.period==period)]
        for sleeve in ("all","fresh","wide_fresh"):
            g=base[sleeve_mask(base,sleeve)]
            item={"return_model":ols(g,"fwd10"),"stop_model":ols(g,"stop20"),"matched":matched(g),
                  "n":int(len(g)),"three_plus_n":int(g.three_plus.sum())}
            result["lanes"][f"top{cap}"][period][sleeve]=item
            rows.append({"rank_cap":cap,"period":period,"sleeve":sleeve,
                         "n":item["n"],"three_plus_n":item["three_plus_n"],
                         "fwd10_three_plus_coef":item["return_model"]["three_plus_coef"],
                         "stop_three_plus_coef":item["stop_model"]["three_plus_coef"],
                         **{f"matched_{k}":v for k,v in item["matched"].items()}})
(OUT/"summary.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
pd.DataFrame(rows).to_csv(OUT/"receipt.csv",index=False)
print(json.dumps(result,indent=2))
