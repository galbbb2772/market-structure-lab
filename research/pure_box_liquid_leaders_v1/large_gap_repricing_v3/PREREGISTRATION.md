# Large Gap Repricing V3 — Preregistration

Status: mechanism research only. No production or forward-shadow changes.

## Motivation
Large Selloff Anatomy V2 found one robust directional result:
signal-date overnight gap component passed all 8 predeclared checks across Top300/500, 60/80% exits, and discovery/validation.

This follow-up does NOT reuse the V2 quintile thresholds as a new strategy rule.
It asks what economically interpretable anatomy produces that result.

## Frozen Large setup
Unchanged:
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
- 10% normalized initial allocation for portfolio diagnostics

## Signal-day decomposition
Known by signal-date close:

gap_component = signal open / prior close - 1
intraday_component = signal close / signal open - 1

## Predeclared states

### Primary binary split
1. GAP_DOWN
   gap_component < 0

2. NO_GAP_DOWN
   gap_component >= 0

Primary hypothesis:
NO_GAP_DOWN has stronger subsequent Large-box mean-reversion economics than GAP_DOWN.

### Four-state anatomy
1. GAP_DOWN_CONTINUED
   gap < 0 AND intraday_component <= 0

2. GAP_DOWN_REJECTED
   gap < 0 AND intraday_component > 0

3. NO_GAP_DOWN_SELLING
   gap >= 0 AND intraday_component < 0

4. NO_GAP_DOWN_RISING
   gap >= 0 AND intraday_component >= 0

Mechanism hypotheses:
- GAP_DOWN_REJECTED > GAP_DOWN_CONTINUED.
- NO_GAP_DOWN_SELLING > GAP_DOWN_CONTINUED.
The second comparison is the clearest proxy for intraday/liquidity selloff versus overnight-information repricing.

No magnitude threshold is optimized in V3.

## Discovery / validation
- discovery: 2019-2022
- validation: 2023-2026Q1

## Metrics
For 60% and 80% exits, Top300 and Top500:
- N
- mean / median trade
- PF
- win rate
- target / stop / max-hold shares
- mean holding sessions
- MFE / MAE
- yearly mean trade / PF

Portfolio replay per state:
- compounded segment return
- MDD
- Sharpe
- exposure
- completed trades

## Support standard
Primary binary mechanism is supported only if NO_GAP_DOWN > GAP_DOWN in:
- discovery and validation;
- Top300 and Top500;
- 60% and 80% exits;
- both event economics and portfolio economics;
- not solely one year.

Four-state mechanism support requires the predeclared ordering comparisons to agree across the same axes.

No state is promoted into a production gate from V3 alone.
