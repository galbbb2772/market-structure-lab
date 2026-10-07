# Large Idiosyncratic Dislocation V1 — Decision Note

Status: completed mechanism diagnostic. No production change.

## Pre-registered hypothesis
Higher stock-specific underperformance relative to beta-implied SPY movement was expected to represent deeper temporary mispricing and therefore stronger subsequent Large-box mean reversion.

## Result
The hypothesis was not supported.

The more stable direction, especially for the 5-session feature, was the opposite:
stocks that were relatively resilient versus their beta-implied market move tended to have better target rates and lower stop rates than stocks that had suffered larger idiosyncratic drawdowns.

For the 20-session residual, discovery was not stable enough to treat the inverse relationship as a robust mechanism, although validation strongly favored the more resilient side.

For the 5-session residual, the inverse direction appeared more consistently across:
- Top300 and Top500;
- 60% and 80% target definitions;
- discovery and validation endpoint comparisons.

The continuous correlations remain modest, so this does not justify a hard trading threshold.

## Interpretation
This weakens the simple "the more stock-specific oversold, the better" thesis.

A more plausible mechanism is:
- price reaches a structurally low box location;
- selling stops / price reclaims away from the low;
- the stock simultaneously shows short-horizon relative resilience versus the market.

That combination is closer to "support is being accepted" than to "deep oversold."

## Next test
Test whether 5-session relative resilience contains information independent of the previously identified selling-exhaustion feature `rebound_from_low_box`.

No V1 threshold or quintile is promoted.
