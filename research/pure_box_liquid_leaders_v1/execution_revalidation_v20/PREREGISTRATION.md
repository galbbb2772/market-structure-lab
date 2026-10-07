# Pure Box Execution-Revalidation Stress V20

Status: diagnostic validation. No retuning.

## Motivation
V19 found that V18 delayed-entry stress allowed execution above the frozen Bottom<=20% boundary.
That changes the strategy geometry rather than testing execution delay alone.

V20 tests a one-session delay while RE-VALIDATING the frozen entry condition at actual execution:
- delayed open must still be within Bottom<=20% of the box,
- otherwise skip the trade.

This is enforcement of an existing frozen-looking rule, not a new filter.

## Frozen core
Strict Wide+Fresh
Bottom<=20% at ACTUAL execution
60% box target
lower-bound stop
H20
risk-to-invalidation sizing
risk budgets 1.25% and 1.50%
Top500 primary / Top300 robustness
single-name cap 50%, no leverage

## Stress
Compare:
1. direct entry baseline
2. delayed one session, unrestricted V18-style (reference)
3. delayed one session, revalidated Bottom<=20%

Costs:
- 5 bps per side
- 20 bps per side

Report total return, MDD, Sharpe, PF, exposure, trades,
rolling 12m minimum return / positive share,
and fraction of original candidates retained after delayed revalidation.

## Decision
If delayed+revalidated materially restores drawdown/rolling stability,
V18's failure is attributed to violation of the frozen entry-location rule rather than pure one-day latency.
No threshold changes permitted.
