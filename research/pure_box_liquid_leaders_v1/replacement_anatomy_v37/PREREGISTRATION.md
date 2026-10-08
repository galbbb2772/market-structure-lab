# Pure Box Simple Core Replacement Anatomy V37

Status: mechanism anatomy only. No parameter changes.

## Fixed subject
Top500
5 bps/side
H15
fixed 1.25% risk
liquidity-first queue
AGE10_STALE_REPLACE:
- held >=10 sessions
- current-open progress toward target <25%
- incoming signal must have strictly better liquidity rank
- worst-liquidity eligible holding displaced first

V35/V36 show 9 historical replacement events and a small but persistent Top500 portfolio improvement.

## Required event log
For each replacement event:
- date
- displaced symbol
- incoming symbol
- displaced holding age
- displaced liquidity rank
- incoming liquidity rank
- displaced current-open progress toward target
- displaced realized return at replacement
- capital released
- incoming funded amount

## Post-hoc counterfactual diagnostics
For each displaced position:
- what its remaining slice would have returned if kept under original stop/target/H15
For each incoming replacement signal:
- realized return of the funded incoming slice under the actual portfolio path

Report:
- paired incoming minus displaced-counterfactual return
- win share of replacement pairs
- mean / median pair delta
- event-year distribution
- contribution concentration across the 9 events

## Interpretation rule
Counterfactual results are explanatory only and MUST NOT be used to retune the replacement rule.
If gains are dominated by one or two events, treat the overlay as fragile despite V36 cost robustness.
