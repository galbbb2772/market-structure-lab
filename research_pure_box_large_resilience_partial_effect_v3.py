#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,math
from pathlib import Path
import numpy as np
import pandas as pd

CONTROLS=[
 "relative_resilience_5d",
 "rebound_from_low_box",
 "box_width_pct",
 "box_age_sessions",
 "liquidity_rank",
 "beta60",
 "spy_ret5",
]
OUTCOMES={
 "net_return":"net_return",
 "target_indicator":"target_indicator",
 "stop_indicator":"stop_indicator",
 "mfe_return":"mfe_return",
}
FRESH={300:23,500:24}

def fit_ols(df,ycol,scales,interaction=False):
    z=df.copy()
    cols=[]
    mats=[]
    names=[]

    n0=len(z)
    for c in CONTROLS:
        mu=scales[c]["mean"]; sd=scales[c]["sd"]
        z[c+"_z"]=(pd.to_numeric(z[c],errors="coerce")-mu)/sd
    z[ycol]=pd.to_numeric(z[ycol],errors="coerce")
    need=[ycol]+[c+"_z" for c in CONTROLS]
    if interaction:
        z["res_x_rebound"]=z["relative_resilience_5d_z"]*z["rebound_from_low_box_z"]
        need.append("res_x_rebound")
    z=z.dropna(subset=need).copy()
    if len(z)<50:
        return None

    X=[np.ones(len(z))]
    names=["intercept"]
    for c in CONTROLS:
        X.append(z[c+"_z"].to_numpy(float))
        names.append(c)
    if interaction:
        X.append(z["res_x_rebound"].to_numpy(float))
        names.append("resilience_x_rebound")

    years=sorted(z.year.astype(int).unique())
    for y in years[1:]:
        X.append((z.year.astype(int).to_numpy()==y).astype(float))
        names.append(f"year_{y}")

    X=np.column_stack(X)
    y=z[ycol].to_numpy(float)
    xtx=X.T@X
    inv=np.linalg.pinv(xtx)
    b=inv@(X.T@y)
    e=y-X@b
    n,k=X.shape
    meat=X.T@((e[:,None]**2)*X)
    cov=inv@meat@inv
    if n>k:
        cov*=n/(n-k)
    se=np.sqrt(np.maximum(np.diag(cov),0))
    t=np.divide(b,se,out=np.full_like(b,np.nan),where=se>0)
    sst=float(((y-y.mean())**2).sum())
    sse=float((e**2).sum())
    r2=None if sst<=0 else 1-sse/sst
    coefs={name:{"coef":float(bb),"se_hc1":float(ss),"t":None if not np.isfinite(tt) else float(tt)}
           for name,bb,ss,tt in zip(names,b,se,t)}
    return {"n":int(n),"k":int(k),"r2":r2,"coefficients":coefs}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--indir",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    src=Path(a.indir);out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

    ff=sorted(src.glob("**/resilience_exhaustion_features_*.csv.gz"))
    oo=sorted(src.glob("**/resilience_exhaustion_outcomes_*.csv.gz"))
    if len(ff)<8 or len(oo)<8:
        raise RuntimeError(f"need 8+8 shards, got {len(ff)} {len(oo)}")
    f=pd.concat([pd.read_csv(p) for p in ff],ignore_index=True).drop_duplicates("event_id",keep="last")
    o=pd.concat([pd.read_csv(p) for p in oo],ignore_index=True)
    f["box_width_pct"]=(f.upper-f.lower)/((f.upper+f.lower)/2.0)
    f["period"]=np.where(f.year.astype(int)<=2022,"discovery","validation")
    o["target_indicator"]=o.exit_reason.astype(str).isin(["target","target_gap"]).astype(float)
    o["stop_indicator"]=o.exit_reason.astype(str).isin(["stop","stop_gap"]).astype(float)

    rows=[];scale_dump={};summary={"schema":"LARGE-RESILIENCE-PARTIAL-EFFECT-V3","lanes":{}}
    for cap in (300,500):
        ck=f"top{cap}";summary["lanes"][ck]={};scale_dump[ck]={}
        fb=f[(f.liquidity_rank<=cap)&(f.box_age_sessions<=FRESH[cap])].copy()
        for target in (.60,.80):
            tk=f"t{int(target*100)}";summary["lanes"][ck][tk]={};scale_dump[ck][tk]={}
            z=o[o.target_fraction==target].merge(fb,on="event_id",how="inner",suffixes=("","_f"))
            # normalize year after merge
            if "year_f" in z.columns:
                z["year"]=z["year_f"]
            disc=z[z.period=="discovery"].copy()
            scales={}
            for c in CONTROLS:
                s=pd.to_numeric(disc[c],errors="coerce").dropna()
                mu=float(s.mean());sd=float(s.std(ddof=0))
                if not math.isfinite(sd) or sd<=1e-12: sd=1.0
                scales[c]={"mean":mu,"sd":sd}
            scale_dump[ck][tk]=scales

            for period in ("discovery","validation"):
                p=z[z.period==period].copy()
                summary["lanes"][ck][tk][period]={}
                for outcome,ycol in OUTCOMES.items():
                    primary=fit_ols(p,ycol,scales,interaction=False)
                    inter=fit_ols(p,ycol,scales,interaction=True)
                    summary["lanes"][ck][tk][period][outcome]={
                      "primary":primary,"interaction":inter
                    }
                    if primary:
                        rr=primary["coefficients"]["relative_resilience_5d"]
                        rows.append({
                          "rank_cap":cap,"target_fraction":target,"period":period,
                          "outcome":outcome,"model":"primary","n":primary["n"],"r2":primary["r2"],
                          "resilience_coef":rr["coef"],"resilience_se_hc1":rr["se_hc1"],"resilience_t":rr["t"],
                          "interaction_coef":None,"interaction_se_hc1":None,"interaction_t":None,
                        })
                    if inter:
                        rr=inter["coefficients"]["relative_resilience_5d"]
                        ii=inter["coefficients"]["resilience_x_rebound"]
                        rows.append({
                          "rank_cap":cap,"target_fraction":target,"period":period,
                          "outcome":outcome,"model":"interaction","n":inter["n"],"r2":inter["r2"],
                          "resilience_coef":rr["coef"],"resilience_se_hc1":rr["se_hc1"],"resilience_t":rr["t"],
                          "interaction_coef":ii["coef"],"interaction_se_hc1":ii["se_hc1"],"interaction_t":ii["t"],
                        })

    pd.DataFrame(rows).to_csv(out/"coefficient_summary.csv",index=False)
    (out/"scales.json").write_text(json.dumps(scale_dump,indent=2),encoding="utf-8")

    # Compact preregistered sign audit for the primary model.
    audit=[]
    expected={"net_return":1,"target_indicator":1,"stop_indicator":-1,"mfe_return":1}
    rdf=pd.DataFrame(rows)
    for r in rdf[rdf.model=="primary"].itertuples(index=False):
        exp=expected[r.outcome]
        audit.append({
          "rank_cap":int(r.rank_cap),"target_fraction":float(r.target_fraction),
          "period":r.period,"outcome":r.outcome,
          "coef":float(r.resilience_coef),
          "se_hc1":float(r.resilience_se_hc1),
          "t":None if pd.isna(r.resilience_t) else float(r.resilience_t),
          "expected_sign":"positive" if exp>0 else "negative",
          "sign_supported":bool(r.resilience_coef*exp>0),
          "n":int(r.n),"r2":None if pd.isna(r.r2) else float(r.r2)
        })
    adf=pd.DataFrame(audit)
    adf.to_csv(out/"sign_audit.csv",index=False)
    summary["sign_audit"]=audit
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps({"schema":summary["schema"],"sign_audit":audit},indent=2))

if __name__=="__main__":
    main()
