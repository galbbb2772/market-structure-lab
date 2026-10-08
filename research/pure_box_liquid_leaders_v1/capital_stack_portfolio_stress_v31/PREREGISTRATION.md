# Pure Box Simple Core Capital Stack Portfolio Stress V31

Status: portfolio-level robustness validation only. Signal core frozen.

## Why V31 exists
V30's baseline portfolio comparisons are valid, but its cost/delay stress used the frozen signal cohort rather than reproducing each capital-routing portfolio under stressed execution. V31 fixes that.

## Frozen candidates

### Top300 candidate
Exposure-Aware risk
+ Low-entry-fraction-first queue
+ H15

### Top500 candidate
Fixed 1.25% risk
+ Liquidity-first queue
+ H15

## Controls
For each universe:
- fixed 1.25% + pro-rata + H15
- candidate capital stack

## Portfolio-level stresses
Run the FULL portfolio allocator under:

1. 5 bps/side, direct next-open
2. 10 bps/side, direct next-open
3. 20 bps/side, direct next-open
4. 5 bps/side, +1 session delay, actual-entry Bottom<=20 revalidation
5. 10 bps/side, +1 session delay, revalidated
6. 20 bps/side, +1 session delay, revalidated

For every lane/stress report:
- total return / CAGR
- MDD / Sharpe
- rolling 12m min / median / positive share
- yearly returns
- average exposure
- entries / completed trades
- blocked and partial entries
- risk realization ratio

## Decision rule
A candidate passes only if:
- 20bps direct remains profitable with acceptable drawdown,
- delay-revalidated 20bps remains profitable,
- candidate does not lose its advantage solely because of execution stress,
- rolling 12m minimum does not collapse below zero in most stress lanes.

Do not promote from trade-level diagnostics.
