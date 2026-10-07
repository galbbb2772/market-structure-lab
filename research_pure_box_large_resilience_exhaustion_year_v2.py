#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd

import research_pure_box_large_market_permission_year_v1 as base
import research_pure_box_large_idio_dislocation_year_v1 as idio

TARGETS={"60":.60,"80":.80}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--year",type=int,required=True)
    ap.add_argument("--indir",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

    sig,cal,idx,nxt,bm,spy=base.load(a.indir,a.year)
    base.CALENDAR=cal
    regs=base.regime_map(spy)
    c=base.confirmed(sig,cal,idx,nxt,bm,regs)
    ci={d:i for i,d in enumerate(cal)}

    feats=[]; outcomes=[]
    for q in c.to_dict("records"):
        f=idio.feature_for(q,cal,idx,bm)
        if f is None or pd.isna(f.get("idio_dislocation_5d")):
            continue
        sm=bm.get(str(q["symbol"]),{})
        b0=sm.get(str(q["signal_date"]))
        b1=sm.get(str(q["confirmation_date"]))
        if b0 is None or b1 is None:
            continue
        lo=float(q["lower"]);hi=float(q["upper"]);width=max(hi-lo,1e-12)
        rebound=(float(b1["close"])-min(float(b0["low"]),float(b1["low"])))/width
        rel5=-float(f["idio_dislocation_5d"])
        event_id=f'{q["symbol"]}|{q["signal_date"]}|{q["confirmation_date"]}|{q["entry_date"]}'
        row={
          "event_id":event_id,"year":a.year,"symbol":q["symbol"],
          "signal_date":q["signal_date"],"confirmation_date":q["confirmation_date"],
          "entry_date":q["entry_date"],"liquidity_rank":q["liquidity_rank"],
          "box_age_sessions":q["box_age_sessions"],"lower":lo,"upper":hi,
          "relative_resilience_5d":rel5,
          "idio_dislocation_5d":float(f["idio_dislocation_5d"]),
          "beta60":float(f["beta60"]),
          "stock_ret5":float(f["stock_ret5"]),
          "spy_ret5":float(f["spy_ret5"]),
          "rebound_from_low_box":rebound,
        }
        feats.append(row)
        for label,frac in TARGETS.items():
            rr=base.event_outcome(q,bm,ci,frac)
            if rr is None:continue
            outcomes.append({
              "event_id":event_id,"target_fraction":frac,**rr
            })

    fdf=pd.DataFrame(feats).drop_duplicates("event_id",keep="last")
    odf=pd.DataFrame(outcomes)
    fdf.to_csv(out/f"resilience_exhaustion_features_{a.year}.csv.gz",index=False,compression="gzip")
    odf.to_csv(out/f"resilience_exhaustion_outcomes_{a.year}.csv.gz",index=False,compression="gzip")
    receipt={
      "schema":"LARGE-RESILIENCE-EXHAUSTION-YEAR-V2",
      "year":a.year,
      "confirmed_large":int(len(c)),
      "feature_events":int(len(fdf)),
      "outcome_rows":int(len(odf)),
    }
    (out/f"summary_{a.year}.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
    print(json.dumps(receipt,indent=2))

if __name__=="__main__":
    main()
