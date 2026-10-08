# Early-R250 Shadow Candidate V1 — Forward OOS Preregistration

Freeze date: 2026-10-08
First eligible post-freeze signal date: 2026-10-09
Status: FORWARD_OOS_PENDING

## Primary lane
TOP500_EARLY_R250_SHADOW

## Frozen rules
Use the frozen Simple Core signal stream.

New position:
- direct next-session open only
- actual entry Bottom<=20%
- fixed 1.25% account risk
- 50% single-name capital cap
- H15
- target60 / lower stop
- liquidity-first same-day queue

Repeated same-box signal:
- only while existing holding age <=3
- same stop / target / box
- no age reset
- total same-symbol stop risk may reach, but not intentionally exceed, 2.50%
- 50% capital cap remains binding
- shares same liquidity-first queue with new positions

Missed execution:
- skip
- no delayed catch-up

## Required forward records
For every base and add-on event:
- signal date
- entry date
- symbol
- position age before add
- pre-add and post-add stop risk
- requested and funded capital
- blocked / partial status
- entry fraction
- exit date / exit reason
- realized slice return
- portfolio equity / exposure / cash

## Interim diagnostics
Track separately:
- base-position PnL
- add-on slice PnL
- add-on event concentration
- add-on symbol concentration
- year / regime distribution

Do not use interim results to retune V1.

## Promotion gate
No promotion before BOTH:
- at least 100 closed PRIMARY lane base trades
- at least 30 closed add-on events
- at least 12 calendar months since first eligible forward date

Even after the minimum gate, concentration must be reviewed before any promotion.
