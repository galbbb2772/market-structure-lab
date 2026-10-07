# Large Relative Resilience × Exhaustion V2 — Preregistration

Status: mechanism research only. No production or forward-shadow changes.

## Motivation
Two separate diagnostics identified different pieces of the same possible mechanism:

1. Strategy Reconstruction V1:
   stronger `rebound_from_low_box` was associated with better Large-box reversion.

2. Large Idiosyncratic Dislocation V1:
   the pre-registered "deeper idiosyncratic oversold is better" hypothesis failed.
   The more stable short-horizon direction was the opposite:
   stocks showing 5-session relative resilience versus beta-implied SPY movement tended to fare better.

V2 asks whether these are:
- the same information expressed twice, or
- complementary evidence of support / acceptance.

## Frozen setup
- Large only
- Top500 primary / Top300 robustness
- Fresh age <=24 Top500 / <=23 Top300
- bottom-20% box signal
- no_new_low_green confirmation
- next-session open entry
- lower-edge stop
- primary target = 60% box position
- robustness target = 80%
- max hold = 20 sessions
- 5 bps each side

## Causal features
Known by confirmation-date close.

### A. relative_resilience_5d
Use the already frozen V1 beta construction:
- beta60 from up to 60 paired stock / SPY daily returns ending confirmation date;
- require at least 45 pairs;
- residual_5d = stock_ret5 - beta60 * spy_ret5.

Higher = stock held up better than its beta-implied market move.

Natural threshold:
- RESILIENT: residual_5d >= 0
- UNDERPERFORMING: residual_5d < 0

Zero is an economic identity threshold, not fitted to returns.

### B. rebound_from_low_box
Same definition as Strategy Reconstruction V1:
(confirm_close - min(signal_low, confirm_low)) / box_width

Discovery-only threshold:
- compute the median separately for Top300 and Top500 using 2019-2022 eligible Large observations;
- freeze it;
- STRONG_REBOUND: >= discovery median
- WEAK_REBOUND: < discovery median

The same discovery threshold is applied unchanged to 2023-2026Q1.

## Four predeclared cells
1. RESILIENT_STRONG = resilient + strong rebound
2. RESILIENT_WEAK = resilient + weak rebound
3. UNDERPERFORM_STRONG = underperforming + strong rebound
4. UNDERPERFORM_WEAK = underperforming + weak rebound

## Primary hypotheses
If relative resilience contains independent information:
- within STRONG_REBOUND, RESILIENT should outperform UNDERPERFORMING;
- within WEAK_REBOUND, RESILIENT should outperform UNDERPERFORMING.

If rebound strength contains independent information:
- within RESILIENT, STRONG_REBOUND should outperform WEAK_REBOUND;
- within UNDERPERFORMING, STRONG_REBOUND should outperform WEAK_REBOUND.

Joint hypothesis:
RESILIENT_STRONG should be best and UNDERPERFORM_WEAK should be worst.

## Evaluation
Discovery = 2019-2022
Validation = 2023-2026Q1

For each cell, target and universe:
- N
- mean / median net trade
- PF
- target / stop / max-hold shares
- MFE / MAE
- holding sessions
- yearly mean trade and PF

Also report four predeclared pairwise contrasts:
- resilience effect within strong rebound
- resilience effect within weak rebound
- rebound effect within resilient
- rebound effect within underperforming

Contrast metrics:
- difference in mean net trade
- difference in target share
- difference in stop share

## Mechanism standard
Complementarity is supported only if:
- the relevant pairwise contrast has the hypothesized sign in discovery AND validation;
- Top300 and Top500 agree;
- 60% and 80% targets agree;
- sample size is not trivially small.

No cell is promoted to a hard gate or sizing rule from V2.
Any trading use requires separate preregistration.
