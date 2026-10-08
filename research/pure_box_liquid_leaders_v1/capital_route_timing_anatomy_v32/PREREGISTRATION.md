# Pure Box Simple Core Capital Route Timing Anatomy V32

Status: execution-mechanism research only. Signal core frozen.

## Context
V31 corrected portfolio-level stress shows Top500 fixed-R1.25 + Liquidity-First + H15:
- materially outperforms H15 pro-rata under 5/10/20 bps direct execution,
- but +1-session delayed/revalidated execution loses rolling stability.

This study explains the delay fragility without changing the signal or route.

## Frozen candidate
Top500
Strict Wide + Fresh
Bottom<=20%
direct next-session open
lower stop
target60
H15
fixed 1.25% risk
Liquidity-First queue
50% single-name cap
5bps/side baseline

## Required decomposition
Compare direct vs +1-session delayed/revalidated for the actually funded portfolio:
1. Signal retention rate after delayed Bottom<=20 revalidation
2. Which direct-funded names disappear after delay
3. Which delayed-funded names replace them
4. Direct vs delayed entry fraction
5. Direct vs delayed stop distance
6. Direct vs delayed reward-to-target
7. Direct vs delayed liquidity-rank distribution
8. PnL contribution of:
   - retained same-symbol entries
   - direct-only entries
   - delayed-only entries
9. Year-by-year decomposition
10. Concentration shift: top5/top10 funded PnL share

## Interpretation rule
Do not call the candidate invalid merely because delay is worse.
Classify whether fragility comes mainly from:
- geometric deterioration,
- opportunity-set turnover,
- capital-routing reordering,
- concentration/path effects.

No parameter changes in V32.
