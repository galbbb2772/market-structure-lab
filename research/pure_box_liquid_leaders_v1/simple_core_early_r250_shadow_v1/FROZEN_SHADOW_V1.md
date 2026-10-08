# Simple Core Early-R250 Shadow Candidate V1

Status: FROZEN_SHADOW_RESEARCH_CANDIDATE / FORWARD_OOS_REQUIRED

Freeze date: 2026-10-08

## Relationship to existing candidates
This candidate does NOT replace:
- Simple Core Candidate V1
- Simple Core Capital Candidate V1

It is a separate higher-risk capital overlay shadow.

## Frozen universe
Top500 liquid-leader proxy primary.
Top300 robustness only.

## Frozen signal/execution core
- Strict Wide + Fresh
- actual entry Bottom <=20%
- first eligible next-session open only
- missed direct execution = skip, no chase
- lower-bound stop
- target = lower + 0.60 * box range
- H15
- stop-first same-day ambiguity
- baseline tracking cost = 5 bps/side
- liquidity-first same-day capital queue
- single-name capital cap = 50%
- no leverage

## Frozen base risk
New symbols request fixed 1.25% account risk to lower-bound invalidation.

## Frozen early re-signal overlay
A repeated valid signal is treated as the SAME box state, not a new independent signal.

Add-on allowed only if:
- the same symbol is already held,
- repeated signal is valid at current session open,
- actual entry remains Bottom<=20%,
- existing holding age <=3 sessions,
- same original box lower / upper / target remain in force,
- holding age is NOT reset,
- total same-symbol stop risk after add-on does not intentionally exceed 2.50% of account equity,
- 50% single-name capital cap remains binding,
- add-on and new-symbol requests share the SAME liquidity-first capital queue.

No add-on is allowed from holding age >=4.

## Historical headline
Top500, 5bps/side:
- total return: +607.01%
- CAGR: 82.92%
- MDD: -17.21%
- Sharpe: 0.957
- rolling 12m minimum: +13.33%
- add-on events: 53

Top500, 10bps/side:
- total return: +524.74%
- MDD: -17.67%
- Sharpe: 0.912
- rolling 12m minimum: +9.11%

Top500, 20bps/side:
- total return: +387.22%
- MDD: -18.45%
- Sharpe: 0.820
- rolling 12m minimum: +1.28%

## Fragility findings
Add-on layer is concentrated:
- top1 add-on event absolute PnL share: ~59.8%
- top3 events: ~77.0%
- top5 events: ~83.3%
- top1 add-on symbol absolute PnL share: ~60.3%
- top5 symbols: ~84.2%
- 73.4% of positive add-on PnL came from 2025

However, the overlay is not purely a 2025 artifact:
- ex-2025 add-on slice PF: ~2.46
- ex-2025 add-on slice PnL remains positive
- full portfolio with ALL 2025 add-ons disabled still returned +412.74%
- that no-2025-add-on portfolio remained above the +373.36% baseline capital candidate

## Interpretation
The overlay has a plausible causal mechanism:
early repeated same-box observations can justify completing / increasing risk while the mean-reversion opportunity is still young.

But historical concentration is too high for promotion.

## Freeze discipline
Do not retune:
- age<=3
- 2.50% same-symbol risk ceiling
- 50% single-name capital cap
- H15
- Bottom<=20
- target60
- liquidity-first queue

Any change creates a new candidate version.

## Promotion discipline
This candidate remains SHADOW until genuine Forward OOS evidence exists.
