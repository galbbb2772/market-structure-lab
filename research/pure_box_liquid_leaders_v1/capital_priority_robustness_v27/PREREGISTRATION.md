# Pure Box Simple Core Capital Priority Robustness V27

Status: portfolio-allocation mechanism test only. Signal core frozen.

## Context
V26 found that LIQUIDITY_FIRST under H15 materially improved portfolio results versus pro-rata scaling in both Top300 and Top500.

This study tests whether the effect is a real monotonic allocation mechanism rather than a path artifact.

## Frozen core
Strict Wide + Fresh
Bottom <=20%
direct next-session open
lower-bound stop
target60
H15
5 bps/side
50% single-name cap
fixed 1.25% risk request
Top300 / Top500

No signal thresholds may change.

## Tests

### A. Same-day ranking monotonicity
On days with cash competition, compare candidate outcome by liquidity-priority position:
- rank 1
- rank 2
- rank 3+
Report mean trade return, PF, win rate, and sample count.

### B. Liquidity rank bands
Within accepted Simple Core candidates:
- 1-100
- 101-200
- 201-300
- 301-400
- 401-500
Report trade-level outcome without changing portfolio allocation.

### C. Allocation controls
Compare:
1. PRO_RATA
2. LIQUIDITY_FIRST
3. REVERSE_LIQUIDITY_FIRST
4. LOW_ENTRY_FRACTION_FIRST

### D. Temporal robustness
For PRO_RATA and LIQUIDITY_FIRST:
- yearly returns
- leave-one-year-out aggregate trade return
- rolling 12m minimum / positive share
- 2023, 2024, 2025, 2026Q1 consistency

## Decision rule
Liquidity priority is supported only if:
- it beats pro-rata directionally in both Top300 and Top500,
- reverse liquidity is worse or does not show the same improvement,
- higher-liquidity bands show at least broadly stronger or more stable outcomes,
- improvement is not concentrated entirely in one calendar year.

Do not promote based on total return alone.
