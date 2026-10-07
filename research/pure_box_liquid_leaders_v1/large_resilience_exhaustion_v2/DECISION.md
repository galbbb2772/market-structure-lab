# Large Resilience × Exhaustion V2 — Decision

Status: completed mechanism diagnostic. No production change.

## Verdict

The full complementarity hypothesis is NOT supported under the preregistered standard.

### What replicated best
The most stable contrast was **relative resilience within strong rebound**.

Top500:
- 60% target:
  - discovery: mean +0.2514%, target-share +2.00pp, stop-share -2.34pp versus underperformers within strong rebound
  - validation: mean +1.1308%, target-share +10.22pp, stop-share -14.88pp
- 80% target:
  - discovery: mean +0.2606%, target-share +1.42pp, stop-share -2.09pp
  - validation: mean +1.4880%, target-share +6.05pp, stop-share -15.98pp

Top300:
- 80% target replicated the same direction in discovery and validation.
- 60% target had positive mean-return contrast in both periods, but discovery target/stop shares did not improve, so this lane is weaker.

Thus short-horizon relative resilience appears to contain information that is not fully explained by rebound strength.

### What did not replicate cleanly
**Strong rebound versus weak rebound, conditional on resilience**, did not satisfy the preregistered discovery/validation expectancy standard:
- discovery mean-return contrasts were negative for both Top300 and Top500;
- validation contrasts turned positive and had much better target/stop profiles.

This means the discovery-median rebound threshold is not stable enough to claim an independent expectancy effect.

The joint hypothesis **RESILIENT_STRONG best / UNDERPERFORM_WEAK worst** also failed the strict discovery/validation mean-return replication test:
- discovery mean differences were generally negative or near zero;
- validation differences became strongly positive.

Therefore the four-cell combination is not eligible for promotion.

## Interpretation

The strongest surviving mechanism is narrower than expected:

> After a Large-box support/confirmation event, stocks that have held up better than their beta-implied SPY move are more likely to complete the mean-reversion path than stocks that are still showing market-adjusted relative weakness.

This is more consistent with **support acceptance / relative strength** than with a pure "deeper oversold = better" thesis.

Rebound-from-low remains useful as a descriptive path-quality variable, especially for target/stop incidence, but V2 does not establish it as an independent return-ranking feature under the frozen median split.

## Governance
- no hard resilience gate is promoted;
- no rebound threshold is promoted;
- no combined cell is promoted;
- next use requires a separately preregistered robustness / walk-forward test.
