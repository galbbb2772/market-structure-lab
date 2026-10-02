"""Cross-era robust regime-gate selection with 2020+ as untouched holdout.

A gate is eligible only if it shows positive 20d regime-adjusted excess return and
positive excess up-rate in BOTH 1992-2009 and 2010-2019, with a minimum event count
in each era. Among eligible gates we maximize the WORST of the two era excess returns.
This favors stability rather than the single strongest pooled historical result.
"""
from __future__ import annotations

import json
from pathlib import Path

import research_updown_divergence_events as base
import research_updown_divergence_regime as reg
import research_updown_divergence_regime_gate_oos as gate

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "docs/data/structure_lab.json"
OOS_PATH = ROOT / "docs/data/updown_divergence_oos.json"
OUT_PATH = ROOT / "docs/data/updown_divergence_regime_gate_robust.json"
PERIODS = {
    "ERA_A_1992_2009": ("1992-01-02", "2009-12-31"),
    "ERA_B_2010_2019": ("2010-01-01", "2019-12-31"),
    "HOLDOUT_2020_PLUS": ("2020-01-01", None),
}
MIN_EVENTS_PER_TRAIN_ERA = 6


def gate_summary_for_period(bars, feat, labels, threshold, start, end, gates):
    mkt = gate.period_market_idx(bars, labels, start, end)
    sig = gate.signal_idx(bars, feat, labels, threshold, start, end)
    out = {}
    for name, fn in gates.items():
        out[name] = gate.summarize_gate(bars, sig, mkt, lambda i, fn=fn: fn(i, labels))
    return {"signal_events": len(sig), "grid": out}


def choose_robust(periods):
    a = periods["ERA_A_1992_2009"]["grid"]
    b = periods["ERA_B_2010_2019"]["grid"]
    candidates = []
    for name in a:
        ra, rb = a[name], b[name]
        ha = ra["forward"]["20"]
        hb = rb["forward"]["20"]
        sa = ha.get("signal", {})
        sb = hb.get("signal", {})
        if ra["signal_events"] < MIN_EVENTS_PER_TRAIN_ERA or rb["signal_events"] < MIN_EVENTS_PER_TRAIN_ERA:
            continue
        ea, eb = ha.get("excess_avg_return_pct"), hb.get("excess_avg_return_pct")
        ua, ub = ha.get("excess_up_rate_pp"), hb.get("excess_up_rate_pp")
        if None in (ea, eb, ua, ub):
            continue
        if ea <= 0 or eb <= 0 or ua <= 0 or ub <= 0:
            continue
        score = min(ea, eb)
        candidates.append((score, min(ua, ub), (ea + eb) / 2, name))
    if not candidates:
        return None, []
    candidates.sort(reverse=True)
    return candidates[0][3], [
        {"gate": x[3], "worst_era_excess_return_pct": x[0], "worst_era_excess_up_rate_pp": x[1], "avg_two_era_excess_return_pct": round(x[2], 3)}
        for x in candidates
    ]


def main():
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    oos = json.loads(OOS_PATH.read_text(encoding="utf-8"))
    gates = gate.gate_defs()
    out = {
        "schema": "UPDOWN-DIVERGENCE-ROBUST-REGIME-GATE-V1",
        "method": {
            "signal_threshold": "locked from original 1992-2009 signal study",
            "training_eras": ["1992-2009", "2010-2019"],
            "holdout": "2020+",
            "candidate_gates": list(gates),
            "eligibility": f">={MIN_EVENTS_PER_TRAIN_ERA} events in each training era; positive 20d excess return and excess up-rate in each era",
            "selection": "maximize the minimum 20d excess return across the two training eras; 2020+ is not used for selection",
        },
        "results": {},
    }

    for sym in base.SYMBOLS:
        inst = raw.get("instruments", {}).get(sym)
        threshold = oos.get("results", {}).get(sym, {}).get("selected_threshold_from_IS")
        if not inst:
            out["results"][sym] = {"error": "missing"}
            continue
        if threshold is None:
            out["results"][sym] = {"name": inst.get("name", sym), "locked_signal_threshold": None, "selected_gate": None, "reason": "No locked signal threshold."}
            print(sym, "SKIP no signal threshold", flush=True)
            continue

        bars = base.load_bars(inst)
        feat = base.features(bars)
        labels = reg.compute_regimes(bars)
        periods = {}
        for pname, (start, end) in PERIODS.items():
            periods[pname] = gate_summary_for_period(bars, feat, labels, threshold, start, end, gates)

        selected, ranking = choose_robust(periods)
        holdout = periods["HOLDOUT_2020_PLUS"]["grid"].get(selected) if selected else None
        out["results"][sym] = {
            "name": inst.get("name", sym),
            "locked_signal_threshold": threshold,
            "selected_gate": selected,
            "eligible_gate_ranking": ranking,
            "periods": periods,
            "locked_gate_holdout": holdout,
        }

        print("\n", sym, inst.get("name", sym), "selected", selected, flush=True)
        if ranking:
            print(" eligible", ranking, flush=True)
        if selected:
            for pname in PERIODS:
                r = periods[pname]["grid"][selected]
                h = r["forward"]["20"]
                print(" ", pname, "n", r["signal_events"], "avg", h["signal"].get("avg_return_pct"), "ex", h.get("excess_avg_return_pct"), "up_ex", h.get("excess_up_rate_pp"), flush=True)

    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Wrote", OUT_PATH, flush=True)


if __name__ == "__main__":
    main()
