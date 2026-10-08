# Simple Core Capital Candidate V2

Status: FROZEN_RESEARCH_CANDIDATE / FORWARD_OOS_REQUIRED

## Purpose
This candidate freezes the capital-layer upgrade discovered after Simple Core Candidate V1.
It does NOT replace or modify Candidate V1.

## Universe
Primary: Top500 liquid-leader proxy.

## Frozen signal core
- Strict Wide + Fresh
- actual next-open entry fraction <=20% of box
- direct next-session open only
- if the intended next-open entry is missed, do not chase later
- lower box bound stop
- target = lower + 60% of box width
- max hold = 15 sessions
- stop-first same-day ambiguity
- 5 bps/side baseline costs

## Capital rule
- fixed 1.25% account risk to lower-bound invalidation
- single-name capital cap 50%
- no leverage
- when same-day requests exceed available cash:
  - order eligible candidates by liquidity rank ascending
  - tie-break by lower entry fraction, then symbol
  - fund sequentially to requested size
  - last funded candidate may receive partial remaining cash
  - later candidates are skipped when cash is exhausted

## Historical evidence
2023-2026Q1 historical reconstruction:
- total return: +373.36%
- CAGR: 61.61%
- max drawdown: -16.83%
- daily Sharpe: 1.141
- profit factor: 2.197
- completed trades: 291
- rolling 12m minimum: +15.11%
- rolling 12m positive share: 100%
- top5 funded absolute PnL share: 35.13%
- top10 funded absolute PnL share: 44.51%

## Cost stress, portfolio-level
Direct execution:
- 10 bps/side: +313.02%, MDD -17.96%, rolling12m min +11.00%
- 20 bps/side: +212.62%, MDD -20.04%, rolling12m min +3.36%

## Execution finding
+1-session delay with Bottom<=20 revalidation remains profitable but materially weakens rolling stability.
V32 shows this is primarily opportunity-set turnover and concentration shift, not geometric deterioration:
- direct funded entries: 294
- delayed funded entries: 202
- same signal retained: 148
- retention: 50.34%
- direct top5 funded PnL share: 35.13%
- delayed top5: 49.28%

Therefore execution invariant is frozen:
Take the intended next-session-open entry if eligible. If missed, skip rather than chase.

## Non-promotion
This is historical research, not production and not live-proven alpha.
Forward OOS is required before promotion.

## Freeze discipline
Do not retune:
- Wide/Fresh thresholds
- Bottom<=20
- target60
- H15
- fixed R1.25
- 50% single-name cap
- liquidity-first queue
from post-freeze observations.

Any modification is Candidate V3 with a new preregistration.
