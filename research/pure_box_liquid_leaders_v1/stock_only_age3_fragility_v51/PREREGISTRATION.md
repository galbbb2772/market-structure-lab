# Pure Box Simple Core Stock-Only AGE3 Fragility V51

Status: preregistered fragility study. No rule changes.

## Dependency
V50 Stage 2 removes the frozen non-single-stock instrument list and reruns:
- SKIP_OVERLAP
- EARLY_R250
- AGE3_ONLY_R250

V51 studies STOCK_ONLY AGE3_ONLY_R250 only. It is useful whether V50 shows a large or modest degradation.

## Frozen subject
- ordinary single-name equity candidate stream from V50 STOCK_ONLY
- Top500 primary, Top300 robustness
- AGE3_ONLY_R250
- initial risk 1.25%
- repeat same-box add-on only at holding age ==3
- total same-symbol stop-risk ceiling 2.50%
- H15 / target60 / same lower stop
- 50% single-name cap
- liquidity-first queue
- no leverage
- 5bps/side primary

No instrument-list, signal, age, or sizing changes.

## Required fragility tests

1. Temporal block robustness
- all-year block compound
- ex-2025 block compound
- leave-one-year-out block compound

2. Add-on event ledger
For every STOCK_ONLY age3 add-on:
- date / year / symbol
- funded capital
- entry
- exit
- add-on slice return
- add-on slice PnL

3. Symbol concentration
- top1 / top3 / top5 / top10 absolute add-on PnL share
- leave-top1-symbol-out signed add-on PnL
- leave-top3-symbols-out signed add-on PnL
- unique symbols

4. Ex-2025 add-on evidence
- n
- mean / median slice return
- PF
- win rate
- signed slice PnL
- concentration after removing 2025

5. Cross-universe
Repeat the same diagnostics for Top300.

## Decision rule
STOCK_ONLY AGE3 is structurally credible only if:
- ex-2025 portfolio block growth remains above STOCK_ONLY SKIP_OVERLAP,
- ex-2025 add-on PF >1,
- removing the top contributing stock does not eliminate all signed add-on PnL,
- and Top300 is directionally coherent.

If these fail, AGE3 remains a mixed-instrument historical phenomenon rather than a single-stock capital overlay.
