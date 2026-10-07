# Large Relative Resilience Partial-Effect V3 — Decision

Status: completed mechanism diagnostic. No production change.

## Verdict

The 5-session relative-resilience signal survives multivariate controls and is therefore supported as an independent mechanism variable.

Primary regression controlled for:
- rebound_from_low_box;
- box width;
- box age;
- liquidity rank;
- beta60;
- SPY 5-session return;
- calendar-year fixed effects.

Discovery scaling was frozen and reused in validation.

## Sign replication

Across 2 universes × 2 targets × 2 periods × 4 outcomes = 32 preregistered sign checks:

- 31 / 32 had the hypothesized sign.
- The sole sign miss was Top500 / 60% / validation MFE, where the coefficient was small and negative.

Most importantly, every lane had:
- positive resilience coefficient for net trade return;
- positive resilience coefficient for target-before-stop probability;
- negative resilience coefficient for stop-before-target probability.

### Examples: validation partial effects per one discovery-SD increase in resilience

Top300:
- 60% target:
  - net return +0.375%
  - target probability +5.87pp
  - stop probability -6.09pp
- 80% target:
  - net return +0.508%
  - target probability +3.45pp
  - stop probability -6.17pp

Top500:
- 60% target:
  - net return +0.035% (weak t-stat)
  - target probability +3.43pp
  - stop probability -3.79pp
- 80% target:
  - net return +0.186%
  - target probability +2.46pp
  - stop probability -4.15pp

The path-probability effect is substantially more stable than the exact return-magnitude effect.

## Interaction with rebound

The predeclared resilience × rebound interaction did NOT replicate:
- discovery interaction coefficients were often negative;
- validation interaction coefficients frequently turned positive;
- MFE interactions were inconsistent.

Therefore:
- relative resilience is supported as an independent variable;
- a multiplicative synergy with rebound is NOT established;
- the V2 four-cell combination should not be promoted.

## Mechanism interpretation

The current evidence is more consistent with:

> At a structurally low Large-box location, market-adjusted relative strength is evidence that support is being accepted. Continued idiosyncratic weakness is evidence that the apparent discount may still be an active repricing process rather than a temporary mispricing.

This is different from a generic market-regime gate and different from a pure oversold score.

## Next step

Test the economically natural, non-optimized gate:

`relative_resilience_5d >= 0`

at the portfolio level, with:
- baseline vs resilient-only vs underperforming-only;
- Top500 primary / Top300 robustness;
- 60% / 80% exits;
- annual stability;
- allocation-cap robustness.

This remains historical robustness, not fresh Forward OOS proof.
