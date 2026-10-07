# Pure Box Core Geometry Anatomy V15

Status: research-only mechanism audit. No production change and no new alpha thresholds.

## Purpose
V13 identified Strict Wide + Fresh + direct box-bottom entry as the main simple high-performance structure.
V14 showed risk-to-invalidation sizing is useful but not the source of the step-change.

V15 asks two simpler structural questions:
1. Is the effect concentrated in Small or Large boxes?
2. Does direct-entry proximity to the box lower bound show an ordered payoff gradient?

## Frozen contract
- Strict Wide + Fresh thresholds fixed from 2019-2022
- validation 2023-01-01 through 2026-03-31
- direct next-session-open entry
- 60% box target
- box lower stop
- 20-session max hold
- fixed 20% request per event
- 5 bps each side
- stop-first
- Top500 primary / Top300 robustness

## Entry geometry
entry_fraction = (entry_open - box_lower) / (box_upper - box_lower)

Predefined structural bins:
- BOTTOM_0_10: 0% to 10% of box
- BOTTOM_10_20: >10% to 20%
- BOTTOM_20_30: >20% to 30%
- ABOVE_30: >30%

Also report nested lanes:
- BOTTOM_LE_10
- BOTTOM_LE_20
- BOTTOM_LE_30

## Scale lanes
- ALL
- SMALL_ONLY
- LARGE_ONLY
- LARGE_BOTTOM_LE_20
- SMALL_BOTTOM_LE_20

## Interpretation
This is descriptive mechanism decomposition.
No bin is promoted based on the largest historical return.
Support for the 'near invalidation' mechanism requires an ordered deterioration as entry_fraction rises, preferably in both Top500 and Top300.
