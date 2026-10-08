# Pure Box Simple Core Path-State Robustness V47

Status: preregistered portfolio-level robustness test. Signal core frozen.

## Context
V46 anatomy found two cross-universe consistent descriptive patterns for EARLY_R250 add-ons:
1. repeated signal occurs while current open is at or below original entry
2. repeated signal occurs on holding day 3

These findings are descriptive only. V47 tests them prospectively within the same historical validation sample using frozen rules and no further threshold search.

## Frozen base
Simple Core Capital Candidate V2 / EARLY_R250:
- Top500 primary, Top300 robustness
- Strict Wide + Fresh
- Bottom<=20%
- first eligible next-session open
- initial risk 1.25%
- repeated same-box signal only
- holding age <=3
- total same-symbol stop-risk ceiling 2.50%
- no age reset
- no stop/target reset
- H15 / target60
- liquidity-first same-day capital queue
- 50% single-name cap
- no leverage
- 5 bps/side baseline

## Policies

A. EARLY_R250_BASE
Current V2 rule:
- allow repeat-signal add-on at age <=3

B. NEGATIVE_ONLY_R250
Allow repeat-signal add-on only when:
- age <=3
- current add-on open <= original entry price

C. AGE3_ONLY_R250
Allow repeat-signal add-on only when:
- holding age ==3

D. AGE3_NEGATIVE_R250
Allow repeat-signal add-on only when:
- holding age ==3
- current add-on open <= original entry price

No other condition changes.

## Required outputs
For Top500 and Top300:
- total return / CAGR / MDD / Sharpe
- rolling 12m min / median / positive share
- yearly returns
- add-on count / capital
- blocked new-symbol entries
- average exposure
- PF / mean trade
- top5 / top10 funded PnL concentration
- add-on top1 / top5 symbol concentration
- ex-2025 add-on PF and slice PnL

## Stress
For Top500 only, rerun all four policies at:
- 10 bps/side
- 20 bps/side

## Decision rule
A path-state restriction is supported only if it:
- preserves most of EARLY_R250 return,
- improves at least one of MDD / Sharpe / rolling minimum / concentration,
- remains directionally sensible on Top300,
- remains viable at 10/20 bps,
- and does not rely entirely on 2025.

No new path condition or threshold may be added after results.
