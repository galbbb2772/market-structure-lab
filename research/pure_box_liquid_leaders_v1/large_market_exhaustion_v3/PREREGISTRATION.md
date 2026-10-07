# Large Box Market Exhaustion V3 — Preregistration

Status: mechanism research only. No production or forward-shadow changes.

## Motivation
Large Market Permission V1 and Pullback-vs-Downtrend V2 show that static market states
(MA200, volatility regime, drawdown depth, or MA200 x 20d return) do not provide a stable
"permission" gate. The same static state can be poor in one era and strong in another.

The next hypothesis mirrors the stock-level exhaustion evidence:
mean reversion should depend more on whether MARKET selling pressure is stopping/reversing
than on whether the market is simply labeled bull/bear.

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
- 10% normalized initial allocation for portfolio diagnostics

All market-exhaustion features are observed at confirmation-date close and are therefore
known before the following-session entry.

## Breadth universe
Reuse the exact causal breadth construction already defined in Breadth Permission V1:
- Top300 / Top500 by prior-20 ADV
- close >= $5
- ADV20 >= $25M
- same point-in-time daily universe proxy
- no future membership information

Daily breadth fields reused:
- pct_above_ma50
- pct_ret20_positive
- pct_up_1d
- median_ret20
- pct_new_20d_low

## Predeclared market-exhaustion features
No threshold grid and no new binary gate.

1. pct_up_1d
   - fraction of the liquid universe up on confirmation day
   - hypothesis: higher is better

2. new_low_relief_1d
   = prior-day pct_new_20d_low - confirmation-day pct_new_20d_low
   - positive means fewer stocks are making new 20d lows
   - hypothesis: higher is better

3. new_low_relief_3d
   = pct_new_20d_low three sessions earlier - confirmation-day pct_new_20d_low
   - hypothesis: higher is better

4. ma50_recovery_3d
   = confirmation pct_above_ma50 - value three sessions earlier
   - hypothesis: higher is better

5. ret20_recovery_3d
   = confirmation pct_ret20_positive - value three sessions earlier
   - hypothesis: higher is better

6. median_ret20_recovery_3d
   = confirmation median_ret20 - value three sessions earlier
   - hypothesis: higher is better

These are continuous mechanism variables. No composite score is allowed in V3.

## Discovery / validation
- discovery: 2019-2022
- validation: 2023-2026Q1

For each rank cap and each feature:
- discovery defines quintile cutpoints
- fixed cutpoints are applied unchanged to validation
- report Q1..Q5 separately

## Event metrics
For 60% primary and 80% robustness exits:
- N
- mean / median net trade
- profit factor
- target / stop / max-hold shares
- mean holding sessions
- MFE / MAE
- yearly mean trade and PF

Continuous diagnostics:
- Spearman(feature, net trade return)
- Spearman(feature, target-before-stop indicator)
- Spearman(feature, stop indicator)

## Portfolio diagnostics
Only predeclared extreme quintiles:
- Q1 only
- Q5 only
- all observations baseline

Use the same normalized 10% initial allocation and frozen exit mechanics.
Report annual return, compounded segment return, MDD, Sharpe, exposure and trade count.

These are diagnostics, not a production selection rule.

## Mechanism support
A feature is considered supported if:
- hypothesized direction is the same in discovery and validation;
- Q5 is economically stronger than Q1 in both periods;
- Top300 and Top500 broadly agree;
- 60% and 80% exits broadly agree;
- the result is not carried by one year.

No feature or quintile cutoff may be promoted from V3 alone.

## Next step if supported
Only if a market-exhaustion feature survives V3 may it be tested jointly with the already
observed stock-level exhaustion variables (rebound_from_low and low_progress) in a separately
preregistered interaction study.
