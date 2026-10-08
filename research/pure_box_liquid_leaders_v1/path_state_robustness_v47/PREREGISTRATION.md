# Pure Box Simple Core Path-State Robustness V47

Status: robustness validation only. Signal core frozen.

## Context
V46 anatomy found two cross-universe descriptive patterns inside EARLY_R250:
1. Repeat signal while current open is still at/below original entry had much stronger add-on outcomes.
2. Age-3 repeat signals had much stronger add-on outcomes than age-2.

These are post-hoc findings and are NOT candidate rules yet.

## Frozen base
Top500 primary, Top300 robustness
Strict Wide + Fresh
Bottom<=20%
first eligible next-session open
initial risk 1.25%
same-box repeat signal only
same lower stop / same target / same H15 clock
50% single-name cap
liquidity-first queue
no leverage

## Preregistered lanes

A. EARLY_R250_BASE
Current Candidate V2:
- repeat signal allowed at holding age <=3
- total same-symbol stop-risk ceiling 2.50%

B. NEGATIVE_ONLY_R250
- repeat signal allowed at age <=3
- current add-on open must be <= original entry price
- otherwise skip add-on
- total same-symbol stop-risk ceiling 2.50%

C. AGE3_ONLY_R250
- repeat signal allowed only when holding age ==3
- no PnL-state condition
- total same-symbol stop-risk ceiling 2.50%

D. AGE3_NEGATIVE_R250
- repeat signal allowed only when holding age ==3
- current add-on open <= original entry price
- total same-symbol stop-risk ceiling 2.50%

E. AGE2_NEGATIVE_R250
- repeat signal allowed only when holding age ==2
- current add-on open <= original entry price
- total same-symbol stop-risk ceiling 2.50%

## Required tests
For Top300 and Top500:
- 5 bps/side
- 10 bps/side
- 20 bps/side

Report:
- total return / CAGR / MDD / Sharpe
- rolling 12m min / median / positive share
- yearly returns
- add-on count / capital
- blocked new entries
- average exposure
- top5/top10 funded PnL concentration
- ex-2025 annual-block compounding

## Decision rule
A path-state lane is supported only if:
- it preserves or improves return versus EARLY_R250_BASE,
- or materially improves MDD / rolling stability / concentration with modest return sacrifice,
- direction is coherent across Top500 and Top300,
- 10/20 bps results remain sensible,
- ex-2025 result does not collapse.

No new path threshold may be added after results.
