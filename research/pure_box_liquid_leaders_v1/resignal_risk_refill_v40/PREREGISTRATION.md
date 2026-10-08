# Pure Box Simple Core Re-Signal Risk Refill V40

Status: exploratory capital-layer research only. Signal core frozen.

## Context
V39 found 192 valid same-symbol overlaps while positions were already held:
- 90 unique symbols
- mean independent H15 return +4.29%
- PF 3.16
- 89.6% had positive headroom below the 50% single-name cap
- 0% represented materially different boxes

Therefore repeated signals are interpreted as repeated observations of the SAME box state, not new independent alpha events.

## Frozen reference
Top500 primary, Top300 robustness
Strict Wide + Fresh
Bottom<=20%
direct next-session open
lower stop
target60
H15
5bps/side
liquidity-first sequential capital queue
50% single-name cap
no leverage

## Question
Can repeated same-box signals be used to refill or deliberately increase risk on an existing position without changing the signal logic?

## Preregistered policies

A. SKIP_OVERLAP
Current Capital Candidate behavior.

B. REFILL_TO_R125
On any valid repeated same-box signal:
- compute current position risk to the same lower stop using current session open
- if total current stop risk is below 1.25% of account equity, add enough at current open to restore total risk to 1.25%
- subject to available cash and 50% single-name capital cap
- never exceed 1.25% target risk intentionally

C. REFILL_TO_R150
Same mechanics, but restore total position stop risk to 1.50%.
This is an aggressive shadow, not a candidate default.

D. PYRAMID_TO_R250
On valid repeated same-box signals, allow total same-symbol stop risk to increase up to 2.50% of account equity.
- same lower stop
- same target
- current open execution
- available cash and 50% capital cap still apply
This tests whether repeated persistence contains useful sizing information.

## Important
No box thresholds, entry thresholds, exits, liquidity ordering, or hold rules may change.
Repeated signals do NOT reset H15 holding age and do NOT create a fresh target/stop.
They only permit additional capital at the current valid open.

## Metrics
- total return / CAGR / MDD / Sharpe
- rolling 12m min / median / positive share
- yearly returns
- number of add-on events
- add-on capital
- average and max position stop risk after add-on
- average exposure
- single-name 50% cap hit count
- blocked/partial new-symbol entries
- turnover proxy
- funded concentration

## Decision rule
REFILL_TO_R125 is most important because it tests capital completion without increasing intended risk.
Higher-risk variants are exploratory.
Do not select PYRAMID_TO_R250 merely because it has the highest historical return; evaluate MDD and rolling stability.
