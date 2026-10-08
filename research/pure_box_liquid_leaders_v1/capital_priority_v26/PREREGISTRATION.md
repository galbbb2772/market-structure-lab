# Pure Box Simple Core Capital Priority V26

Status: portfolio allocation research only. Signal core frozen.

## Frozen core
Strict Wide + Fresh
Bottom <=20%
direct next-session open
lower-bound stop
target60
H15
5 bps/side
50% single-name cap
Top300 / Top500
Primary risk reference: 1.25%

## Question
When simultaneous eligible entries exceed available cash, can a causal priority rule improve portfolio efficiency versus proportional scaling?

## Preregistered allocation policies

A. PRO_RATA
- current baseline: scale all same-day requests proportionally to available cash.

B. LOW_ENTRY_FRACTION_FIRST
- prioritize lower actual entry fraction within box.
- tie: higher liquidity, then symbol.

C. WIDER_BOX_FIRST
- prioritize larger strict box width/open.
- tie: lower entry fraction, then liquidity.

D. LOWER_STOP_RISK_FIRST
- prioritize smaller risk-per-dollar to lower bound.
- tie: lower entry fraction, then liquidity.

E. LARGE_SCALE_FIRST
- prioritize Large scale over Small.
- tie: lower entry fraction, then liquidity.

F. LIQUIDITY_FIRST
- prioritize better liquidity rank.
- tie: lower entry fraction.

## Capital fill rule
For B-F:
- process ordered candidates sequentially.
- each receives its full requested weight up to remaining cash.
- last candidate may receive partial remainder.
- later candidates receive zero if cash exhausted.
No leverage.

## Metrics
- total return / CAGR / MDD / Sharpe
- rolling 12m minimum / positive share
- average exposure and idle share
- completed trades
- blocked entries / partially funded entries
- realized requested-risk ratio
- average selected entry fraction / width / stop risk
- Top300 / Top500 consistency

## Decision rule
Reject a priority rule if improvement is universe-specific, driven by one year, or materially worsens drawdown/stability.
Do not select based solely on highest total return.
