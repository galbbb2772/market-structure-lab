# Large Gap Retest-Lift Forward OOS V1 — Preregistration

Freeze date: 2026-10-07

## Purpose
Prospectively test the frozen Top500 RETEST_LIFT mechanism with zero historical backfill and no rule changes.

## Eligibility
Only events with signal_date strictly after 2026-10-07 are eligible.

Universe:
- Top500 liquid-leader universe only.

Frozen labels:
- same EXTREME_GAP methods as V7-V9
- same RETEST and LIFT definitions as V7-V9
- expanding thresholds may update only from information available before each signal date
- no Market Regime gate
- no new technical filter
- no parameter search

## Observation lanes
Record both:
- RETEST_LIFT
- NO_RETEST_LIFT control

Keep both target-fraction views:
- 0.60
- 0.80

Keep both gap-method views:
- EXPANDING
- FIXED_-1PCT

These four views are correlated diagnostics, not four independent trials.

## Minimum evaluation gate
Do not make a promotion/rejection decision until BOTH conditions are met:
1. at least 50 closed RETEST_LIFT observations and at least 50 closed NO_RETEST_LIFT observations in the primary EXPANDING lane;
2. at least 12 calendar months have elapsed since 2026-10-07.

Before the gate is met, status remains FORWARD_OOS_PENDING.

## Frozen evaluation
At the gate, report:
- count
- mean net return
- profit factor
- win rate
- target/stop shares
- mean MFE / MAE
- symbol-balanced mean difference
- leave-one-quarter-out differences
- symbol-cluster bootstrap P(RETEST_LIFT - NO_RETEST_LIFT > 0)

## Promotion criterion
PROMOTE_CANDIDATE only if the primary EXPANDING lane satisfies all:
- RETEST_LIFT mean net return > NO_RETEST_LIFT mean net return
- RETEST_LIFT PF > NO_RETEST_LIFT PF
- symbol-balanced mean difference > 0
- every leave-one-quarter-out difference > 0
- symbol-cluster bootstrap P(diff > 0) >= 0.90

Otherwise:
- if evidence is clearly negative: REJECT_CANDIDATE
- if mixed/underpowered: EXTEND_OBSERVATION

## Anti-overfitting rule
No threshold, universe, state definition, target fraction, or gap method may be changed based on interim forward results.
Any proposed change must start a separately named hypothesis with a new freeze date.
