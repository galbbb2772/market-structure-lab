# Pure Box Simple Core Age-3 Add-On Fragility V49

Status: robustness / fragility validation only. No rule changes.

## Frozen subject
AGE3_ONLY_R250 from V48:
- Top500 primary, Top300 robustness
- Strict Wide + Fresh
- Bottom<=20%
- initial stop risk 1.25%
- repeated same-box signal add-on only when holding age ==3
- total same-symbol stop-risk ceiling 2.50%
- H15 / target60 / same lower stop
- liquidity-first queue
- 50% single-name cap
- no leverage

Controls:
- SKIP_OVERLAP
- EARLY_R250

## Motivation
V48 showed AGE3_ONLY:
- slightly lower Top500 raw return than EARLY_R250,
- materially better rolling 12m minimum,
- and higher historical return than EARLY_R250 in Top300 across 5/10/20bps.

## Tests

### A. Ex-2025 annual-block compounding
Using exact V48 yearly portfolio returns:
- compound 2023, 2024, and 2026Q1 only
- compare SKIP / EARLY_R250 / AGE3_ONLY_R250

### B. Leave-one-year-out block compounding
For each policy/universe:
- omit each year in turn
- compare remaining compounded return.

### C. AGE3 add-on event ledger
Reconstruct exact age3-only add-on slices.
Report:
- n / funded capital
- mean / median return
- PF / win rate
- sum slice PnL
- unique symbols
- 2025 vs ex-2025

### D. Concentration
- top1 / top3 / top5 / top10 absolute add-on PnL share
- leave-top1-symbol-out sum PnL
- leave-top3-symbols-out sum PnL

## Decision rule
AGE3_ONLY is a stronger robustness candidate than EARLY_R250 only if:
- ex-2025 portfolio growth remains superior to SKIP and competitive with EARLY_R250,
- ex-2025 add-on PF > 1,
- add-on PnL is not entirely dependent on one symbol,
- and cross-universe evidence remains coherent.

No further age tuning after results.
