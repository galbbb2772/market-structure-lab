# Large Relative Resilience V4 — Preregistration

Status: mechanism research only. No production or forward-shadow changes.

## Motivation
Large Market Exhaustion V3 rejected the simple hypothesis that Large-box mean reversion improves when the whole market's selling pressure is already visibly recovering.

All six predeclared market-recovery features failed the full cross-sample / cross-universe / cross-exit support standard.

A more specific mechanism is now tested:

A stock may become a higher-quality mean-reversion candidate when ITS OWN downside progress has stopped and price has reclaimed distance from the low, even while the broader market remains weak.

This is interpreted as relative resilience / idiosyncratic selling exhaustion, not broad-market recovery.

## Frozen Large setup
Unchanged:
- Top500 primary / Top300 robustness
- Large only
- Fresh age <=24 Top500 / <=23 Top300
- signal close in bottom 20% of box
- no_new_low_green confirmation
- enter following-session open
- lower-edge stop
- primary target = 60% box
- robustness target = 80% box
- max hold = 20 sessions
- 5 bps each side
- normalized 10% initial allocation for portfolio diagnostics

## Stock-level exhaustion variables
Definitions frozen from Strategy Reconstruction V1 and measured on confirmation-date close:

1. rebound_from_low_box
   = (confirmation close - min(signal low, confirmation low)) / box width
   Higher = stronger reclaim away from the low.

2. low_progress_box
   = (confirmation low - signal low) / box width
   Higher = less downside progress / stronger refusal to make a lower low.

## Market-pressure variables
Definitions reused from Breadth Permission V1 and measured on confirmation-date close:

1. pct_up_1d
   Fraction of the causal liquid universe with positive 1-day return.
   Lower = broader market is weaker that day.

2. pct_new_20d_low
   Fraction of the causal liquid universe closing at/below its prior 20-session low.
   Higher = broader market is under more downside pressure.

No new market threshold is optimized.

## Frozen discovery cutpoints
Discovery = 2019-2022.
For each Top300 / Top500 universe separately:
- define quintiles for each stock variable;
- define quintiles for each market variable;
- apply those cutpoints unchanged to 2023-2026Q1 validation.

## Predeclared 2D interaction tests

### Grid A — Stock rebound vs broad up/down pressure
Rows: rebound_from_low_box quintile.
Columns: pct_up_1d quintile.

Primary relative-resilience corner:
- STOCK_STRONG / MARKET_WEAK = stock rebound Q5 AND pct_up_1d Q1.

Comparison corners:
- STOCK_STRONG / MARKET_STRONG = stock Q5 AND market Q5.
- STOCK_WEAK / MARKET_WEAK = stock Q1 AND market Q1.
- STOCK_WEAK / MARKET_STRONG = stock Q1 AND market Q5.

Primary hypothesis:
STOCK_STRONG / MARKET_WEAK should outperform STOCK_WEAK / MARKET_WEAK and should not be inferior to STOCK_STRONG / MARKET_STRONG.

### Grid B — Downside refusal vs broad new-low stress
Rows: low_progress_box quintile.
Columns: pct_new_20d_low quintile.

Primary relative-resilience corner:
- STOCK_STRONG / MARKET_STRESSED = low_progress Q5 AND market-new-low Q5.

Comparison corners:
- STOCK_STRONG / MARKET_CALM = stock Q5 AND market Q1.
- STOCK_WEAK / MARKET_STRESSED = stock Q1 AND market Q5.
- STOCK_WEAK / MARKET_CALM = stock Q1 AND market Q1.

Primary hypothesis:
STOCK_STRONG / MARKET_STRESSED should outperform STOCK_WEAK / MARKET_STRESSED and should not be inferior to STOCK_STRONG / MARKET_CALM.

## Metrics
For both 60% and 80% exits:
- N
- mean / median net trade
- profit factor
- target / stop / max-hold shares
- MFE / MAE
- mean holding sessions
- yearly mean trade and PF

Portfolio diagnostics for the four predeclared corners only:
- annual return
- compounded segment return
- MDD
- Sharpe
- exposure
- completed trades

## Support standard
Relative-resilience mechanism is supported only if:
- the primary stock-strong / market-weak(stressed) corner beats the corresponding stock-weak / same-market-pressure corner in discovery AND validation;
- Top300 and Top500 broadly agree;
- 60% and 80% exits broadly agree;
- the effect is not solely one calendar year;
- portfolio direction is consistent with event-level economics.

No interaction is promoted into a hard gate from V4 alone.
