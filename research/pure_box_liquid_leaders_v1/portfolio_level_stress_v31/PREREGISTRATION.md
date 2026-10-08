# Pure Box Simple Core Portfolio-Level Stress V31

Status: correction / portfolio-level robustness validation.

## Why V31 exists
V30 cost/delay/concentration diagnostics were computed on the full frozen signal set rather than the actually funded portfolio path. They are valid for signal-level robustness, but they do NOT distinguish capital-routing policies.

V31 corrects this by replaying the actual funded portfolio path for each candidate capital stack.

## Frozen signal core
Strict Wide + Fresh
Bottom <=20%
direct next-session open
lower-bound stop
target60
H15
50% single-name cap

## Candidate lanes
Top300:
- BASE: fixed 1.25% + pro-rata
- CANDIDATE: exposure-aware + low-entry-first

Top500:
- BASE: fixed 1.25% + pro-rata
- CANDIDATE: fixed 1.25% + liquidity-first

## Portfolio-level stresses
For every lane:
1. Cost:
   - 5 bps/side
   - 10 bps/side
   - 20 bps/side
2. Execution:
   - direct next open
   - +1 session delay, only if delayed actual entry remains Bottom<=20
3. Concentration:
   - realized funded PnL by symbol
   - top5/top10 absolute funded PnL share
4. Path metrics:
   - total return, CAGR, MDD, Sharpe
   - rolling 12m min/median/positive share
   - yearly returns
   - average exposure
   - blocked/partial entries
   - completed trades

## Decision rule
A capital candidate survives only if its advantage over BASE remains directionally positive under stressed cost and delay-revalidated execution, while funded concentration and drawdown remain acceptable.
