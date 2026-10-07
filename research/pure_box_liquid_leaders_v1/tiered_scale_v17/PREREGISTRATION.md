# Pure Box Tiered Scale Allocation V17

Status: research-only. No production change.

## Motivation
V15/V16 imply:
- Bottom <=20% is a strong structural filter.
- Large boxes carry much stronger trade-level alpha.
- Removing Small entirely hurts portfolio breadth and compounding.

Test a tiered allocation where Large gets higher risk budget and Small remains as a lower-risk breadth sleeve.

## Frozen signal
Strict Wide+Fresh from V13, direct next-session-open entry, no confirmation, entry_fraction <=20%.

Top500 primary thresholds:
- Small width >= 0.13255303761158518, age <=3
- Large width >= 0.2832764505119453, age <=7

Top300 robustness thresholds:
- Small width >= 0.13149887551263392, age <=3
- Large width >= 0.2831081474441409, age <=7

## Exit
Primary: 60% box target, lower-bound stop, max hold 20.
Robustness: full-box target, H20.
Costs 5 bps each side, stop-first.

## Sizing matrix
Risk budgets are account-risk-to-invalidation per entry:
- Equal controls:
  - Small 0.50%, Large 0.50%
  - Small 0.75%, Large 0.75%
  - Small 1.00%, Large 1.00%
- Tiered:
  - Small 0.25%, Large 0.75%
  - Small 0.25%, Large 1.00%
  - Small 0.25%, Large 1.25%
  - Small 0.50%, Large 1.00%
  - Small 0.50%, Large 1.25%
  - Small 0.50%, Large 1.50%
  - Small 0.75%, Large 1.25%
  - Small 0.75%, Large 1.50%

Single-name cap 50%, no leverage, same-day requests pro-rata if cash constrained.

## Decision
Prefer a broad plateau that improves total return and Sharpe versus fixed20 Bottom<=20% reference without materially worsening MDD.
