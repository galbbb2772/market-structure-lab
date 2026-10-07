# Pure Box Risk-to-Invalidation Sizing V14

Status: research-only portfolio sizing audit. No signal threshold changes.

## Motivation
V13 showed that the simple Strict Wide + Fresh direct-entry geometry materially outperformed later confirmation-heavy variants.
The next question is whether fixed capital weights are the wrong expression for a box-bottom strategy.

A box-bottom trade has a natural invalidation level: the box lower bound.
Therefore position size can be defined by the account risk implied by the distance from entry to that lower bound.

## Frozen signal / exit contract
No alpha rules are changed:
- Top500 primary / Top300 robustness
- Strict Wide + Fresh thresholds frozen from the 2019-2022 discovery sample
- direct next-session-open entry
- 60% box target
- box lower stop
- max hold 20 sessions
- 5 bps each side
- same-day stop-first
- 2023-01-01 through 2026-03-31 validation window

## Baseline
- fixed 20% requested capital per event
- max gross exposure 100%

## Risk sizing
For each eligible event:
stop_distance = (entry_price - box_lower) / entry_price

requested_weight = min(
  33% single-name cap,
  risk_budget / stop_distance
)

Risk-budget grid:
- 0.25% of account equity
- 0.50%
- 0.75%
- 1.00%

If simultaneous requested allocations exceed available cash, scale all new entries proportionally.
No leverage.

## Readout
For each risk budget and baseline:
- total return / CAGR
- maximum drawdown
- Sharpe
- average exposure
- completed trades
- PF / mean trade / win rate
- average requested position weight
- average realized initial account-risk fraction
- share of entries constrained by the 33% single-name cap
- share of entry days constrained by available cash

## Interpretation
The purpose is not to pick the historically highest number.
Risk sizing is supported only if a neighborhood of adjacent risk budgets improves capital efficiency while drawdown scales smoothly and Sharpe remains competitive with the fixed-20% baseline.

No automatic production change.