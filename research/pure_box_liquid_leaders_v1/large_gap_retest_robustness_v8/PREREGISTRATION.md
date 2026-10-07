# Large Gap Retest Robustness V8 — Preregistration

Date frozen: 2026-10-07

## Purpose
Falsify or strengthen the V7 Top500 finding that EXTREME_GAP events with RETEST_LIFT outperform NO_RETEST_LIFT.

This is a robustness audit, not a parameter search and not a live-trading rule.

## Frozen upstream definitions
- Universe: rank_cap=500 only for primary analysis. Top300 is retained as a negative control because V7 failed there.
- Test years: 2021-2026.
- Target fractions: 0.60 and 0.80.
- Gap methods: expanding prior-history 20th percentile and fixed -1%.
- RETEST / LIFT labels: identical to V7; all expanding thresholds use strictly prior years.
- No Market Regime gate.
- No new entry/exit tuning.

## Robustness tests
For each of four Top500 specifications:
1. Raw mean difference: RETEST_LIFT - NO_RETEST_LIFT.
2. 2.5%/97.5% winsorized mean difference.
3. Symbol-balanced mean difference (average each symbol/state first).
4. Leave-one-year-out mean differences for every 2021-2026 omission.
5. Ex-best-year mean difference.
6. Deterministic symbol-cluster bootstrap (seed 20261007, 5000 draws) for the raw mean difference.
7. 2026-only difference is reported explicitly as a recent-decay diagnostic.

## Pre-registered interpretation
A specification is BROADLY_ROBUST when:
- raw_diff > 0
- winsor_diff > 0
- symbol_balanced_diff > 0
- min_leave_one_year_out_diff > 0
- ex_best_year_diff > 0
- cluster_bootstrap_p_diff_gt_0 >= 0.90

Promotion gate:
- at least 3 of 4 Top500 specifications are BROADLY_ROBUST.

Recent-decay flag:
- if promotion gate passes but fewer than 2 of 4 specifications have 2026_diff > 0, label HISTORICAL_SUPPORT_RECENT_DECAY rather than PROMOTE.

Negative control:
- Repeat raw/winsor/symbol-balanced summaries for Top300. No requirement that Top300 pass.

No thresholds will be changed after observing V8 results.

Trigger note: workflow file is now present; this line only triggers the preregistered run and changes no test definition.
