# Pure Box Simple Core Capital Displacement V35

Status: exploratory portfolio-capital research only. Signal core frozen.

## Context
V34 showed smooth funding underperforms liquidity-first sequential allocation.
The remaining capital inefficiency may come from already-held positions occupying cash when higher-priority new signals arrive.

## Frozen signal/execution core
- Top500
- Strict Wide + Fresh
- actual entry Bottom <=20%
- first eligible next-session open only
- lower-bound stop
- target60
- H15
- 5 bps/side
- fixed 1.25% account risk request
- 50% single-name cap
- no leverage
- liquidity-first same-day ranking

No signal thresholds may change.

## Question
When cash is insufficient for a newly eligible high-priority signal, can capital be improved by replacing lower-priority existing positions using only causal information?

## Preregistered policies

A. NO_DISPLACEMENT
Frozen Capital Candidate V1 baseline.

B. LIQUIDITY_RANK_REPLACE
When a new candidate cannot receive its full requested capital:
- identify currently held position with worst liquidity rank
- replacement allowed only if new candidate has strictly better liquidity rank
- close enough of the worst-ranked holding at current session open to fund the new request
- repeat if needed
- no position may be increased beyond its frozen request
- remaining same-day candidates still processed by liquidity-first order

C. AGE10_LIQUIDITY_REPLACE
Same as B, but only positions held >=10 sessions may be displaced.

D. AGE5_STALE_REPLACE
Replacement candidate must:
- be held >=5 sessions
- current open progress toward target <25% of box range from entry
Among eligible replaceable holdings, displace worst liquidity rank first.
New candidate must have better liquidity rank.

E. AGE10_STALE_REPLACE
Same as D but held >=10 sessions.

## Important
These are capital-layer exits, not signal filters.
No post-entry future information is used.
All replacement decisions use current session open, known box geometry, age, and liquidity rank.

## Metrics
- total return / CAGR / MDD / Sharpe
- rolling 12m min / median / positive share
- yearly returns
- replacement count
- average realized return of displaced positions
- average subsequent return of newly funded replacement signals
- blocked / partial entries
- average exposure
- turnover proxy
- funded concentration

## Decision rule
A displacement policy is supported only if it improves return or risk-adjusted return versus NO_DISPLACEMENT without materially worsening MDD, rolling stability, or turnover.
Do not optimize age/progress thresholds after seeing results.
