# Pure Box Large-Bottom Risk Sizing V16

Status: research-only. No production change.

## Purpose
Cross the two strongest structural findings:
1. V15: Large boxes carry most of the edge; Bottom <=20% is the strongest location band.
2. V14: risk-to-invalidation sizing improves capital efficiency.

## Frozen signal
Strict Wide + Fresh from V13, direct next-session-open entry, no confirmation.

Top500 primary:
- Large only
- large width >= 0.2832764505119453
- age <= 7
- entry_fraction <= 0.20

Top300 robustness:
- Large only
- large width >= 0.2831081474441409
- age <= 7
- entry_fraction <= 0.20

Entry fraction = (entry - lower)/(upper-lower).

## Exit
Primary: target 60% of box, lower-bound stop, max hold 20 sessions.
Robustness: full box target, same stop/H20.
Costs: 5 bps per side. Stop-first.

## Sizing
Controls:
- fixed 20% per event

Risk budgets:
- 0.50%
- 0.75%
- 1.00%
- 1.25%
- 1.50%
- 1.75%
- 2.00%

Requested capital = risk_budget * equity / effective stop distance.
Single-name capital cap = 50% equity.
No leverage. Same-day requests scaled pro-rata if cash-constrained.

## Report
total return, CAGR, MDD, Sharpe, avg exposure, trades, PF, mean trade, win rate,
avg/median realized initial weight, cap-hit share, avg realized planned account risk.

## Decision rule
Look for a broad plateau and cross-universe consistency. Do not select one isolated maximum.
