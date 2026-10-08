# Pure Box Simple Core Smooth Capital Allocation V34

Status: portfolio-allocation research only. Signal core frozen.

## Context
V33 showed:
- LIQUIDITY_FIRST remains strongest for total return.
- diversification-first sharply reduces concentration but sacrifices too much return.
- geometric/diversification scores did not beat liquidity-first.

V34 asks whether the weakness is the current all-or-nothing sequential funding rule rather than the priority variable itself.

## Frozen signal/execution core
- Top500
- Strict Wide + Fresh
- actual entry Bottom <=20%
- first eligible next-session open only
- lower-bound stop
- target60
- H15
- 5 bps/side
- fixed 1.25% risk request
- 50% single-name cap
- no leverage

No signal thresholds may change.

## Preregistered capital allocators

A. LIQUIDITY_FIRST_SEQUENTIAL
Current capital-candidate baseline.

B. PRO_RATA
Uniform proportional scaling across all valid same-day requests.

C. LIQUIDITY_WEIGHTED_LINEAR
When requested capital exceeds cash:
- score_i = (N - rank_position_i + 1)
- allocate cash proportional to score_i * requested_capital_i
- cap each allocation at its original request
- redistribute any residual iteratively with the same weights.
No candidate receives more than its frozen request.

D. LIQUIDITY_WEIGHTED_INVERSE_RANK
When oversubscribed:
- score_i = 1 / rank_position_i
- allocate proportional to score_i * requested_capital_i
- cap at request and redistribute residual iteratively.

E. LIQUIDITY_WEIGHTED_INVERSE_SQRT
When oversubscribed:
- score_i = 1 / sqrt(rank_position_i)
- allocate proportional to score_i * requested_capital_i
- cap at request and redistribute residual iteratively.

F. TWO_TIER_LIQUIDITY
When oversubscribed:
- top half by liquidity gets weight 2
- bottom half gets weight 1
- allocate proportional to weight * request
- cap and iteratively redistribute residual.

## Why these are allowed
All formulas are fixed before results.
No fitted coefficients.
All use only same-day causal liquidity rank and frozen requested capital.

## Metrics
- total return / CAGR / MDD / Sharpe
- rolling 12m min / median / positive share
- yearly returns
- average exposure
- completed trades / PF / mean trade
- fraction of same-day candidates receiving nonzero funding
- partial funding frequency
- risk realization ratio
- top5/top10 funded PnL concentration

## Decision rule
A smooth allocator is supported only if it beats or closely matches LIQUIDITY_FIRST_SEQUENTIAL on return while improving at least one of:
- MDD
- rolling stability
- concentration
- breadth of funded opportunities

No post-result weight tuning.
