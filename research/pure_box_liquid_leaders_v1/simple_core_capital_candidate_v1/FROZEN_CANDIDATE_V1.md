# Simple Core Capital Candidate V1 — Frozen Research Candidate

Status: FROZEN_RESEARCH_CANDIDATE / FORWARD_OOS_REQUIRED

Freeze date: 2026-10-08

## Purpose
This is a capital-layer candidate built on the already frozen Simple Core signal logic.
It does NOT replace Simple Core Candidate V1 and does NOT alter its signal definition.

## Frozen universe
Top500 liquid-leader proxy.

## Frozen signal core
- Strict Wide + Fresh
- actual entry Bottom <= 20%
- direct next eligible session open
- no confirmation
- if the direct next-open opportunity is missed, do not chase later
- lower-bound stop
- target = lower + 0.60 * box range
- max hold = 15 sessions
- stop-first same-day ambiguity
- baseline cost assumption = 5 bps/side

## Frozen capital architecture
- fixed 1.25% account risk to lower-bound invalidation
- single-name capital cap 50%
- no leverage
- when same-day valid requests exceed available cash:
  - rank by liquidity rank ascending
  - tie-break by lower entry fraction
  - then symbol
  - fund sequentially
  - final candidate may receive partial remainder
  - later candidates receive zero

## Historical baseline evidence
Top500, 2023-2026Q1 historical validation:
- total return: +373.36%
- CAGR: 61.61%
- max drawdown: -16.83%
- Sharpe: 1.141
- rolling 12m minimum: +15.11%
- rolling 12m positive share: 100%
- completed trades: 291

## Portfolio-level stress
10 bps/side, direct:
- total return: +313.02%
- MDD: -17.96%
- rolling 12m minimum: +11.00%

20 bps/side, direct:
- total return: +212.62%
- MDD: -20.04%
- rolling 12m minimum: +3.36%

The direct-execution candidate remains profitable and historically robust under 4x baseline transaction costs.

## Delay finding
A +1-session delay with Bottom<=20 revalidation changes the opportunity set materially:
- direct funded entries: 294
- delayed funded entries: 202
- same entries: 148
- retained same-entry share vs direct: ~50.3%

Delay also worsens concentration and rolling stability.
Therefore delay is NOT treated as an acceptable execution substitute.

## Frozen execution invariant
The candidate requires the first eligible next-session open.
If that execution is missed, the trade is skipped.
No delayed catch-up entry is permitted in Candidate V1.

## Research interpretation
Liquidity-first is a capital-routing rule, not a signal-quality factor.
Do not interpret higher liquidity rank as monotonic alpha.

## Promotion discipline
No production promotion from historical results.
Forward OOS is required.
No post-freeze retuning of:
- H15
- 1.25% risk
- Bottom<=20
- target60
- liquidity-first ordering
- 50% cap
