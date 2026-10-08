# Simple Core Capital Candidate V1 — Forward OOS Preregistration

Freeze date: 2026-10-08
First eligible post-freeze signal date: 2026-10-09
Status: FORWARD_OOS_PENDING

## Primary lane
TOP500_CAPITAL_R125_LIQUIDITY_FIRST_H15

## Rules
Use the frozen Simple Core signal stream only.
At the first eligible next-session open:
- actual entry must remain Bottom<=20%
- fixed 1.25% account risk to lower-bound invalidation
- 50% single-name capital cap
- no leverage
- H15
- target60
- lower stop
- 5 bps/side tracking assumption
- same-day cash competition resolved by liquidity-first sequential queue
- missed direct next-open entry = SKIP, no chase

## Forward records
Track:
- eligible signals
- actual entry decisions
- funded / partial / blocked status
- requested vs realized risk
- entry/exit
- equity
- exposure
- cash
- slippage proxy if live fill data becomes available

## Minimum promotion gate
No promotion before BOTH:
- 100 closed PRIMARY lane trades
- 12 calendar months from first eligible forward date

Interim forward data may be observed but must not be used to retune Candidate V1.
