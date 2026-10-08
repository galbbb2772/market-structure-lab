# Pure Box Simple Core Marginal Capital Allocation V33

Status: portfolio-allocation research only. Signal core frozen.

## Context
Simple Core Capital Candidate V1 freezes:
Top500 + H15 + fixed 1.25% risk + liquidity-first sequential funding.

V33 asks whether capital can be allocated more efficiently using only information known at the entry decision.

## Frozen signal/execution core
- Top500
- Strict Wide + Fresh
- actual entry Bottom <=20%
- first eligible next-session open only
- lower-bound stop
- target60
- H15
- 5 bps/side
- fixed 1.25% account risk request
- 50% single-name cap
- no leverage

No signal thresholds may change.

## Preregistered capital allocators

A. LIQUIDITY_FIRST
Current capital-candidate baseline.

B. LOW_ENTRY_FIRST
Lower actual box-entry fraction first.

C. DIVERSIFICATION_FIRST
For each eligible candidate at the decision open:
- compute 60-session close-to-close returns ending strictly before entry date
- compute average absolute correlation versus currently held positions with sufficient history
- lower average absolute correlation gets priority
- if no valid correlations exist, use neutral 0.50
- tie: liquidity rank, then entry fraction, then symbol

D. MARGINAL_GEOMETRY_DIVERSIFICATION
Fixed causal score:
- upside_to_target = (target / entry_open) - 1
- stop_risk = 1 - lower*(1-exit_cost)/(entry_open*(1+entry_cost))
- geometric_RR = upside_to_target / stop_risk
- diversification_multiplier = 1 / (1 + average_absolute_60d_correlation)
- score = geometric_RR * diversification_multiplier
- higher score first
- tie: liquidity rank, then entry fraction, then symbol

E. HYBRID_LIQUIDITY_GEOMETRY
No fitted weights.
Rank candidates separately by:
- liquidity rank ascending
- geometric_RR descending
Final ordinal score = liquidity_position + RR_position.
Lower total ordinal score first.
Tie: lower entry fraction, then symbol.

## Capital fill
Sequential funding:
- each candidate receives its full frozen risk request up to remaining cash
- final candidate may receive partial cash
- later candidates receive zero
No leverage.

## Metrics
- total return / CAGR / MDD / Sharpe
- rolling 12m min / median / positive share
- yearly returns
- average exposure
- blocked / partial entries
- realized requested-risk ratio
- completed trades / PF / mean trade
- funded top5/top10 absolute PnL concentration
- average pairwise correlation of funded portfolio at entry where measurable

## Decision rule
A new allocator is supported only if:
- it materially improves return or risk-adjusted return versus LIQUIDITY_FIRST,
- MDD and rolling stability do not materially deteriorate,
- improvement is not isolated to one year,
- funded concentration does not materially worsen,
- no post-entry information is used.

Do not optimize formula weights after seeing results.
