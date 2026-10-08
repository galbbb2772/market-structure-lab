# Pure Box Simple Core Capital Interaction V23

Status: capital-layer interaction test only. Signal core frozen.

## Frozen signal core
Strict Wide + Fresh
Bottom <= 20%
direct next-session open
lower-bound stop
target60
5 bps/side
Top300 and Top500

No signal filters or thresholds may change.

## Purpose
Test whether the two independently supported V22 capital-layer findings interact constructively:
1. exposure-aware risk budgeting
2. H15 capital recycling

## Preregistered lanes
For Top300 and Top500:

A. BASE_R125_H20
- fixed 1.25% risk
- H20

B. EXPOSURE_AWARE_H20
- opening exposure <25%: 1.50%
- opening exposure 25%-60%: 1.25%
- opening exposure >60%: 1.00%
- H20

C. R125_H15
- fixed 1.25% risk
- H15

D. EXPOSURE_AWARE_H15
- same exposure-aware risk rule
- H15

## Primary decision criteria
A combined lane is considered genuinely better only if:
- total return and/or CAGR improve materially,
- MDD does not materially worsen,
- rolling-12m minimum and positive share are not degraded,
- behavior is directionally consistent in both Top300 and Top500.

No selection based solely on highest historical return.
