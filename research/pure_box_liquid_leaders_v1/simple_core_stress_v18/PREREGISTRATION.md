# Pure Box Simple Core Stress Test V18

Status: research-only validation/stress test. No retuning.

## Frozen core under test
Strict Wide + Fresh
→ Bottom <=20%
→ direct next-session-open entry
→ target 60% of box
→ lower-bound stop
→ max hold 20 sessions
→ risk-to-invalidation sizing
Primary risk budgets: 1.25% and 1.50% per entry
Large and Small both retained
Single-name cap 50%, no leverage.

Top500 primary; Top300 robustness.
Historical reconstruction window: 2023-01-01 to 2026-03-31.

## Stress dimensions
1. Costs
- baseline: 5 bps each side
- 10 bps each side
- 20 bps each side

2. Entry delay
- baseline direct next-session open
- +1 trading-session delay after baseline entry day, using delayed open if still inside valid box/target range

3. Liquidity universe
- Top500
- Top300

4. Risk budget
- 1.25%
- 1.50%

5. Rolling / calendar robustness
Report:
- yearly returns
- rolling 12-month total return / MDD / Sharpe where feasible
- worst rolling window
- positive rolling-window share

6. 2025 stress
Explicitly report 2025-only portfolio return and drawdown.

## Decision
Do not optimize from this test.
Candidate is stress-surviving only if:
- both Top300 and Top500 remain profitable under baseline,
- doubled and quadrupled costs remain profitable,
- +1 day delay does not destroy the edge,
- no single calendar year is catastrophically dominant,
- rolling-window behavior is not dependent on one narrow period.
