# Pure Box Simple Core Candidate — PREFREEZE_DRAFT

Status: PREFREEZE_DRAFT
This is not a frozen production candidate yet. Promotion requires V18 stress-test gates to pass.

## Core thesis
A fresh, wide box entered near its lower boundary offers asymmetric payoff:
small, explicit invalidation distance versus materially larger mean-reversion space.

## Frozen-looking rule set under evaluation
Universe:
- Top500 primary liquid-leader proxy
- Top300 robustness universe

Geometry:
- Strict Wide + Fresh thresholds remain those discovered from 2019-2022.
- Top500:
  - Small: width >= 0.13255303761158518, age <= 3
  - Large: width >= 0.2832764505119453, age <= 7
- Top300:
  - Small: width >= 0.13149887551263392, age <= 3
  - Large: width >= 0.2831081474441409, age <= 7

Location:
- direct entry only when entry fraction <= 20% of active box
- entry fraction = (entry - lower)/(upper - lower)

Execution:
- enter next-session open
- no additional confirmation
- stop at box lower boundary
- primary target at 60% of box
- maximum holding period 20 market sessions
- same-day stop/target ambiguity resolves stop first
- 5 bps per side baseline costs

Sizing:
- risk-to-invalidation sizing
- primary candidate region: 1.25%-1.50% account-risk request per entry
- Small and Large both retained
- single-name capital cap 50%
- no leverage
- simultaneous requests scaled pro-rata to available cash

## Why this core
Evidence chain:
- V13: simple direct-entry geometry beat confirmation-heavy variants.
- V15: Bottom <=20% separates strong from weak geometry; 20-30% band largely loses the edge.
- V16 robustness: positive after winsorization, symbol balancing, leave-one-year-out, and bootstrap checks.
- V17: retaining both Small and Large materially improves portfolio compounding versus Large-only concentration.
- 60% target gives materially better drawdown behavior than full-box target.

## Pre-freeze stress gates
Promotion requires V18 to show:
1. Top300 and Top500 baseline both remain profitable.
2. 10 bps and 20 bps per-side cost stress remain profitable.
3. +1 trading-session delayed entry does not destroy the edge.
4. No single calendar year is solely responsible for the result.
5. Rolling 12-month behavior does not show structural collapse.
6. No rule or threshold is retuned after seeing V18.

If any gate fails, remain PREFREEZE_DRAFT and diagnose the failure without tuning this version in-place.
