"""Vectorized Stage-2 walk-forward validation for Concentration V1.

Same historical definition as research/modules_stage2_v1/STUDY_SPEC.md, but the
nearest-neighbor distance calculation is vectorized so century-scale history is
tractable. Research-only; no production effect.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

import numpy as np
import run_concentration_v1 as conc

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "docs/data/structure_lab.json"
OUT = ROOT / "docs/data/concentration_stage2_walkforward_v1.json"


def rankdata(a):
    a = np.asarray(a, dtype=float)
    order = np.argsort(a, kind="mergesort")
    ranks = np.empty(len(a), dtype=float)
    i = 0
    while i < len(a):
        j = i + 1
        while j < len(a) and a[order[j]] == a[order[i]]:
            j += 1
        ranks[order[i:j]] = ((i + 1) + j) / 2.0
        i = j
    return ranks


def spearman(x, y):
    x = np.asarray(x, dtype=float); y = np.asarray(y, dtype=float)
    ok = np.isfinite(x) & np.isfinite(y)
    x = x[ok]; y = y[ok]
    if len(x) < 3:
        return None
    rx, ry = rankdata(x), rankdata(y)
    sx, sy = rx.std(), ry.std()
    if sx == 0 or sy == 0:
        return None
    return float(np.corrcoef(rx, ry)[0, 1])


def metrics(records, h):
    good = [r for r in records if all(r.get(k) is not None for k in (f"pred_{h}", f"actual_{h}", f"base_{h}", f"prob_{h}", f"base_prob_{h}"))]
    if not good:
        return {"n": 0}
    pred = np.array([r[f"pred_{h}"] for r in good], dtype=float)
    act = np.array([r[f"actual_{h}"] for r in good], dtype=float)
    base = np.array([r[f"base_{h}"] for r in good], dtype=float)
    pp = np.array([r[f"prob_{h}"] for r in good], dtype=float)
    bp = np.array([r[f"base_prob_{h}"] for r in good], dtype=float)
    y = (act > 0).astype(float)
    return {
        "n": len(good),
        "spearman": None if spearman(pred, act) is None else round(spearman(pred, act), 4),
        "direction_accuracy_pct": round(float(np.mean((pred > 0) == (act > 0))) * 100, 2),
        "baseline_direction_accuracy_pct": round(float(np.mean((base > 0) == (act > 0))) * 100, 2),
        "mae": round(float(np.mean(np.abs(pred - act))), 4),
        "baseline_mae": round(float(np.mean(np.abs(base - act))), 4),
        "mae_improvement": round(float(np.mean(np.abs(base - act)) - np.mean(np.abs(pred - act))), 4),
        "brier": round(float(np.mean((pp - y) ** 2)), 5),
        "baseline_brier": round(float(np.mean((bp - y) ** 2)), 5),
        "brier_improvement": round(float(np.mean((bp - y) ** 2) - np.mean((pp - y) ** 2)), 5),
    }


def symbol_run(data, sym, m5):
    inst = data["instruments"][sym]
    bars = inst["bars"]
    rows = conc.rolling_rows(bars, m5)
    n = len(rows)
    if not n:
        return {"symbol": sym, "evaluated_n": 0}

    idx = np.array([int(r["idx"]) for r in rows], dtype=int)
    streak = np.array([int(r.get("streak") or 0) for r in rows], dtype=int)
    regime = np.array([1 if r.get("regime") == "above200" else 0 for r in rows], dtype=int)
    weights = np.array([float(w) for _, w, _ in conc.FEATURES], dtype=float)
    scales = np.array([float(s) for _, _, s in conc.FEATURES], dtype=float)
    mat = np.full((n, len(conc.FEATURES)), np.nan, dtype=float)
    for j, (key, _, _) in enumerate(conc.FEATURES):
        for i, r in enumerate(rows):
            v = r.get(key)
            if isinstance(v, (int, float)) and math.isfinite(v):
                mat[i, j] = float(v) / scales[j]

    close = np.array([float(b[4]) for b in bars], dtype=float)
    fwd = {}
    for h in (5, 10):
        a = np.full(n, np.nan, dtype=float)
        valid = idx + h < len(close)
        a[valid] = 100.0 * (close[idx[valid] + h] / close[idx[valid]] - 1.0)
        fwd[h] = a

    targets = []
    last_idx = -10**9
    for p, r in enumerate(rows):
        ti = int(r["idx"])
        if abs(int(r.get("streak") or 0)) < 2 or ti < 500 or ti + 10 >= len(bars):
            continue
        if ti - last_idx < 5:
            continue
        targets.append(p)
        last_idx = ti

    recs = []
    for tp in targets:
        ti = idx[tp]
        ts = streak[tp]
        mask = (idx + 10 < ti) & (streak != 0) & ((streak > 0) == (ts > 0)) & (np.abs(np.abs(streak) - abs(ts)) <= conc.STREAK_TOL) & (regime == regime[tp])
        cp = np.flatnonzero(mask)
        if len(cp) < 20:
            continue
        x = mat[cp]
        t = mat[tp]
        valid = np.isfinite(x) & np.isfinite(t[None, :])
        ww = valid * weights[None, :]
        den = ww.sum(axis=1)
        diff = np.where(valid, x - t[None, :], 0.0)
        dist = np.full(len(cp), np.inf, dtype=float)
        ok = den > 0
        dist[ok] = np.sqrt((ww[ok] * diff[ok] ** 2).sum(axis=1) / den[ok])
        order = cp[np.argsort(dist, kind="stable")]
        selected = []
        selected_idx = []
        for p in order:
            if not math.isfinite(float(dist[np.where(cp == p)[0][0]])):
                continue
            ii = int(idx[p])
            if any(abs(ii - j) < conc.DECLUSTER for j in selected_idx):
                continue
            selected.append(int(p)); selected_idx.append(ii)
            if len(selected) >= conc.TOP_K:
                break
        if len(selected) < 20:
            continue
        basep = np.flatnonzero((idx + 10 < ti) & (streak == ts))
        if len(basep) < 10:
            continue
        rec = {"date": rows[tp]["date"], "streak": int(ts), "regime": rows[tp].get("regime"), "analog_n": len(selected), "baseline_n": len(basep)}
        for h in (5, 10):
            av = fwd[h][selected]; av = av[np.isfinite(av)]
            bv = fwd[h][basep]; bv = bv[np.isfinite(bv)]
            actual = fwd[h][tp]
            if len(av) and len(bv) and math.isfinite(float(actual)):
                rec[f"pred_{h}"] = float(np.median(av))
                rec[f"prob_{h}"] = float(np.mean(av > 0))
                rec[f"base_{h}"] = float(np.median(bv))
                rec[f"base_prob_{h}"] = float(np.mean(bv > 0))
                rec[f"actual_{h}"] = float(actual)
        recs.append(rec)

    return {
        "symbol": sym,
        "name": inst.get("name", sym),
        "source_start": inst.get("start"),
        "source_end": inst.get("end"),
        "target_n": len(targets),
        "evaluated_n": len(recs),
        "5d": metrics(recs, 5),
        "10d": metrics(recs, 10),
        "records": recs,
    }


def main():
    data = json.loads(SRC.read_text(encoding="utf-8"))
    m5 = conc.market5_map(data)
    results = [symbol_run(data, s, m5) for s in conc.SYMS if s in (data.get("instruments") or {})]
    out = {
        "schema": "CONCENTRATION-STAGE2-WALKFORWARD-V1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "diagnostic_only": True,
        "production_effect": "none",
        "definition": "Strict past-only Concentration V1 analog validation; abs(streak)>=2 targets, 5-session target decluster, same direction, streak tolerance 1, same MA200 regime, top40 analogs, 5-session candidate decluster.",
        "results": results,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({r["symbol"]: {"n": r["evaluated_n"], "10d": r["10d"]} for r in results}, ensure_ascii=False))


if __name__ == "__main__":
    main()
