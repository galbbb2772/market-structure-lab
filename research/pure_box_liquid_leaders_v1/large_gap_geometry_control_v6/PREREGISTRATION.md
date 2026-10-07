# Large Gap Tail Geometry Control V6 — Preregistration

Status: mechanism audit only. No production or forward-shadow changes.

## Question
V5 found that inside the extreme overnight-gap tail, stronger confirmation-day stock exhaustion
(rebound_from_low_box or low_progress_box above the prior-history median)
was consistently WORSE than weaker confirmation.

Before interpreting this as a behavioral mechanism, V6 tests a simpler confound:
strong confirmation may mechanically lift the following-session entry price,
leaving less upside to the fixed box target and/or worse stop geometry.

## Frozen setup
Unchanged from V5:
- Large Fresh only
- Top500 primary / Top300 robustness
- no_new_low_green confirmation
- entry = session after confirmation open
- lower-edge stop
- 60% target primary / 80% robustness
- max hold 20 sessions
- 5 bps each side
- expanding gap-tail and fixed -1% gap-tail definitions from V5
- expanding prior-history medians for rebound_from_low_box and low_progress_box

## Geometry variables
Known at entry:
- entry_fraction = (entry_price - lower) / (upper - lower)
- stop_distance = (entry_price - lower) / entry_price
- target_upside_60 = (lower + 0.60 * box_width) / entry_price - 1
- target_upside_80 = (lower + 0.80 * box_width) / entry_price - 1
- rr_60 = target_upside_60 / stop_distance
- rr_80 = target_upside_80 / stop_distance

## Part A — direct confound audit
Within EXTREME_GAP, compare STRONG vs WEAK exhaustion on:
- mean entry_fraction
- mean target upside
- mean stop distance
- mean R/R

Hypothesis:
STRONG exhaustion enters higher in the box and therefore has worse remaining trade geometry.

## Part B — prior-history geometry stratification
For each test year Y, cap, gap method and exhaustion feature:
- use EXTREME_GAP candidates from years < Y;
- define entry_fraction quartile cutpoints from that prior history only;
- apply those cutpoints unchanged to year Y.

Within each test-year quartile:
- compare STRONG vs WEAK event mean return and PF.

Standardized strong-minus-weak effect:
- include only quartiles containing both groups;
- weight each quartile by min(N_strong, N_weak);
- report weighted mean-return difference;
- report number of quartiles where STRONG > WEAK.

This controls the most direct entry-location confound without optimizing a new cutoff.

## Part C — residual geometry control
For each cap / target / gap method / exhaustion feature:
- on all 2021-2026 test events, fit a simple linear diagnostic:
  net_return ~ intercept + entry_fraction + gap_component + year fixed effects + STRONG
- report the coefficient on STRONG.
- No p-value threshold is used; this is directional diagnostic only.

## Interpretation
- If V5's negative STRONG effect disappears or turns positive after entry-geometry control,
  V5 was mainly an entry-location / R:R effect.
- If STRONG remains negative after both stratification and residual control,
  deep-gap strong confirmation behaves more like a failed/violent bounce than true exhaustion.

No rule is promoted from V6 alone.
