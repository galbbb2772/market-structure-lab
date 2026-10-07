# Pure Box Simple Core Candidate V1 — V18 Decision

Status: PREFREEZE_DRAFT / NOT YET FROZEN

## Decision
V18 does NOT satisfy every preregistered pre-freeze stress gate.
Do not promote to a frozen candidate yet.

## What passed

### 1. Universe robustness
Baseline remains strongly profitable in both universes.

Top500:
- 1.25% risk: +234.05%, MDD -17.32%, Sharpe 1.071
- 1.50% risk: +256.11%, MDD -17.58%, Sharpe 1.114

Top300:
- 1.25% risk: +208.02%, MDD -16.04%
- 1.50% risk: +236.67%, MDD -16.35%

### 2. Transaction-cost stress
At 20 bps per side (4x baseline), direct-entry variants remain strongly profitable.

Top500:
- 1.25% risk: +129.92%, MDD -20.40%
- 1.50% risk: +154.32%, MDD -20.35%

Top300:
- 1.25% risk: +124.07%, MDD -16.45%
- 1.50% risk: +152.62%, MDD -16.84%

Thus the edge is not explained by a fragile low-cost assumption.

### 3. Baseline rolling robustness
At baseline cost/direct entry:
Top500 rolling 12m positive share = 100% for both 1.25% and 1.50% risk.
Minimum rolling 12m return:
- 1.25%: +6.45%
- 1.50%: +7.68%

Top300 rolling 12m positive share = 100%.
Minimum rolling 12m return:
- 1.25%: +1.95%
- 1.50%: +0.80%

This is strong historical consistency.

## What failed

### Entry-delay stress
A one-session delay does not destroy total return, but materially damages drawdown and rolling-window stability.

Top500, baseline costs:
- 1.25%: +245.80%, MDD -28.23%, worst rolling 12m -19.25%
- 1.50%: +270.61%, MDD -26.19%, worst rolling 12m -12.66%

Top300, baseline costs:
- 1.25%: +164.41%, MDD -33.38%, worst rolling 12m -23.53%
- 1.50%: +160.93%, MDD -32.33%, worst rolling 12m -20.90%

Under 20 bps per side plus one-session delay:
Top500 MDD reaches -35.91% / -28.68%.
Top300 MDD reaches -40.13% / -34.68%.

Therefore the preregistered gate 'one-day delayed entry does not destroy the edge / rolling structure' is not satisfied on a risk-adjusted basis.

## Interpretation
The strategy's timing is structural, not cosmetic.
The edge is not merely 'wide + fresh + bottom-ish'. It depends on entering while price is still very close to the invalidation boundary.

This supports the economic mechanism:
- expected upside remains large,
- but waiting one more session increases path risk and worsens the relationship between entry and the box lower-bound invalidation point.

Do NOT repair this candidate by adding an ad-hoc confirmation or by retuning thresholds after V18.

## Next permitted research
Diagnose timing fragility without changing the frozen-looking core:
1. measure entry fraction migration from direct day to delayed day,
2. compare stop distance / reward-to-risk migration,
3. determine whether delayed-entry drawdowns come from paying up inside the box, overnight gaps, or clustered market-regime exposure,
4. preregister any future execution guard only after the mechanism is identified.

The current core remains a strong research candidate but is NOT formally frozen.
