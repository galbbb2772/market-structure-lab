#!/usr/bin/env python3
import argparse,json
from pathlib import Path
import pandas as pd

ap=argparse.ArgumentParser()
ap.add_argument("--indir",required=True)
ap.add_argument("--outdir",required=True)
a=ap.parse_args()
src=Path(a.indir);out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)

summary={"schema":"PURE-BOX-INTEGRITY-V1","lanes":{}}
annual=[];receipts=[]
for cap in (300,500):
    files=list(src.glob(f"**/summary_top{cap}.json"))
    if not files:raise RuntimeError(f"missing top{cap} summary")
    d=json.loads(files[0].read_text())
    summary["lanes"][f"top{cap}"]=d["lanes"]
    af=list(src.glob(f"**/annual_integrity_top{cap}.csv"))
    rf=list(src.glob(f"**/feature_year_receipt_top{cap}.csv"))
    annual.append(pd.read_csv(af[0]))
    receipts.append(pd.read_csv(rf[0]))

pd.concat(annual,ignore_index=True).to_csv(out/"annual_integrity.csv",index=False)
pd.concat(receipts,ignore_index=True).to_csv(out/"feature_year_receipt.csv",index=False)
(out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
print(json.dumps(summary,indent=2))
