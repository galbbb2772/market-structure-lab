# Large Idiosyncratic Dislocation V1 — Preregistration

Status: mechanism research only. No production / forward-shadow change.

## Question
For confirmed Fresh Large-box signals, is subsequent mean reversion stronger when the stock has underperformed its beta-implied market move, rather than merely falling with the market?

This tests the temporary-mispricing thesis directly at the stock level.

## Frozen setup
- Top500 primary / Top300 robustness
- Large boxes only
- Fresh age <=24 Top500 / <=23 Top300
- bottom-20% signal
- no_new_low_green confirmation
- entry = following session open, inside box
- lower-edge stop
- primary exit = 60% box position
- robustness exit = 80%
- max hold = 20 sessions
- 5 bps each side

## Causal beta / residual construction
All features are computed using data available through the confirmation-date close.

1. beta60
   - align stock and SPY daily close-to-close returns
   - use the most recent 60 return observations ending on confirmation date
   - require at least 45 paired observations
   - beta = covariance(stock, SPY) / variance(SPY)

2. stock_ret5 / stock_ret20
   - trailing close return ending confirmation date

3. spy_ret5 / spy_ret20
   - trailing SPY close return ending confirmation date

4. idio_dislocation_5d
   = -(stock_ret5 - beta60 * spy_ret5)

5. idio_dislocation_20d
   = -(stock_ret20 - beta60 * spy_ret20)

Higher idio_dislocation means the stock has fallen MORE than its beta-implied market move.

No sector residual is used in V1 because point-in-time sector identity is not yet audited.

## Hypothesis
Higher idiosyncratic dislocation should imply:
- higher target-before-stop probability
- higher trade expectancy
- lower stop-first rate

if the strategy is genuinely capturing stock-specific temporary mispricing.

## Discovery / validation
Discovery: 2019-2022
Validation: 2023-2026Q1

For each feature separately:
- discovery defines quintile boundaries
- fixed boundaries are applied unchanged to validation
- report validation N / mean trade / PF / target share / stop share / mean MFE / MAE
- report Spearman relationship with net trade outcome in both periods

No threshold or quintile is promoted from V1.

## Robustness
The hypothesized monotonic direction should broadly agree:
- Top300 and Top500
- 60% and 80% exits
- discovery and validation

A relationship that exists only in 2022 or only in one target is rejected.

## Governance
This is mechanism diagnosis only.
Any future use as a ranking or sizing score requires a separately preregistered test.
