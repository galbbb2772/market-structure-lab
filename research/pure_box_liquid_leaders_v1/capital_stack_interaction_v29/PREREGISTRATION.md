# Pure Box Simple Core Capital Stack Interaction V29

Status: capital-layer interaction only. Signal core frozen.

## Frozen signal core
Strict Wide + Fresh
Bottom <=20%
direct next-session open
lower-bound stop
target60
H15
5 bps/side
50% single-name cap
Top300 / Top500

## Question
Can the two independently supported capital mechanisms be stacked without degrading robustness?
1. Exposure-aware risk budgeting
2. Capital priority routing

## Preregistered lanes
For Top300 and Top500:

A. R125_PRO_RATA_H15
- fixed 1.25% risk
- pro-rata allocation
- H15

B. EXPOSURE_AWARE_PRO_RATA_H15
- <25% opening exposure: 1.50%
- 25%-60%: 1.25%
- >60%: 1.00%
- pro-rata
- H15

C. R125_LIQUIDITY_FIRST_H15
- fixed 1.25%
- liquidity-first sequential capital queue
- H15

D. EXPOSURE_AWARE_LIQUIDITY_FIRST_H15
- exposure-aware risk
- liquidity-first sequential capital queue
- H15

E. EXPOSURE_AWARE_LOW_ENTRY_FIRST_H15
- exposure-aware risk
- lower actual box-entry fraction first
- H15

## Primary decision criteria
- total return / CAGR
- MDD / Sharpe
- rolling 12m minimum and positive share
- yearly returns
- completed trades
- blocked/partial entries
- realized requested-risk ratio
- average exposure

## Decision rule
A stacked rule is supported only if it improves capital efficiency without materially worsening drawdown/rolling stability and remains directionally sensible in both universes.
Do not promote based on total return alone.
