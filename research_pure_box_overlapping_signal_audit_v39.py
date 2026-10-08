#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,statistics
from collections import defaultdict
from pathlib import Path
import pandas as pd
import research_pure_box_core_geometry_simplicity_v13 as v13
import research_pure_box_capital_architecture_v22 as v22

EC=v13.ENTRY_COST;XC=v13.EXIT_COST
RB=.0125;CAP=.50;H=15

def pf(rs):
    w=sum(x for x in rs if x>0);l=-sum(x for x in rs if x<0)
    return w/l if l>0 else None

def independent_return(c,d,calendar,cidx,bm):
    s=str(c["symbol"]);b=bm.get(s,{}).get(d)
    if b is None:return None
    op=float(b["open"]);lo=float(c["lower"]);hi=float(c["upper"]);target=lo+.60*(hi-lo)
    if not(lo<op<target):return None
    ef=(op-lo)/(hi-lo)
    if ef>.20:return None
    start=cidx[d];px=op;reason=""
    for age in range(1,H+1):
        j=start+age-1
        if j>=len(calendar):break
        day=calendar[j];bb=bm.get(s,{}).get(day)
        if bb is None:continue
        o=float(bb["open"])
        if o<=lo:px=o;reason="stop_gap"
        elif o>=target:px=o;reason="target_gap"
        elif float(bb["low"])<=lo:px=lo;reason="stop"
        elif float(bb["high"])>=target:px=target;reason="target60"
        elif age>=H:px=float(bb["close"]);reason="time_h15"
        else:continue
        break
    return px*(1-XC)/(op*(1+EC))-1

def run(cands,calendar,bm):
    cidx={d:i for i,d in enumerate(calendar)}
    by=defaultdict(list)
    for c in cands:
        d=str(c["direct_entry_date"])
        if v13.VAL_START<=d<=v13.VAL_END and d in cidx:by[d].append(c)
    days=[d for d in calendar if v13.VAL_START<=d<=v13.VAL_END]
    cash=1.;pos={};overlaps=[];oid=0
    for d in days:
        # age + gap exits
        for s in list(pos):
            b=bm.get(s,{}).get(d)
            if b is None:continue
            p=pos[s];p["hold"]+=1;o=float(b["open"]);px=None
            if o<=p["lower"]:px=o
            elif o>=p["target"]:px=o
            if px is not None:
                proceeds=p["shares"]*px*(1-XC);cash+=proceeds
                for i in p.get("overlap_ids",[]):
                    rec=overlaps[i]
                    rec["existing_future_return_from_overlap_open"]=px*(1-XC)/rec["overlap_open"]-1
                del pos[s]

        eqo=cash;pos_open_value={}
        for s,p in pos.items():
            b=bm.get(s,{}).get(d);op=float(b["open"]) if b is not None else p["last"]
            v=p["shares"]*op;pos_open_value[s]=v;eqo+=v

        raw=[];seen=set()
        for c in sorted(by.get(d,[]),key=lambda x:(str(x["symbol"]),str(x["signal_date"]))):
            s=str(c["symbol"])
            if s in seen:continue
            seen.add(s)
            b=bm.get(s,{}).get(d)
            if b is None:continue
            op=float(b["open"]);lo=float(c["lower"]);hi=float(c["upper"]);target=lo+.60*(hi-lo)
            if not(lo<op<target):continue
            ef=(op-lo)/(hi-lo)
            if ef>.20:continue
            riskpd=1-(lo*(1-XC))/(op*(1+EC))
            if riskpd<=0:continue

            if s in pos:
                p=pos[s]
                weight=pos_open_value.get(s,0.)/eqo if eqo>0 else 0.
                head=max(0.,CAP-weight)
                ind=independent_return(c,d,calendar,cidx,bm)
                held_lo=float(p["lower"]);held_hi=float(p["upper"])
                material=(abs(lo-held_lo)/max(abs(held_lo),1e-12)>.01 or
                          abs(hi-held_hi)/max(abs(held_hi),1e-12)>.01)
                rec={
                  "overlap_id":oid,"date":d,"year":d[:4],"symbol":s,
                  "existing_age":int(p["hold"]),"existing_weight":weight,
                  "cap_headroom":head,"overlap_open":op,
                  "new_entry_fraction":ef,"new_box_width_pct":(hi-lo)/op,
                  "new_stop_risk":riskpd,"materially_different_box":bool(material),
                  "ignored_independent_h15_return":ind,
                  "existing_future_return_from_overlap_open":None,
                  "held_entry_price":float(p["entry_price"]),
                  "held_lower":held_lo,"held_upper":held_hi,
                  "new_lower":lo,"new_upper":hi
                }
                overlaps.append(rec);p.setdefault("overlap_ids",[]).append(oid);oid+=1
                continue

            rq=min(RB*eqo/riskpd,CAP*eqo)
            raw.append({**c,"symbol":s,"entry_price":op,"lower":lo,"upper":hi,"target":target,
                        "entry_fraction":ef,"risk_per_dollar":riskpd,"request":rq})
        raw.sort(key=lambda x:(x["liquidity_rank"],x["entry_fraction"],x["symbol"]))
        rem=cash
        for x in raw:
            amt=min(x["request"],rem) if rem>0 else 0.
            rem-=amt
            if amt<=1e-12:continue
            invest=amt*(1-EC);cash-=amt
            pos[x["symbol"]]={**x,"shares":invest/x["entry_price"],"cost_basis":amt,
                              "hold":1,"last":x["entry_price"],"overlap_ids":[]}

        # intraday exits
        for s in list(pos):
            p=pos[s];b=bm.get(s,{}).get(d)
            if b is None:continue
            lo=float(b["low"]);hi=float(b["high"]);cl=float(b["close"]);px=None
            if lo<=p["lower"]:px=p["lower"]
            elif hi>=p["target"]:px=p["target"]
            elif p["hold"]>=H:px=cl
            if px is not None:
                proceeds=p["shares"]*px*(1-XC);cash+=proceeds
                for i in p.get("overlap_ids",[]):
                    rec=overlaps[i]
                    rec["existing_future_return_from_overlap_open"]=px*(1-XC)/rec["overlap_open"]-1
                del pos[s]
            else:p["last"]=cl
    return pd.DataFrame(overlaps)

def age_bucket(a):
    if a<=5:return "age01_05"
    if a<=10:return "age06_10"
    return "age11_15"

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--indir",required=True);ap.add_argument("--outdir",required=True);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig,cal,idx,nxt,bm=v13.load(a.indir)
    cs=v22.bottom20(v13.strict_signals(sig,500,cal,idx,nxt,bm))
    df=run(cs,cal,bm)
    if not df.empty:
        df["age_bucket"]=df.existing_age.map(age_bucket)
        df["beats_continuation"]=df.ignored_independent_h15_return>df.existing_future_return_from_overlap_open
    df.to_csv(out/"overlaps.csv",index=False)
    rs=df.ignored_independent_h15_return.dropna().tolist() if not df.empty else []
    summary={
      "schema":"PURE-BOX-SIMPLE-CORE-OVERLAPPING-SIGNAL-AUDIT-V39",
      "overlap_count":int(len(df)),
      "unique_symbols":int(df.symbol.nunique()) if len(df) else 0,
      "age_buckets":{str(k):int(v) for k,v in df.age_bucket.value_counts().sort_index().items()} if len(df) else {},
      "mean_ignored_return":float(statistics.mean(rs)) if rs else None,
      "median_ignored_return":float(statistics.median(rs)) if rs else None,
      "profit_factor":pf(rs) if rs else None,
      "win_rate":sum(x>0 for x in rs)/len(rs) if rs else None,
      "positive_cap_headroom_share":float((df.cap_headroom>0).mean()) if len(df) else None,
      "mean_cap_headroom":float(df.cap_headroom.mean()) if len(df) else None,
      "material_box_difference_share":float(df.materially_different_box.mean()) if len(df) else None,
      "beats_continuation_share":float(df.beats_continuation.dropna().mean()) if len(df) else None,
      "year":{str(k):int(v) for k,v in df.year.value_counts().sort_index().items()} if len(df) else {},
      "top_symbol_counts":{str(k):int(v) for k,v in df.symbol.value_counts().head(10).items()} if len(df) else {}
    }
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))
    if len(df):print(df.to_string(index=False))
if __name__=="__main__":main()
