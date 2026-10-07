# Large Stock-vs-Market Divergence V4 — Preregistration

Status: mechanism / interaction research only. No production or forward-shadow changes.

## Motivation
Evidence so far:
- Stock-level exhaustion is stable:
  rebound_from_low_box and low_progress_box show positive relationships with future
  box progress / target completion in discovery and validation.
- Static market regime V1/V2 is unstable.
- Market-level exhaustion V3 fails all 8/8 consistency checks for all six tested features.

This suggests the useful information may be stock-specific rather than broad-market recovery.

V4 asks:
Is a stock-level exhaustion/rebound signal more valuable when the broad liquid universe
is NOT simultaneously experiencing a majority-up day?

Interpretation:
a stock rebounding independently of broad beta may be a cleaner idiosyncratic
mispricing-repair signal.

## Frozen Large setup
Unchanged:
- Top500 primary / Top300 robustness
- Large only
- Fresh age <=24 Top500 / <=23 Top300
- signal close in lower 20% of box
- no_new_low_green confirmation
- following-session open entry
- lower-edge stop
- primary target = 60% box position
- robustness target = 80%
- max hold = 20 sessions
- 5 bps each side
- normalized 10% initial allocation for portfolio diagnostics

## Stock-level exhaustion features
Known at confirmation-date close.

1. rebound_from_low_box
   = (confirmation close - min(signal low, confirmation low)) / box width
   Primary stock feature.

2. low_progress_box
   = (confirmation low - signal low) / box width
   Secondary robustness feature.

For each Top300 / Top500 universe:
- discovery 2019-2022 defines the median of each stock feature;
- the frozen discovery median is applied unchanged to 2023-2026Q1.

Stock state:
- STRONG_STOCK = feature >= frozen discovery median
- WEAK_STOCK = feature < frozen discovery median

No outcome-driven threshold search.

## Market breadth state
Reuse the exact causal Top300 / Top500 breadth construction from Breadth Permission V1.

At confirmation-date close:
- WEAK_MARKET_DAY = pct_up_1d < 50%
- STRONG_MARKET_DAY = pct_up_1d >= 50%

The 50% threshold is a pre-existing natural breadth threshold; it is not fit here.

## Four predeclared interaction cells
For each stock feature separately:
1. STRONG_STOCK | WEAK_MARKET_DAY
2. STRONG_STOCK | STRONG_MARKET_DAY
3. WEAK_STOCK | WEAK_MARKET_DAY
4. WEAK_STOCK | STRONG_MARKET_DAY

## Primary hypothesis
For rebound_from_low_box:

STRONG_STOCK | WEAK_MARKET_DAY should be economically stronger than:
- WEAK_STOCK | WEAK_MARKET_DAY, and
- STRONG_STOCK | STRONG_MARKET_DAY.

Reason:
the stock is showing localized rejection/recovery even though broad beta is not providing
a majority-up tailwind.

low_progress_box is the preregistered robustness replication.

## Evaluation
Discovery: 2019-2022
Validation: 2023-2026Q1

For 60% and 80% exits, report per cell:
- N
- mean / median trade
- PF
- win rate
- target / stop / max-hold shares
- mean holding sessions
- MFE / MAE
- yearly mean trade and PF

Portfolio include-cell diagnostics:
- compounded segment return
- annual returns
- MDD
- Sharpe
- exposure
- trade count

## Mechanism support
Primary rebound_from_low_box interaction is supported only if:
- STRONG_STOCK|WEAK_MARKET beats WEAK_STOCK|WEAK_MARKET in discovery and validation;
- STRONG_STOCK|WEAK_MARKET beats STRONG_STOCK|STRONG_MARKET in discovery and validation;
- ordering holds in Top300 and Top500;
- ordering holds for 60% and 80% exits;
- trade economics and normalized portfolio diagnostics agree broadly;
- no single year explains the result.

low_progress_box must show broadly compatible behavior to strengthen the interpretation,
but is not required to match every cell exactly.

No cell becomes a production gate from V4.
