# Large Selloff Anatomy V2 — Preregistration

Status: mechanism research only. No production or forward-shadow changes.

## Motivation
Abnormal Selloff V1 rejected a simple monotonic rule that "the more extreme the selloff, the better the mean reversion."
A plausible reason is shock heterogeneity:
- information repricing often arrives as an overnight gap and may continue;
- liquidity / panic selling may occur intraday and be more mean-reverting;
- the same total decline can therefore have different economics.

V2 studies HOW the signal-date selloff occurred, not how large it was in aggregate.

## Frozen Large setup
Unchanged:
- Top500 primary / Top300 robustness
- Large only
- Fresh age <=24 Top500 / <=23 Top300
- signal close in bottom 20% of box
- no_new_low_green confirmation
- following-session open entry
- lower-edge stop
- primary target = 60% box
- robustness target = 80% box
- max hold = 20 sessions
- 5 bps each side
- normalized 10% initial allocation for portfolio diagnostics

All anatomy variables are known by SIGNAL-DATE close.

## Predeclared selloff-anatomy variables

1. gap_component
   = signal open / prior close - 1
   More negative = more overnight repricing.

2. intraday_component
   = signal close / signal open - 1
   More negative = more same-session selling after the open.

3. close_recovery_from_low
   = (signal close - signal low) / max(signal high - signal low, epsilon)
   Higher = price rejected the intraday low before the close.

4. downside_wick_fraction
   = (min(signal open, signal close) - signal low) / signal range
   Higher = larger lower wick / stronger intraday rejection.

5. volume_ratio20
   = signal volume / median volume of prior 20 sessions
   Higher = larger participation shock.

6. gap_share_of_negative_move
   For observations with total 1d return < 0:
   = abs(min(gap_component,0)) / [abs(min(gap_component,0)) + abs(min(intraday_component,0)) + epsilon]
   Higher = more of the negative move came through the overnight gap.
   Directional hypothesis: LOWER should be more mean-reverting.

## Primary hypotheses
- close_recovery_from_low: higher is better.
- downside_wick_fraction: higher is better.
- gap_share_of_negative_move: lower is better.
- gap_component: less-negative / smaller gap damage is better, conditional on reaching the box.
- volume_ratio20 and intraday_component are descriptive; no monotonic claim is promoted in advance.

## Discovery / validation
Discovery: 2019-2022.
Validation: 2023-2026Q1.

For each Top300 / Top500 universe:
- discovery defines quintiles for each variable;
- fixed cutpoints are applied unchanged to validation.

## Metrics
For 60% and 80% exits:
- Spearman(feature, net trade return)
- quintile N / mean / median trade / PF
- target / stop / max-hold shares
- holding sessions / MFE / MAE
- Q1 vs Q5 portfolio replay under normalized 10% sizing

For inverse-direction hypotheses (gap_share_of_negative_move), support direction is Q1 > Q5.
For direct-direction hypotheses, support direction is Q5 > Q1.
Descriptive variables are reported but not support-graded.

## Support standard
A directional anatomy feature is supported only if:
- correlation direction agrees in discovery and validation;
- extreme-quintile ordering agrees in discovery and validation;
- Top300 and Top500 broadly agree;
- 60% and 80% exits broadly agree;
- portfolio direction matches event-level economics;
- not carried by one calendar year.

No anatomy feature becomes a production rule from V2 alone.
