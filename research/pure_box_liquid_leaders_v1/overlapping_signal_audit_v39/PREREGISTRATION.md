# Pure Box Simple Core Overlapping Signal Audit V39

Status: diagnostic only. No strategy change.

## Frozen reference portfolio
Top500
Strict Wide + Fresh
Bottom<=20%
direct next-session open only
target60
lower stop
H15
5bps/side
fixed 1.25% risk
50% single-name cap
liquidity-first sequential funding

## Question
How much potential alpha is ignored because a new valid Simple Core signal is skipped while the same symbol is already held?

## Required audit
For every otherwise-valid candidate whose symbol is already in the portfolio:
- date / symbol
- existing position age
- existing position market weight
- remaining headroom to 50% single-name cap
- new signal entry fraction
- new box width
- new stop risk
- whether the new box differs materially from the held position box (material = either lower or upper boundary differs by >1% relative to the held box boundary)
- independent H15 return of the ignored signal using its own frozen stop/target
- existing position eventual return from that date onward

Report:
- ignored-overlap count
- unique symbols
- ignored signals by existing-position age bucket
- mean / median ignored-signal return
- PF / win rate
- fraction with positive cap headroom
- fraction where ignored signal beats continuing held position
- yearly distribution
- contribution concentration by symbol

## Interpretation
This is explanatory only.
Do not add pyramiding or refresh rules unless the ignored-overlap sample is material and shows a coherent positive edge.
