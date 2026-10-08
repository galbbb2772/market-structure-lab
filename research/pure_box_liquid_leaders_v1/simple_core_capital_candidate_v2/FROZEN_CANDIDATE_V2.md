# Simple Core Capital Candidate V2 — Early Re-Signal Pyramiding

Status: FROZEN_RESEARCH_CANDIDATE / AGGRESSIVE_SHADOW / FORWARD_OOS_REQUIRED

Freeze date: 2026-10-08

## Relationship to existing candidates
This does NOT replace:
- Simple Core Candidate V1
- Simple Core Capital Candidate V1

It is a separate aggressive capital-layer candidate.

## Frozen universe
Top500 liquid-leader proxy.

## Frozen signal core
- Strict Wide + Fresh
- actual entry Bottom <=20%
- first eligible next-session open only
- no confirmation
- missed direct next-open entry = skip, no chase
- lower-bound stop
- target = lower + 0.60 * box range
- H15
- stop-first same-day ambiguity
- baseline cost assumption 5 bps/side

## Initial position
- fixed 1.25% account risk to lower-bound invalidation
- 50% single-name capital cap
- no leverage
- same-day new-symbol cash competition resolved by liquidity-first sequential queue

## Frozen repeat-signal overlay
A repeated signal is NOT a new independent box.

An add-on is allowed only when:
- same symbol is already held
- the repeated signal is still valid at the current open
- actual entry remains Bottom <=20%
- same box / same lower stop / same target
- existing holding age <=3 sessions

When allowed:
- total same-symbol stop risk may be increased up to 2.50% of account equity
- add-on executes at the current valid open
- add-on and new-symbol requests share the SAME liquidity-first queue
- add-on has no special priority
- 50% single-name capital cap remains hard
- no leverage
- holding age is NOT reset
- H15 clock is NOT reset
- stop is NOT changed
- target is NOT changed

## Historical evidence — Top500
5 bps/side:
- total return: +607.01%
- CAGR: 82.92%
- MDD: -17.21%
- Sharpe: 0.957
- rolling 12m minimum: +13.33%
- rolling 12m positive share: 100%

10 bps/side:
- total return: +524.74%
- MDD: -17.67%
- rolling 12m minimum: +9.11%

20 bps/side:
- total return: +387.22%
- MDD: -18.45%
- rolling 12m minimum: +1.28%

## Fragility findings
The 2025 period materially amplifies the result, but the overlay is not entirely dependent on 2025.

Annual-block compounding excluding 2025:
- SKIP_OVERLAP: +84.43%
- FULL_R250: +92.18%
- EARLY_R250: +99.59%

EARLY_R250 add-on slices excluding 2025:
- n = 37
- mean slice return ≈ +2.40%
- PF ≈ 2.46
- total slice PnL positive

Concentration remains material:
- overall top1 absolute add-on PnL share ≈ 60.3%
- top5 ≈ 84.2%
But after excluding 2025:
- removing top1 contributing symbol still leaves positive add-on PnL
- removing top3 contributing symbols still leaves positive add-on PnL

## Single-name cap finding
50% remains frozen.
Raising the cap to 60% did not improve the risk/return profile:
- 5bps EARLY_R250 CAP50: +607.01%, MDD -17.21%
- 5bps EARLY_R250 CAP60: +588.79%, MDD -19.99%
Wider caps degraded further.

## Interpretation
Repeated same-box observations contain useful historical sizing information primarily in the first 3 holding sessions.
This is a capital-sizing overlay, not a new signal factor.

## Freeze discipline
Do not retune after 2026-10-08:
- age <=3
- initial risk 1.25%
- repeated-signal risk ceiling 2.50%
- 50% single-name cap
- Bottom<=20%
- target60
- H15
- liquidity-first queue
- direct-next-open execution

Any changed logic must become a separate candidate version.

## Promotion discipline
Historical results are exploratory validation, not forward proof.
No production promotion without forward OOS.
