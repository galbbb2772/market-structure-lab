"""Locked regime-gate OOS validation for the bullish divergence signal.

Signal thresholds remain those selected from 1992-2009 by the strict OOS study.
A small, pre-specified set of simple regime gates is evaluated on 1992-2019
(development period). The best gate must have >=15 events, positive 20d excess
return, and positive excess up-rate. That gate is then locked and evaluated only
on 2020+.

This makes 2020+ the clean holdout for the NEW regime filter.
"""
from __future__ import annotations

import json
from pathlib import Path

import research_updown_divergence_events as base
import research_updown_divergence_regime as reg

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "docs/data/structure_lab.json"
OOS_PATH = ROOT / "docs/data/updown_divergence_oos.json"
OUT_PATH = ROOT / "docs/data/updown_divergence_regime_gate_oos.json"
DEV_START, DEV_END = "1992-01-02", "2019-12-31"
TEST_START = "2020-01-01"
MIN_DEV_EVENTS = 15


def gate_defs():
    return {
        "ALL": lambda i, L: True,
        "ABOVE_MA200": lambda i, L: L["trend"][i] == "ABOVE_MA200",
        "BELOW_MA200": lambda i, L: L["trend"][i] == "BELOW_MA200",
        "NOT_HIGH_VOL": lambda i, L: L["vol"][i] in ("LOW_LE_30PCT", "MID_30_TO_70PCT"),
        "HIGH_VOL": lambda i, L: L["vol"][i] == "HIGH_GE_70PCT",
        "SHALLOW_DD": lambda i, L: L["drawdown"][i] == "SHALLOW_GT_-5PCT",
        "NON_SHALLOW_DD": lambda i, L: L["drawdown"][i] in ("MEDIUM_-5_TO_-10PCT", "DEEP_LE_-10PCT"),
        "ABOVE_AND_NOT_HIGH": lambda i, L: L["trend"][i] == "ABOVE_MA200" and L["vol"][i] in ("LOW_LE_30PCT", "MID_30_TO_70PCT"),
        "ABOVE_AND_SHALLOW": lambda i, L: L["trend"][i] == "ABOVE_MA200" and L["drawdown"][i] == "SHALLOW_GT_-5PCT",
        "NOT_HIGH_AND_SHALLOW": lambda i, L: L["vol"][i] in ("LOW_LE_30PCT", "MID_30_TO_70PCT") and L["drawdown"][i] == "SHALLOW_GT_-5PCT",
        "ABOVE_NOT_HIGH_SHALLOW": lambda i, L: L["trend"][i] == "ABOVE_MA200" and L["vol"][i] in ("LOW_LE_30PCT", "MID_30_TO_70PCT") and L["drawdown"][i] == "SHALLOW_GT_-5PCT",
    }


def period_market_idx(bars, labels, start, end=None):
    out = []
    for i, b in enumerate(bars):
        if b["date"] < start:
            continue
        if end and b["date"] > end:
            continue
        if labels["trend"][i] is None or labels["vol"][i] is None or labels["drawdown"][i] is None:
            continue
        out.append(i)
    return out


def signal_idx(bars, feat, labels, threshold, start, end=None):
    idx = base.extract_events(
        bars, feat, side="bull", threshold=float(threshold),
        require_corr=True, require_lead=True, start_date=start,
    )
    good = set(period_market_idx(bars, labels, start, end))
    return [i for i in idx if i in good]


def summarize_gate(bars, sig_idx, mkt_idx, pred):
    s = [i for i in sig_idx if pred(i)]
    b = [i for i in mkt_idx if pred(i)]
    return {
        "signal_events": len(s),
        "baseline_days": len(b),
        "forward": reg.summarize_bucket(bars, s, b),
    }


def choose_gate(dev_map):
    candidates = []
    for name, r in dev_map.items():
        h20 = r["forward"].get("20", {})
        sig = h20.get("signal", {})
        if r["signal_events"] < MIN_DEV_EVENTS or sig.get("n", 0) < MIN_DEV_EVENTS:
            continue
        er = h20.get("excess_avg_return_pct")
        eu = h20.get("excess_up_rate_pp")
        if er is None or eu is None or er <= 0 or eu <= 0:
            continue
        candidates.append((er, eu, name))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][2]


def main():
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    oos = json.loads(OOS_PATH.read_text(encoding="utf-8"))
    gates = gate_defs()
    out = {
        "schema": "UPDOWN-DIVERGENCE-REGIME-GATE-OOS-V1",
        "method": {
            "signal_threshold_source": "strict 1992-2009 threshold selection from updown_divergence_oos.json",
            "regime_gate_development": [DEV_START, DEV_END],
            "regime_gate_holdout": [TEST_START, "latest"],
            "candidate_gates": list(gates),
            "selection_rule": f"highest 20d excess avg return among gates with >= {MIN_DEV_EVENTS} events and positive excess avg return + excess up-rate",
            "lookahead": "none in signal/regime construction; 2020+ not used to select gate",
        },
        "results": {},
    }

    for sym in base.SYMBOLS:
        inst = raw.get("instruments", {}).get(sym)
        threshold = oos.get("results", {}).get(sym, {}).get("selected_threshold_from_IS")
        if not inst:
            out["results"][sym] = {"error": "missing instrument"}
            continue
        if threshold is None:
            out["results"][sym] = {
                "name": inst.get("name", sym),
                "locked_signal_threshold": None,
                "selected_gate": None,
                "reason": "No locked signal threshold survived the original training rule, so gate selection is skipped.",
            }
            print(sym, "SKIP: no locked signal threshold", flush=True)
            continue

        bars = base.load_bars(inst)
        feat = base.features(bars)
        labels = reg.compute_regimes(bars)
        dev_mkt = period_market_idx(bars, labels, DEV_START, DEV_END)
        test_mkt = period_market_idx(bars, labels, TEST_START, None)
        dev_sig = signal_idx(bars, feat, labels, threshold, DEV_START, DEV_END)
        test_sig = signal_idx(bars, feat, labels, threshold, TEST_START, None)

        dev_map = {}
        test_map = {}
        for name, fn in gates.items():
            dev_map[name] = summarize_gate(bars, dev_sig, dev_mkt, lambda i, fn=fn: fn(i, labels))
            test_map[name] = summarize_gate(bars, test_sig, test_mkt, lambda i, fn=fn: fn(i, labels))

        selected = choose_gate(dev_map)
        out["results"][sym] = {
            "name": inst.get("name", sym),
            "locked_signal_threshold": threshold,
            "dev_signal_events": len(dev_sig),
            "test_signal_events": len(test_sig),
            "selected_gate": selected,
            "development_grid": dev_map,
            "holdout_grid_diagnostic": test_map,
            "locked_gate_dev": dev_map.get(selected) if selected else None,
            "locked_gate_2020_plus": test_map.get(selected) if selected else None,
        }

        print("\n", sym, inst.get("name", sym), "threshold", threshold, "selected gate", selected, flush=True)
        for name in gates:
            d = dev_map[name]["forward"]["20"]
            t = test_map[name]["forward"]["20"]
            print(
                " ", name,
                "DEV n", dev_map[name]["signal_events"], "ex", d.get("excess_avg_return_pct"), "up_ex", d.get("excess_up_rate_pp"),
                "| TEST n", test_map[name]["signal_events"], "ex", t.get("excess_avg_return_pct"), "up_ex", t.get("excess_up_rate_pp"),
                flush=True,
            )

    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Wrote", OUT_PATH, flush=True)


if __name__ == "__main__":
    main()
