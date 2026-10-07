# Pure Box Risk-to-Invalidation Sizing V14

Status: research-only. V13 geometry thresholds are frozen.

## Hypothesis
The box lower boundary is the natural invalidation point. Fixed capital weights may under-use high-quality entries with small stop distance and over-use entries with large stop distance. Size each entry by a fixed fraction of account equity at risk to the lower boundary.

## Frozen signal
Primary: Top500 Strict Wide + Fresh from V13:
- Small width >= 0.13255303761158518 and age <= 3
- Large width >= 0.2832764505119453 and age <= 7
- direct next-session-open entry
Robustness: Top300 frozen V13 thresholds.
No confirmation filter.

## Frozen exit
Primary: 60% box target, lower-bound stop, max hold 20 sessions, 5 bps per side, stop-first.
Robustness: full box target with H20.

## Sizing lanes
Risk budget per new position:
- 0.25% equity
- 0.50%
- 0.75%
- 1.00%
- 1.25%
- 1.50%

Requested capital = risk_budget * equity / effective_stop_distance.
Effective stop distance includes entry cost and adverse stop exit cost:
  risk_per_dollar = 1 - ((lower * (1-exit_cost)) / (entry * (1+entry_cost)))
Capital request is capped at:
- 50% equity per symbol
- available cash
No leverage.
When simultaneous requests exceed cash, scale all same-day requests pro-rata.

Controls:
- fixed 20% per event
- old aggressive request weighting is NOT a sizing candidate; V13 already reports it.

## Report
For each lane:
total return, CAGR, MDD, Sharpe, avg exposure, trades, PF, mean trade, win rate,
average requested/realized initial weight, fraction hitting 50% cap, average planned account risk.

## Interpretation
Look for a broad plateau, not a single best risk percentage. No production promotion from this reconstruction.