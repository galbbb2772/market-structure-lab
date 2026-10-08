# Pure Box Simple Core Instrument Purity Audit V50

Status: diagnostic / integrity audit only. No candidate changes.

## Motivation
V49 identified SPXU as the largest contributor to AGE3 add-on PnL.
SPXU is a leveraged inverse ETF, not an ordinary common stock.
The Simple Core research has been interpreted as liquid US equity / stock research, so instrument-type contamination must be audited before further optimization.

## Objective
Measure how much historical performance and add-on edge comes from:
1. ordinary common stocks
2. ordinary unlevered ETFs
3. leveraged / inverse ETFs
4. other non-common-equity instruments if present

## Frozen strategies to audit
Top500:
- Capital Candidate V1 / SKIP_OVERLAP
- EARLY_R250
- AGE3_ONLY_R250

No signal, sizing, exit, or ordering rules change.

## Instrument classification
Use only static symbol/product identity metadata.
Primary sources in order:
- repository security master / ticker metadata if available
- otherwise explicit known ETF/inverse/leveraged lists from available dataset metadata
- no classification from future returns.

Minimum explicit flags:
- is_etf
- is_leveraged_or_inverse
- is_common_stock
- unknown

## Required outputs
For each strategy:
- funded trade count by instrument class
- funded capital by class
- signed PnL by class
- absolute PnL share by class
- top contributors by class

For add-ons:
- add-on event count by class
- add-on PnL by class
- top1/top5 contribution after excluding leveraged/inverse ETFs

Recompute historical portfolio performance under diagnostic exclusions:
A. ALL_INSTRUMENTS
B. EXCLUDE_LEVERAGED_INVERSE_ETF
C. COMMON_STOCK_ONLY

Report:
- total return / CAGR / MDD / Sharpe
- rolling 12m min
- yearly returns

## Decision rule
If leveraged/inverse ETFs materially drive the historical edge, do not promote the affected result as a stock-strategy result.
Any exclusion rule must be treated as data-universe correction, not post-hoc alpha tuning, and must be applied consistently to all versions and forward observers.
