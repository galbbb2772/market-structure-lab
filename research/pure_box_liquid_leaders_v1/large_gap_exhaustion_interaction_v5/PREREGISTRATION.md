# Large Gap Tail × Stock Exhaustion V5 — Preregistration

Status: mechanism research only. No production or forward-shadow changes.

## Motivation
Selloff Anatomy V2 showed a robust association between signal-day gap_component and later Large-box mean reversion.
Gap Repricing V3 showed that gap-down sign alone is not the mechanism.
Gap Tail Exclusion V4 showed that the deepest overnight gap tail is poor in aggregate and exclusion improves drawdown / trade economics, but the tail is not uniformly bad every year: it recovers in some later periods, including 2025 and 2026Q1.

Therefore the next question is not whether to blindly exclude deep gaps.
It is whether confirmation-day STOCK exhaustion can distinguish:
- persistent repricing / continuation,
from
- an extreme gap that has already exhausted and begun reverting.

## Frozen trade setup
- Top500 primary / Top300 robustness
- Large only
- Fresh age <=24 Top500 / <=23 Top300
- signal close in bottom 20% of active box
- no_new_low_green confirmation
- enter following-session open
- lower-edge stop
- target 60% primary / 80% robustness
- max hold 20 sessions
- 5 bps each side
- normalized 10% allocation for portfolio diagnostics

## Gap-tail definition
Primary:
- expanding prior-history 20th percentile of signal-day gap_component;
- separately estimated for Top300 and Top500;
- test years 2021..2026;
- threshold for year Y uses only candidate observations from years < Y.

Robustness:
- fixed gap_component <= -1.0%.

## Frozen stock-exhaustion variables
Measured on confirmation-date close; definitions from Strategy Reconstruction V1:

1. rebound_from_low_box
   = (confirmation close - min(signal low, confirmation low)) / box width
   Higher = stronger reclaim away from the low.

2. low_progress_box
   = (confirmation low - signal low) / box width
   Higher = stronger refusal to extend the low.

## Exhaustion thresholds
For each test year Y and rank cap separately:
- use only confirmed Fresh Large candidates from years < Y;
- compute the median of each stock-exhaustion feature;
- STRONG = feature > prior-history median
- WEAK = feature <= prior-history median

No outcome data from year Y may enter its threshold.

Median is predeclared to avoid choosing a favorable extreme quintile and to preserve sample size inside the gap tail.

## Predeclared interaction lanes
For each gap definition and each stock-exhaustion feature:

1. EXTREME_GAP + STRONG_EXHAUSTION
2. EXTREME_GAP + WEAK_EXHAUSTION
3. NON_EXTREME + STRONG_EXHAUSTION
4. NON_EXTREME + WEAK_EXHAUSTION

## Primary hypothesis
Within EXTREME_GAP observations:
STRONG_EXHAUSTION > WEAK_EXHAUSTION.

If this ordering holds, deep overnight gaps are not automatically rejected; they require stronger evidence that stock-level selling has actually exhausted.

Secondary descriptive comparison:
EXTREME_GAP + STRONG_EXHAUSTION versus NON_EXTREME + STRONG_EXHAUSTION.

## Metrics
For Top300 / Top500 and 60% / 80% exits:
- yearly N
- mean / median trade
- PF
- target / stop / max-hold shares
- MFE / MAE
- compounded yearly portfolio return
- MDD / Sharpe / exposure
- yearly ordering count

## Support standard
The interaction is supported only if:
- EXTREME+STRONG beats EXTREME+WEAK in a majority of test years;
- aggregate event mean and PF are higher;
- portfolio compounded return is higher;
- Top300 and Top500 agree;
- 60% and 80% exits agree;
- expanding-tail and fixed -1% definitions broadly agree.

No new entry rule is promoted from V5 alone.
