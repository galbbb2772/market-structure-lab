"""Cross-module Stage-2 validation factory V1.

Research-only diagnostics for Box, sentiment, breadth, composite score, and
historical streak/concentration analogs. This does not alter any production rule
or frozen Forward-OOS ledger.
"""
from __future__ import annotations

import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

import run_concentration_v1 as conc

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "docs/data/market_state_box_v1.json"
STRUCT = ROOT / "docs/data/structure_lab.json"
BREADTH_OOS = ROOT / "docs/data/updown_divergence_regime_gate_robust.json"
OUT = ROOT / "docs/data/modules_stage2_v1.json"
SEED = 240205
H = (5, 10, 20)


def num(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def avg(xs):
    a = [num(x) for x in xs]
    a = [x for x in a if x is not None]
    return mean(a) if a else None


def qtile(xs, p):
    a = sorted(x for x in (num(v) for v in xs) if x is not None)
    if not a:
        return None
    z = (len(a) - 1) * p
    i = int(z)
    j = min(i + 1, len(a) - 1)
    f = z - i
    return a[i] + (a[j] - a[i]) * f


def rankdata(vals):
    pairs = sorted((float(v), i) for i, v in enumerate(vals))
    out = [0.0] * len(vals)
    p = 0
    while p < len(pairs):
        q = p + 1
        while q < len(pairs) and pairs[q][0] == pairs[p][0]:
            q += 1
        rank = ((p + 1) + q) / 2.0
        for _, i in pairs[p:q]:
            out[i] = rank
        p = q
    return out


def pearson(x, y):
    if len(x) < 3 or len(y) != len(x):
        return None
    mx, my = mean(x), mean(y)
    dx = [v - mx for v in x]
    dy = [v - my for v in y]
    den = math.sqrt(sum(v * v for v in dx) * sum(v * v for v in dy))
    return None if den == 0 else sum(a * b for a, b in zip(dx, dy)) / den


def spearman_xy(x, y):
    pairs = [(num(a), num(b)) for a, b in zip(x, y)]
    pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
    if len(pairs) < 3:
        return {"n": len(pairs), "rho": None}
    rho = pearson(rankdata([a for a, _ in pairs]), rankdata([b for _, b in pairs]))
    return {"n": len(pairs), "rho": None if rho is None else round(rho, 4)}


def enrich(rows):
    out = [dict(r) for r in rows]
    closes = [num(r.get("sp500_close")) for r in out]
    rets = [None]
    for i in range(1, len(closes)):
        a, b = closes[i - 1], closes[i]
        rets.append(None if a in (None, 0) or b is None else b / a - 1.0)
    for i, r in enumerate(out):
        r["_i"] = i
        c = closes[i]
        if c is not None and i >= 20 and closes[i - 20] not in (None, 0):
            r["s2_ret20_pct"] = 100.0 * (c / closes[i - 20] - 1.0)
        else:
            r["s2_ret20_pct"] = None
        if i >= 20:
            w = [x for x in rets[i - 19:i + 1] if x is not None]
            if len(w) == 20:
                m = mean(w)
                var = sum((x - m) ** 2 for x in w) / (len(w) - 1)
                r["s2_rv20_pct"] = math.sqrt(var) * math.sqrt(252) * 100.0
            else:
                r["s2_rv20_pct"] = None
        else:
            r["s2_rv20_pct"] = None
        if i >= 199 and c is not None:
            w = [x for x in closes[i - 199:i + 1] if x is not None]
            ma = mean(w) if len(w) == 200 else None
            r["s2_price_regime"] = None if ma is None else ("above200" if c >= ma else "below200")
        else:
            r["s2_price_regime"] = None
        r["s2_vol_regime"] = None if num(r.get("s2_rv20_pct")) is None else ("high_ge20" if r["s2_rv20_pct"] >= 20 else "low_lt20")
        if c is not None and i + 20 < len(out) and closes[i + 20] is not None:
            r["fwd_20d"] = 100.0 * (closes[i + 20] / c - 1.0)
        elif "fwd_20d" not in r:
            r["fwd_20d"] = None
        score_hist = [num(out[j].get("market_score_pct")) for j in range(max(0, i - 9), i + 1)]
        score_hist = [x for x in score_hist if x is not None]
        r["s2_score_min10_pct"] = min(score_hist) if score_hist else None
    return out


def event_onsets(rows, predicate, gap=5):
    events = []
    last = -10**9
    prev = False
    for i, r in enumerate(rows):
        cur = bool(predicate(r))
        if cur and not prev and i - last >= gap:
            events.append(r)
            last = i
        prev = cur
    return events


def summary(events):
    out = {"n": len(events)}
    for h in H:
        vals = [num(r.get(f"fwd_{h}d")) for r in events]
        vals = [x for x in vals if x is not None]
        out[f"{h}d"] = {"n": len(vals)} if not vals else {
            "n": len(vals),
            "mean_pct": round(mean(vals), 4),
            "median_pct": round(median(vals), 4),
            "positive_pct": round(100.0 * sum(x > 0 for x in vals) / len(vals), 2),
            "p10_pct": round(qtile(vals, 0.10), 4),
            "p90_pct": round(qtile(vals, 0.90), 4),
        }
    return out


def cluster_count(events, gap=20):
    idx = sorted(int(r["_i"]) for r in events)
    if not idx:
        return 0
    n = 1
    last = idx[0]
    for i in idx[1:]:
        if i - last > gap:
            n += 1
        last = i
    return n


def regime_split(events):
    out = {}
    for key in ("s2_price_regime", "s2_vol_regime"):
        vals = sorted(set(r.get(key) for r in events if r.get(key)))
        out[key] = {v: summary([r for r in events if r.get(key) == v]) for v in vals}
    return out


def year_sensitivity(events):
    years = sorted(set(r["date"][:4] for r in events))
    by_year = {y: summary([r for r in events if r["date"].startswith(y)]) for y in years}
    excl = {y: summary([r for r in events if not r["date"].startswith(y)]) for y in years}
    return {"by_year": by_year, "leave_one_year_out": excl}


def placebo(events, rows, predicate, rounds=5000):
    n = len(events)
    actual = [num(r.get("fwd_10d")) for r in events]
    actual = [x for x in actual if x is not None]
    eligible = [r for r in rows if num(r.get("fwd_10d")) is not None and not predicate(r)]
    if not actual or n == 0 or len(eligible) < n:
        return {"rounds": rounds, "n": n, "empirical_one_sided_p": None}
    actual_mean = mean(actual)
    rng = random.Random(SEED + n)
    sims = []
    for _ in range(rounds):
        s = rng.sample(eligible, n)
        sims.append(mean(num(r.get("fwd_10d")) for r in s))
    ge = sum(x >= actual_mean for x in sims)
    return {
        "rounds": rounds,
        "n": n,
        "actual_10d_mean_pct": round(actual_mean, 4),
        "placebo_mean_pct": round(mean(sims), 4),
        "placebo_p95_pct": round(qtile(sims, 0.95), 4),
        "actual_percentile": round(100.0 * sum(x <= actual_mean for x in sims) / len(sims), 2),
        "empirical_one_sided_p": round((ge + 1) / (rounds + 1), 5),
    }


def feature_scales(rows, features):
    scales = {}
    for f in features:
        vals = [num(r.get(f)) for r in rows]
        vals = [x for x in vals if x is not None]
        if len(vals) < 10:
            scales[f] = None
            continue
        q1, q3 = qtile(vals, 0.25), qtile(vals, 0.75)
        s = (q3 - q1) if q1 is not None and q3 is not None else None
        scales[f] = s if s and s > 1e-9 else max(1.0, abs(mean(vals)))
    return scales


def matched_control(events, rows, predicate, features, k=5):
    scales = feature_scales(rows, features)
    event_idx = [int(r["_i"]) for r in events]
    used_dates = []
    records = []
    for e in events:
        ei = int(e["_i"])
        er = e.get("s2_price_regime")
        candidates = []
        for r in rows:
            ri = int(r["_i"])
            if predicate(r) or num(r.get("fwd_20d")) is None:
                continue
            if any(abs(ri - x) <= 20 for x in event_idx):
                continue
            if er and r.get("s2_price_regime") and r.get("s2_price_regime") != er:
                continue
            ss = 0.0
            used = 0
            for f in features:
                a, b, sc = num(e.get(f)), num(r.get(f)), scales.get(f)
                if a is None or b is None or not sc:
                    continue
                d = (a - b) / sc
                ss += d * d
                used += 1
            if used >= 3:
                candidates.append((math.sqrt(ss / used), r, used))
        candidates.sort(key=lambda z: z[0])
        picked = candidates[:k]
        if not picked:
            continue
        ctrls = [r for _, r, _ in picked]
        used_dates.extend(r["date"] for r in ctrls)
        rec = {"event_date": e["date"], "controls": [{"date": r["date"], "distance": round(d, 4), "features_used": u} for d, r, u in picked]}
        for h in H:
            ev = num(e.get(f"fwd_{h}d"))
            cv = [num(r.get(f"fwd_{h}d")) for r in ctrls]
            cv = [x for x in cv if x is not None]
            rec[f"event_{h}d_pct"] = ev
            rec[f"control_mean_{h}d_pct"] = None if not cv else round(mean(cv), 4)
            rec[f"lift_{h}d_pp"] = None if ev is None or not cv else round(ev - mean(cv), 4)
        records.append(rec)
    agg = {}
    for h in H:
        vals = [num(r.get(f"lift_{h}d_pp")) for r in records]
        vals = [x for x in vals if x is not None]
        agg[f"{h}d"] = {"n": len(vals)} if not vals else {
            "n": len(vals), "mean_lift_pp": round(mean(vals), 4), "median_lift_pp": round(median(vals), 4),
            "positive_lift_pct": round(100.0 * sum(x > 0 for x in vals) / len(vals), 2),
        }
    return {"features": features, "controls_per_event": k, "unique_control_dates": len(set(used_dates)), "aggregate": agg, "records": records}


def common_module(rows, center_pred, grid, match_features):
    events = event_onsets(rows, center_pred)
    stability = []
    for label, pred in grid:
        ev = event_onsets(rows, pred)
        stability.append({"label": label, "events": summary(ev), "independent_clusters_20": cluster_count(ev, 20)})
    return {
        "center": summary(events),
        "independent_clusters_20": cluster_count(events, 20),
        "regime": regime_split(events),
        "year_sensitivity": year_sensitivity(events),
        "placebo_10d": placebo(events, rows, center_pred),
        "matched_control": matched_control(events, rows, center_pred, match_features),
        "stability_grid": stability,
    }


def box_module(rows):
    def pred(t):
        return lambda r: num(r.get("box_position")) is not None and num(r.get("box_position")) <= t
    return common_module(
        rows, pred(0.25), [(str(t), pred(t)) for t in (0.15, 0.25, 0.35)],
        ["s2_ret20_pct", "s2_rv20_pct", "sentiment_stress_pct", "breadth_20d_pct", "market_score_pct"],
    )


def sentiment_module(rows):
    def pred(t):
        return lambda r: num(r.get("sentiment_stress_pct")) is not None and num(r.get("sentiment_stress_pct")) >= t
    return common_module(
        rows, pred(80), [(str(t), pred(t)) for t in (70, 80, 90)],
        ["s2_ret20_pct", "s2_rv20_pct", "box_position", "breadth_20d_pct", "market_score_pct"],
    )


def breadth_pred(t):
    def f(r):
        vals = [num(r.get("sp500_ud20_pct")), num(r.get("nasdaq_ud20_pct")), num(r.get("dow_ud20_pct"))]
        vals = [x for x in vals if x is not None]
        return len(vals) >= 2 and sum(x <= t for x in vals) >= 2
    return f


def breadth_module(rows):
    out = common_module(
        rows, breadth_pred(20), [(str(t), breadth_pred(t)) for t in (15, 20, 25)],
        ["s2_ret20_pct", "s2_rv20_pct", "box_position", "sentiment_stress_pct", "market_score_pct"],
    )
    if BREADTH_OOS.exists():
        old = json.loads(BREADTH_OOS.read_text(encoding="utf-8"))
        refs = {}
        for sym, d in (old.get("results") or {}).items():
            refs[sym] = {"selected_gate": d.get("selected_gate"), "locked_signal_threshold": d.get("locked_signal_threshold")}
        out["existing_independent_divergence_validation"] = {
            "present": True,
            "method": (old.get("method") or {}),
            "selected": refs,
        }
    else:
        out["existing_independent_divergence_validation"] = {"present": False}
    return out


def score_pred(t):
    return lambda r: num(r.get("s2_score_min10_pct")) is not None and r["s2_score_min10_pct"] <= t and bool(r.get("score_recovering"))


def score_module(rows):
    out = common_module(
        rows, score_pred(20), [(str(t), score_pred(t)) for t in (10, 20, 30)],
        ["s2_ret20_pct", "s2_rv20_pct", "box_position", "sentiment_stress_pct", "breadth_20d_pct"],
    )
    valid = [r for r in rows if num(r.get("market_score_pct")) is not None]
    out["rank_ic"] = {f"{h}d": spearman_xy([r.get("market_score_pct") for r in valid], [r.get(f"fwd_{h}d") for r in valid]) for h in H}
    dec = {}
    for d in range(10):
        lo, hi = d * 10, (d + 1) * 10
        sample = [r for r in valid if lo <= num(r.get("market_score_pct")) < (hi if d < 9 else 100.0001)]
        dec[f"D{d+1}_{lo}_{hi}"] = summary(sample)
    out["score_percentile_deciles"] = dec
    out["definition_warning"] = "Recent-low + score-recovery event is a new diagnostic construction, not an existing production rule."
    return out


def conc_metrics(records, h):
    good = [r for r in records if r.get(f"pred_{h}") is not None and r.get(f"actual_{h}") is not None and r.get(f"base_{h}") is not None]
    if not good:
        return {"n": 0}
    pred = [r[f"pred_{h}"] for r in good]
    act = [r[f"actual_{h}"] for r in good]
    base = [r[f"base_{h}"] for r in good]
    pp = [r[f"prob_{h}"] for r in good]
    bp = [r[f"base_prob_{h}"] for r in good]
    y = [1.0 if x > 0 else 0.0 for x in act]
    return {
        "n": len(good),
        "spearman": spearman_xy(pred, act)["rho"],
        "direction_accuracy_pct": round(100.0 * sum((a > 0) == (b > 0) for a, b in zip(pred, act)) / len(good), 2),
        "baseline_direction_accuracy_pct": round(100.0 * sum((a > 0) == (b > 0) for a, b in zip(base, act)) / len(good), 2),
        "mae": round(mean(abs(a - b) for a, b in zip(pred, act)), 4),
        "baseline_mae": round(mean(abs(a - b) for a, b in zip(base, act)), 4),
        "mae_improvement": round(mean(abs(a - b) for a, b in zip(base, act)) - mean(abs(a - b) for a, b in zip(pred, act)), 4),
        "brier": round(mean((a - b) ** 2 for a, b in zip(pp, y)), 5),
        "baseline_brier": round(mean((a - b) ** 2 for a, b in zip(bp, y)), 5),
    }


def concentration_symbol(data, sym):
    bars = data["instruments"][sym]["bars"]
    m5 = conc.market5_map(data)
    rows = conc.rolling_rows(bars, m5)
    targets = []
    last_t = -10**9
    for t in rows:
        if abs(int(t.get("streak") or 0)) < 2 or t["idx"] + 10 >= len(bars):
            continue
        if t["idx"] - last_t < 5:
            continue
        if t["idx"] < 500:
            continue
        targets.append(t)
        last_t = t["idx"]
    recs = []
    for t in targets:
        ti = int(t["idx"])
        candidates = [r for r in rows if int(r["idx"]) + 10 < ti]
        candidates = [r for r in candidates if r.get("streak") and (r["streak"] > 0) == (t["streak"] > 0)]
        candidates = [r for r in candidates if abs(abs(r["streak"]) - abs(t["streak"])) <= conc.STREAK_TOL and r.get("regime") == t.get("regime")]
        ranked = sorted(((conc.distance(t, r), r) for r in candidates), key=lambda z: z[0])
        selected = []
        idxs = []
        for d, r in ranked:
            if not math.isfinite(d):
                continue
            if any(abs(int(r["idx"]) - j) < conc.DECLUSTER for j in idxs):
                continue
            selected.append(r)
            idxs.append(int(r["idx"]))
            if len(selected) >= conc.TOP_K:
                break
        baseline = [r for r in rows if int(r["idx"]) + 10 < ti and r.get("streak") == t.get("streak")]
        if len(selected) < 20 or len(baseline) < 10:
            continue
        rec = {"date": t["date"], "streak": t["streak"], "regime": t.get("regime"), "analog_n": len(selected), "baseline_n": len(baseline)}
        for h in (5, 10):
            av = [conc.outcome(bars, r, h)["ret"] for r in selected if conc.outcome(bars, r, h)]
            bv = [conc.outcome(bars, r, h)["ret"] for r in baseline if conc.outcome(bars, r, h)]
            ao = conc.outcome(bars, t, h)
            if av and bv and ao:
                rec[f"pred_{h}"] = median(av)
                rec[f"prob_{h}"] = sum(x > 0 for x in av) / len(av)
                rec[f"base_{h}"] = median(bv)
                rec[f"base_prob_{h}"] = sum(x > 0 for x in bv) / len(bv)
                rec[f"actual_{h}"] = ao["ret"]
        recs.append(rec)
    return {
        "symbol": sym,
        "target_n": len(targets),
        "evaluated_n": len(recs),
        "5d": conc_metrics(recs, 5),
        "10d": conc_metrics(recs, 10),
        "records": recs,
    }


def concentration_module():
    data = json.loads(STRUCT.read_text(encoding="utf-8"))
    syms = [s for s in conc.SYMS if s in (data.get("instruments") or {})]
    results = [concentration_symbol(data, s) for s in syms]
    return {
        "method": "strict past-only walk-forward using existing Concentration V1 distance/settings; targets abs(streak)>=2 and de-clustered 5 sessions",
        "results": results,
    }


def main():
    src = json.loads(STATE.read_text(encoding="utf-8"))
    rows = enrich(src.get("daily") or [])
    if not rows:
        raise RuntimeError("market_state_box_v1 daily history missing")
    out = {
        "schema": "CROSS-MODULE-STAGE2-V1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "diagnostic_only": True,
        "production_effect": "none",
        "thresholds_changed": False,
        "study_spec": "research/modules_stage2_v1/STUDY_SPEC.md",
        "coverage": {"start": rows[0]["date"], "end": rows[-1]["date"], "observations": len(rows)},
        "box": box_module(rows),
        "sentiment": sentiment_module(rows),
        "breadth": breadth_module(rows),
        "score": score_module(rows),
        "concentration": concentration_module(),
        "decision": {
            "may_change_production": False,
            "may_change_existing_forward_oos": False,
            "may_select_best_threshold_from_grid": False,
        },
        "warnings": [
            "Sentiment and composite score histories are reconstructed, not fully publication-time archives.",
            "Box coverage is intermittent because only point-in-time eligible boxes are used.",
            "Common event studies are historical diagnostics; they are not prospective confirmation.",
            "Concentration walk-forward is stricter than the current-date analog view but still uses a feature set designed on historical data.",
        ],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    brief = {
        "box_10d": out["box"]["center"].get("10d"),
        "sentiment_10d": out["sentiment"]["center"].get("10d"),
        "breadth_10d": out["breadth"]["center"].get("10d"),
        "score_recovery_10d": out["score"]["center"].get("10d"),
        "score_ic10": out["score"]["rank_ic"].get("10d"),
        "concentration": {r["symbol"]: r["10d"] for r in out["concentration"]["results"]},
    }
    print(json.dumps(brief, ensure_ascii=False))


if __name__ == "__main__":
    main()
