# Structure Decay Economic Impact V2

Status: exploratory economic-impact test. No production promotion.

## Motivation
Structure Decay V1/V1.1 found a post-hoc but strong validation cliff at 3+ lower-boundary touch episodes.
This V2 does NOT search for a new threshold. It fixes:
- exhausted = touch_episodes >= 3
- eligible integrity = touch_episodes <= 2

The objective is to measure economic significance in the actual portfolio engine.

## Important evidence status
The 3+ cliff was identified using V1 validation behavior, so V2 is NOT independent OOS evidence.
Treat V2 as an economic-impact / mechanism test only.

## Frozen strategy mechanics
Same Pure Box Liquid Leaders V1:
- Top300 and Top500 causal liquid-leader proxy
- long only
- next-session-open entry
- stop at box lower
- target at box upper
- same-day stop+target -> stop first
- 5 bps/side
- small requested weight 50%; large 100%

Annual walk-forward box-vitality thresholds:
- Fresh: age <= prior-history median by scale
- Wide+Fresh: Fresh + width >= prior-history median by scale

## Lanes
For Fresh and Wide+Fresh:
1. baseline
2. no_3plus: reject new entries with touch_episodes >=3
3. breadth_dual: require contemporaneous breadth MA50 >=50% AND breadth 20d-positive >=50%
4. no_3plus_plus_breadth_dual

Breadth uses the already-defined point-in-time causal Top300/Top500 cross-section.

## Evaluation
Annual walk-forward years 2021..2026Q1.
Report yearly:
- total return
- MDD
- Sharpe
- avg exposure
- trade count
- PF
- mean trade

And aggregate:
- compounded annual walk-forward return
- positive-year count
- average Sharpe
- average exposure

## Interpretation
Because threshold selection is not untouched OOS, do not promote.
A useful result is:
- no_3plus improves PF / drawdown with modest exposure loss;
- effect direction is similar in Top300 and Top500;
- combination with breadth is better than either filter alone, indicating distinct information.
