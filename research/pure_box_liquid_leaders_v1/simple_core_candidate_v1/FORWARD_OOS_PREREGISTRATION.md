# Pure Box Simple Core Candidate V1 — Forward OOS Preregistration

Freeze date: 2026-10-07
First eligible post-freeze signal date: 2026-10-08
Status: FORWARD_OOS_PENDING

## Purpose
Evaluate the frozen Pure Box Simple Core Candidate V1 prospectively without any parameter changes.

## Primary lane
Top500
Strict Wide + Fresh frozen thresholds
Bottom<=20% at actual entry
next-session-open execution
target60
lower-bound stop
H20
1.25% risk-to-invalidation sizing
50% single-name capital cap
no leverage
5 bps per-side research cost model

## Robustness lane
Same rules with 1.50% risk budget.
Top300 may be recorded as a secondary universe but must not replace Top500 as the primary decision lane.

## Required logging
For every eligible signal:
- signal date
- symbol
- scale
- lower/upper
- box width
- age
- planned entry date
- actual entry fraction
- accepted/skipped and reason
- requested and realized weight
- planned account risk
- exit date / exit reason
- net trade return
- daily equity/exposure

## Forward decision gate
No promotion before BOTH:
- at least 100 closed primary-lane trades
- at least 12 calendar months elapsed since first eligible forward date

Interim data may be observed but MUST NOT be used to retune Candidate V1.

## Failure diagnostics
If forward evidence weakens:
- diagnose without changing Candidate V1,
- any modified logic becomes Candidate V2 with a new preregistration.
