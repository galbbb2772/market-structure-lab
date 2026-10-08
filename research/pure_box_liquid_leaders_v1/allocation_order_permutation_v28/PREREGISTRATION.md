# Pure Box Simple Core Allocation Order Permutation V28

Status: portfolio-routing robustness test only. Signal core frozen.

## Context
V26/V27 show LIQUIDITY_FIRST improves portfolio results versus pro-rata and reverse-liquidity controls, but trade-level liquidity bands are not monotonically stronger. Therefore liquidity must NOT be promoted as a signal-quality factor.

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

## Question
Is LIQUIDITY_FIRST genuinely better than arbitrary same-day capital ordering, or is its historical result within the random-order distribution?

## Tests
For each universe:
1. PRO_RATA
2. LIQUIDITY_FIRST
3. LOW_ENTRY_FRACTION_FIRST
4. 40 deterministic random same-day orderings using fixed seeds 0..39

For every random ordering report:
- total return
- CAGR
- MDD
- Sharpe
- rolling-12m minimum
- positive-share

Then report empirical percentile of LIQUIDITY_FIRST and LOW_ENTRY_FRACTION_FIRST versus the random-order distribution.

## Decision rule
A routing rule is supported only if:
- it is above the 90th percentile of random total return AND
- does not have materially worse MDD than random median AND
- rolling stability remains strong AND
- direction is consistent across Top300 and Top500.

If the rule is not exceptional versus random ordering, treat V26 as path luck, not a capital mechanism.
