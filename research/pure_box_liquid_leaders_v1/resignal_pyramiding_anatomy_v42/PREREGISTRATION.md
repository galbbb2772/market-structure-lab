# Pure Box Simple Core Re-Signal Pyramiding Anatomy V42

Status: mechanism anatomy only. No policy changes.

## Fixed subject
PYRAMID_TO_R250 from V40/V41:
- repeated same-box valid signals may refill total same-symbol stop risk up to 2.50%
- no age reset
- same lower stop / target60
- H15
- liquidity-first same-day queue
- 50% single-name cap
- 5 bps/side baseline
- Top500 primary, Top300 robustness

## Motivation
V41 shows large and cost-robust portfolio uplift, but 88%-97% of positive annual uplift comes from 2025.
This study explains that concentration without retuning the rule.

## Required add-on slice ledger
For every funded add-on:
- date / year / symbol
- existing position age
- overlap entry fraction
- position stop risk before add
- position stop risk after add
- add-on funded capital
- add-on shares
- add-on slice realized return when the position exits
- exit reason
- whether 50% single-name cap constrained the add

## Required summaries
By Top300 / Top500 and by year:
- add-on event count
- funded add-on capital
- mean / median add-on slice return
- PF / win rate
- add-on slice return contribution
- symbol concentration
- age-bucket performance (1-3, 4-5, 6-10, 11+)
- entry-fraction quartile diagnostics

## Ex-2025 test
Report the same add-on-slice statistics excluding 2025.

## Interpretation rule
This is explanatory only.
Do not change R250, age handling, or entry rules based on these results.
If ex-2025 add-on slices remain positive and coherent, the mechanism may be broader than the portfolio-year attribution suggests.
If ex-2025 edge collapses, treat R250 as regime-specific / exploratory.
