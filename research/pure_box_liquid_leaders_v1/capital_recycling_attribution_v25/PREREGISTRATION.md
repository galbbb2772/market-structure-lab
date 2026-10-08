# Pure Box Simple Core Capital Recycling Attribution V25

Status: mechanism attribution only. Signal core frozen.

## Question
V24 shows Day16-20 tail PnL is not uniformly negative. Explain why H15 still improves portfolio results.

## Frozen comparison
- FIXED_R125_H20
- FIXED_R125_H15
Top300 and Top500, same Strict Wide + Fresh + Bottom<=20 direct-entry core, target60, lower stop, 5bps/side, 50% single-name cap.

## Required attribution
Measure:
1. Foregone tail PnL:
   PnL H20 would have earned after Day15 on positions H15 forces out.
2. Recycling benefit:
   PnL from entries that H15 can take earlier / at larger weight because capital was released.
3. Cash-path effect:
   difference in daily available cash and exposure.
4. Blocked/scaled-entry effect:
   changes in number and size of constrained entries.
5. Net interaction:
   realized portfolio delta = recycling benefit - foregone tail value + interaction/resizing effects.

## Decision rule
Do not claim Day16-20 is bad unless tail PnL itself is persistently negative.
If H15 works mainly through opportunity-cost reduction, describe it as capital recycling, not alpha decay.
