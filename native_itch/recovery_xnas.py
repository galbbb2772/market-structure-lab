#!/usr/bin/env python3
import argparse
import csv
import json
import math
import statistics
from pathlib import Path

HORIZONS = (1, 10, 30, 60, 300)

def qtile(values, q):
    xs = sorted(float(x) for x in values if math.isfinite(float(x)))
    if not xs:
        return math.nan
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return xs[lo]
    w = pos - lo
    return xs[lo] * (1 - w) + xs[hi] * w

def median(values):
    xs = [float(x) for x in values if x is not None and math.isfinite(float(x))]
    return statistics.median(xs) if xs else math.nan

def fnum(v):
    if v in (None, ""):
        return math.nan
    return float(v)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--analysis-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    src = Path(args.analysis_dir)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    summary_in = json.loads((src / "summary.json").read_text())
    cross_ns = int(summary_in["ipo_cross"]["ns"])
    cross_sec = cross_ns // 1_000_000_000
    # Auction cleanup persisted into the next wall-clock second in SPCX.
    continuous_start_sec = cross_sec + 2
    close_sec = 16 * 3600

    rows = {}
    with (src / "book_1s.csv").open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            s = int(r["second"])
            row = {
                "second": s,
                "time_et": r["time_et"],
                "mid": fnum(r["mid"]),
                "spread_bp": fnum(r["spread_bp"]),
                "bid_d20": fnum(r["bid_d20"]),
                "ask_d20": fnum(r["ask_d20"]),
                "buy_qty": fnum(r["classified_buy_qty"]),
                "sell_qty": fnum(r["classified_sell_qty"]),
                "unknown_qty": fnum(r["unknown_trade_qty"]),
            }
            rows[s] = row

    continuous = []
    for s in sorted(rows):
        if not (continuous_start_sec <= s < close_sec):
            continue
        r = rows[s]
        if not (100 <= r["mid"] <= 300):
            continue
        if not (0 <= r["spread_bp"] <= 300):
            continue
        buy = r["buy_qty"] * r["mid"]
        sell = r["sell_qty"] * r["mid"]
        classified = buy + sell
        signed = buy - sell
        abs_signed = abs(signed)
        purity = max(buy, sell) / classified if classified > 0 else math.nan
        total_proxy = classified + r["unknown_qty"] * r["mid"]
        coverage = classified / total_proxy if total_proxy > 0 else math.nan
        continuous.append({
            **r,
            "buy_notional_proxy": buy,
            "sell_notional_proxy": sell,
            "classified_notional_proxy": classified,
            "signed_notional_proxy": signed,
            "abs_signed_notional_proxy": abs_signed,
            "purity": purity,
            "classification_coverage_proxy": coverage,
        })

    q98 = qtile([r["abs_signed_notional_proxy"] for r in continuous], 0.98)
    candidates = [
        r for r in continuous
        if r["abs_signed_notional_proxy"] > q98
        and math.isfinite(r["purity"])
        and r["purity"] >= 0.70
    ]
    for r in candidates:
        r["direction"] = "BUY" if r["signed_notional_proxy"] > 0 else "SELL"

    # Greedy 120-second non-max suppression. This is an XNAS-native proxy for
    # BMLL's two-minute event de-clustering, not an exact cross-venue replication.
    selected = []
    selected_seconds = []
    for r in sorted(candidates, key=lambda x: x["abs_signed_notional_proxy"], reverse=True):
        if all(abs(r["second"] - s) >= 120 for s in selected_seconds):
            selected.append(r)
            selected_seconds.append(r["second"])
    selected.sort(key=lambda x: x["second"])

    selected_set = sorted(r["second"] for r in selected)
    events = []
    for r in selected:
        s = r["second"]
        direction = r["direction"]
        depth_col = "ask_d20" if direction == "BUY" else "bid_d20"
        pre_frozen = [
            rows[t][depth_col] for t in range(s - 60, s - 9)
            if t in rows and rows[t][depth_col] > 0
        ]
        pre_full = [
            rows[t][depth_col] for t in range(s - 60, s)
            if t in rows and rows[t][depth_col] > 0
        ]
        if len(pre_frozen) < 20 or len(pre_full) < 20:
            continue

        bases = {
            "frozen_median_m60_m10": median(pre_frozen),
            "full_median_m60_m1": median(pre_full),
        }
        ev = {
            "second": s,
            "time_et": r["time_et"],
            "direction": direction,
            "abs_signed_notional_proxy": r["abs_signed_notional_proxy"],
            "purity": r["purity"],
            "classification_coverage_proxy": r["classification_coverage_proxy"],
            **bases,
        }
        next_event = min((t for t in selected_set if t > s), default=None)
        for base_name, base in bases.items():
            for h in HORIZONS:
                key = f"{base_name}_r{h}"
                if s + h in rows and base > 0:
                    ev[key] = rows[s + h][depth_col] / base
                else:
                    ev[key] = ""
                ckey = f"{base_name}_r{h}_isolated"
                if next_event is not None and next_event <= s + h:
                    ev[ckey] = ""
                else:
                    ev[ckey] = ev[key]
        events.append(ev)

    def group_stats(base_name, direction):
        es = [e for e in events if e["direction"] == direction]
        outd = {"n": len(es)}
        for h in HORIZONS:
            vals = [e[f"{base_name}_r{h}"] for e in es if e[f"{base_name}_r{h}"] != ""]
            outd[f"median_r{h}"] = median(vals)
            outd[f"pdr50_r{h}"] = (
                sum(float(v) < 0.5 for v in vals) / len(vals) if vals else math.nan
            )
        return outd

    summary = {
        "method": "XNAS-only native ITCH, venue-local midpoint, 20bp displayed depth",
        "comparability_warning": (
            "Not directly comparable in level to BMLL 13-venue SIP-midpoint depth. "
            "Use this run for same-source direction/persistence validation."
        ),
        "continuous_start_time_et": rows.get(continuous_start_sec, {}).get("time_et"),
        "q98_abs_signed_notional_proxy": q98,
        "candidate_count": len(candidates),
        "selected_event_count": len(events),
        "selected_buy_count": sum(e["direction"] == "BUY" for e in events),
        "selected_sell_count": sum(e["direction"] == "SELL" for e in events),
        "frozen_baseline": {
            "BUY": group_stats("frozen_median_m60_m10", "BUY"),
            "SELL": group_stats("frozen_median_m60_m10", "SELL"),
        },
        "full_pre_baseline": {
            "BUY": group_stats("full_median_m60_m1", "BUY"),
            "SELL": group_stats("full_median_m60_m1", "SELL"),
        },
    }

    if events:
        with (out / "xnas_recovery_events.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(events[0].keys()))
            w.writeheader()
            w.writerows(events)
    (out / "xnas_recovery_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
