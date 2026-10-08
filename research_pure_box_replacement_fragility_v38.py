#!/usr/bin/env python3
import json, pandas as pd
from pathlib import Path
SRC=Path("research/pure_box_liquid_leaders_v1/replacement_anatomy_v37/events.csv")
OUT=Path("research/pure_box_liquid_leaders_v1/replacement_fragility_v38")
OUT.mkdir(parents=True,exist_ok=True)
df=pd.read_csv(SRC)
p=df.dropna(subset=["pair_delta"]).copy()
vals=p.pair_delta.tolist()
signed_sum=float(sum(vals))
sv=sorted(vals,reverse=True)
def share(k):
    return float(sum(sv[:k])/signed_sum) if signed_sum else None
loo=[]
for _,r in p.iterrows():
    rem=p[p.event_id!=r.event_id].pair_delta
    loo.append({
      "event_id":int(r.event_id),"date":r.date,"displaced_symbol":r.displaced_symbol,
      "incoming_symbol":r.incoming_symbol,"pair_delta":float(r.pair_delta),
      "leave_one_out_mean":float(rem.mean()) if len(rem) else None
    })
top_sorted=p.sort_values("pair_delta",ascending=False)
def leave_top(k):
    rem=p.drop(top_sorted.head(k).index).pair_delta
    return float(rem.mean()) if len(rem) else None
year={str(y):{
    "n":int(len(g)),
    "sum_pair_delta":float(g.pair_delta.sum()),
    "mean_pair_delta":float(g.pair_delta.mean()),
    "positive_share":float((g.pair_delta>0).mean())
} for y,g in p.groupby("year")}
summary={
 "schema":"PURE-BOX-SIMPLE-CORE-REPLACEMENT-FRAGILITY-V38",
 "paired_count":int(len(p)),
 "signed_sum_pair_delta":signed_sum,
 "mean_pair_delta":float(p.pair_delta.mean()),
 "median_pair_delta":float(p.pair_delta.median()),
 "positive_pair_share":float((p.pair_delta>0).mean()),
 "top1_signed_share":share(1),
 "top2_signed_share":share(2),
 "top3_signed_share":share(3),
 "leave_top1_mean":leave_top(1),
 "leave_top2_mean":leave_top(2),
 "leave_top3_mean":leave_top(3),
 "leave_one_out":loo,
 "year":year
}
(OUT/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
pd.DataFrame(loo).to_csv(OUT/"leave_one_out.csv",index=False)
print(json.dumps(summary,indent=2))
