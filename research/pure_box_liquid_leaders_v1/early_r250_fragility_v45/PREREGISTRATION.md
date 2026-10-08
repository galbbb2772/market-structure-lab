# Pure Box Simple Core Early-R250 Fragility V45

Status: fragility diagnosis only. No parameter tuning.

## Frozen subject
Top500 primary:
- Strict Wide + Fresh
- Bottom<=20%
- direct next-session open only
- lower stop
- target60
- H15
- liquidity-first queue
- 50% single-name capital cap
- no leverage
- repeated same-box signals may add only while existing holding age <=3
- total same-symbol stop risk may reach 2.50%
- repeated signals do not reset age

Historical V43 headline at 5bps:
+607.01% total return, CAGR 82.92%, MDD -17.21%.

## Purpose
Measure whether Early-R250's uplift is robust or dominated by 2025 / a few symbols / a few add-on events.

## Required diagnostics

### A. Add-on event log
For every Early-R250 add-on:
- date/year
- symbol
- existing age
- funded add-on capital
- risk before/after
- slice realized return
- slice PnL contribution

### B. Leave-one-add-on-out
For each add-on event, remove only that add-on slice and report change in aggregate add-on slice PnL.
This is explanatory, not a full portfolio replay.

### C. Concentration
- top1/top3/top5 add-on event absolute PnL share
- top1/top3/top5 add-on symbol absolute PnL share
- Gini-like concentration proxy if easy
- number of unique add-on symbols

### D. Temporal robustness
- add-on slice stats by year
- ex-2025 add-on slice PF / mean / sum PnL
- fraction of positive add-on PnL coming from 2025

### E. Full-portfolio 2025 ablation
Run the full Early-R250 portfolio with add-ons DISABLED only during calendar year 2025.
All baseline entries remain unchanged.
Compare against:
- normal Early-R250
- SKIP_OVERLAP baseline

This is a fragility diagnostic, not a proposed trading rule.

## Interpretation
If the normal Early-R250 advantage collapses when 2025 add-ons are disabled or if top few events/symbols dominate add-on PnL, keep Early-R250 exploratory and require forward OOS.
No new filter may be derived from this study.
