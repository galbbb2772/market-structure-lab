# Large Relative Resilience Partial-Effect V3 — Preregistration

Status: mechanism research only. No production / forward-shadow change.

## Question

Does 5-session market-adjusted relative resilience contain information beyond the Large-box geometry and confirmation-path variables that are already known to matter?

This study is specifically designed to rule out the explanation that the apparent resilience effect is only a proxy for:
- stronger rebound from the low;
- wider boxes;
- fresher boxes;
- liquidity-rank differences;
- beta differences;
- contemporaneous SPY 5-session return.

## Frozen event / execution setup

Reuse the completed Large Resilience × Exhaustion V2 event ledger:
- Top500 primary / Top300 robustness;
- Large only;
- Fresh age <=24 Top500 / <=23 Top300;
- bottom-20% signal;
- no_new_low_green confirmation;
- following-session open entry;
- lower-edge stop;
- 60% primary target / 80% robustness target;
- max hold 20 sessions;
- 5 bps each side.

No event definition or exit rule changes.

## Primary explanatory variable

`relative_resilience_5d = stock_ret5 - beta60 * spy_ret5`

Higher = the stock held up better than its beta-implied SPY movement.

The variable is continuous. No threshold is optimized.

## Controls

All controls are known by confirmation-date close:

1. `rebound_from_low_box`
2. `box_width_pct = (upper - lower) / ((upper + lower)/2)`
3. `box_age_sessions`
4. `liquidity_rank`
5. `beta60`
6. `spy_ret5`
7. calendar-year fixed effects within each study period

No additional variables may be added after seeing results.

## Scaling

For each Top300/Top500 × target lane:
- compute mean and standard deviation of each continuous regressor using DISCOVERY 2019-2022 only;
- apply those frozen discovery scaling parameters to both discovery and validation;
- year dummies are unscaled.

Thus the resilience coefficient represents approximately a one-discovery-standard-deviation change.

## Outcomes

Separate OLS / linear-probability models:
1. net trade return
2. target-before-stop indicator
3. stop-before-target indicator
4. MFE return

Use HC1 heteroskedasticity-robust standard errors.

## Primary model

Outcome ~ relative_resilience_5d
        + rebound_from_low_box
        + box_width_pct
        + box_age_sessions
        + liquidity_rank
        + beta60
        + spy_ret5
        + year fixed effects

## Secondary interaction model

Add:
`relative_resilience_5d * rebound_from_low_box`

The interaction is descriptive only. V3 can establish a resilience partial effect even if the interaction is unstable.

## Discovery / validation

- discovery: 2019-2022
- validation: 2023-2026Q1

Report for every universe/target/outcome:
- coefficient
- HC1 standard error
- t-stat
- N
- R²

## Support standard

Independent resilience evidence requires the relative-resilience coefficient to have the hypothesized sign in:
- discovery AND validation;
- Top300 AND Top500;
- 60% AND 80% exits.

Hypothesized signs:
- net return: positive
- target indicator: positive
- stop indicator: negative
- MFE: positive

Statistical significance is supportive but NOT required by itself; sign replication is primary.

No production gate, ranking weight, or threshold may be promoted from V3.
