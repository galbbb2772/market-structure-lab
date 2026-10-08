# Pure Box Simple Core Early R250 Fragility V44

Status: robustness / fragility validation only. No rule changes.

## Frozen subject
EARLY_R250 from V43:
- Top500 primary, Top300 robustness
- Strict Wide + Fresh
- Bottom<=20%
- first eligible next-session open only
- lower stop / target60 / H15
- liquidity-first queue
- 50% single-name cap
- no leverage
- repeated same-box signals may add only when existing holding age <=3
- repeated signal does not reset age, stop, or target
- total same-symbol stop risk may rise up to 2.50%

Controls:
- SKIP_OVERLAP
- FULL_R250

## Motivation
V43:
Top500 5bps:
- SKIP +373.36%
- FULL_R250 +580.76%
- EARLY_R250 +607.01%
EARLY_R250 also improved rolling minimum and Sharpe vs FULL_R250.
However 2025 remains a dominant strong year and add-on PnL is concentrated.

## Tests

### A. Ex-2025 portfolio growth
Using annual portfolio return blocks already produced by the exact portfolio simulation:
- compound 2023, 2024, and 2026Q1 only
- compare SKIP / FULL_R250 / EARLY_R250
This is a temporal fragility diagnostic, not a new backtest path.

### B. Leave-one-year-out block compounding
For each policy:
- omit each available year in turn
- compound remaining annual portfolio returns
Report EARLY_R250 minus controls.

### C. Add-on symbol concentration
Reconstruct EARLY_R250 add-on slice ledger.
Report:
- top1 / top3 / top5 / top10 absolute add-on PnL share
- largest-symbol add-on PnL contribution
- leave-top1-symbol-out add-on slice PnL
- leave-top3-symbols-out add-on slice PnL
- unique symbols

### D. 2025 exclusion at add-on-slice level
Report add-on:
- n / funded capital
- mean return / PF / win rate
- sum slice PnL
for ex-2025.

## Decision rule
EARLY_R250 can be called a stronger historical capital overlay than FULL_R250 only if:
- ex-2025 portfolio growth still exceeds SKIP,
- leave-one-year-out comparisons remain directionally sensible,
- add-on PnL is not entirely one symbol,
- ex-2025 add-on PF remains >1.

No new age cutoff or risk target after results.
