# Simple Core Capital Candidate V2 — Forward OOS Preregistration

Freeze date: 2026-10-08
First eligible post-freeze signal date: 2026-10-09
Status: FORWARD_OOS_PENDING

## Primary lane
TOP500_EARLY_R250_PRIMARY_SHADOW

## Frozen execution
New symbol:
- Simple Core valid signal
- first eligible next-session open only
- actual entry Bottom<=20%
- initial 1.25% account stop-risk request
- 50% single-name cap
- no leverage

Repeated same-box signal:
- same symbol already held
- holding age <=3
- repeated observation valid at current open
- actual current-open entry Bottom<=20%
- same lower stop / same target / same H15 clock
- no age reset
- may raise total same-symbol stop risk up to 2.50%
- 50% capital cap remains hard

Capital queue:
- new entries and add-ons share one liquidity-first sequential queue
- tie-break lower entry fraction, then symbol
- last request may receive partial cash
- no leverage
- missed direct opportunity = skip

## Forward records
Append-only:
- eligible new signals
- repeated-signal observations
- position age
- requested add-on risk
- realized post-add risk
- funded / partial / blocked status
- cash / exposure
- entry / add-on / exit
- equity
- realized and unrealized PnL

## Forward comparison lanes
Track in parallel without retuning:
1. Capital Candidate V1: no repeat-signal pyramiding
2. Capital Candidate V2: EARLY_R250

## Promotion gate
Do not promote before BOTH:
- >=100 CLOSED primary candidate positions
- >=12 calendar months since first eligible forward date

Because add-ons are less frequent, also require:
- >=30 completed add-on events before making a standalone claim about the pyramiding overlay.

Interim results may be observed but must not be used to retune V2.
