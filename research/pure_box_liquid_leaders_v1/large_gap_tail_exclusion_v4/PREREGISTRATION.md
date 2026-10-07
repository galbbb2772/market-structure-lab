# Large Gap Tail Exclusion V4 — Preregistration

Status: robustness / mechanism test only. No production or forward-shadow changes.

## Motivation
Selloff Anatomy V2 showed gap_component was the only directional anatomy variable to pass all 8 checks.
Gap Repricing V3 showed the effect is NOT a simple gap<0 versus gap>=0 distinction.

The full quintile curve suggests a narrower hypothesis:
the deepest overnight gap-down tail is structurally different, while the remaining 80% does not show a stable monotonic ordering.

V4 tests only tail exclusion. It does not select a "best" middle quintile.

## Frozen Large setup
Unchanged:
- Large Fresh only
- Top500 primary / Top300 robustness
- no_new_low_green confirmation
- following-session open entry
- lower-edge stop
- 60% primary / 80% robustness target
- max hold 20 sessions
- 5 bps each side
- normalized 10% initial allocation

## Gap variable
gap_component = signal-date open / prior close - 1

Known by signal-date close.

## Primary expanding walk-forward tail
For each test year Y in 2021..2026:
- use all confirmed Fresh Large candidate gap_component observations from years < Y;
- compute the 20th percentile separately for Top300 and Top500;
- freeze that threshold before evaluating year Y;
- EXTREME_GAP_TAIL = gap_component <= prior-history 20th percentile;
- NON_EXTREME = gap_component > threshold.

No outcome data from year Y enters its threshold.

## Fixed-round robustness
Also test one predeclared round threshold:
- EXTREME_GAP_FIXED = gap_component <= -1.0%
- NON_EXTREME_FIXED = gap_component > -1.0%

This is a robustness lane only, not a parameter grid.

## Annual comparisons
For each cap and target:
1. baseline all confirmed Fresh Large
2. expanding NON_EXTREME
3. expanding EXTREME_GAP_TAIL only
4. fixed -1% NON_EXTREME
5. fixed -1% extreme tail only

Report by year:
- threshold
- candidate count
- total return
- MDD
- Sharpe
- exposure
- completed trades
- PF
- mean trade

Aggregate 2021-2026 segments:
- compounded segment return
- positive years
- average Sharpe
- worst MDD
- average exposure
- total trades

## Support standard
Tail-exclusion mechanism is supported if:
- NON_EXTREME beats baseline in risk-adjusted terms or materially reduces losses without destroying return;
- EXTREME_GAP_TAIL has worse trade economics than NON_EXTREME in most test years;
- direction is similar in Top300 / Top500;
- direction is similar at 60% / 80%;
- fixed -1% robustness broadly agrees with the expanding 20th-percentile version.

No middle quintile or alternate threshold may be selected from V4.
