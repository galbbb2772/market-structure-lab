# Large Relative Resilience Portfolio Robustness V4 — Preregistration

Status: historical robustness only. No production / forward-shadow change.

## Purpose
Translate the supported V3 mechanism into a portfolio-level robustness test without optimizing a threshold.

## Frozen gate
`relative_resilience_5d = stock_ret5 - beta60 * spy_ret5`

Natural, non-optimized split:
- RESILIENT: relative_resilience_5d >= 0
- UNDERPERFORMING: relative_resilience_5d < 0

No percentile threshold, search, or tuning is allowed.

## Event universe
Reuse the frozen Large Resilience × Exhaustion V2 feature ledger.

For fair comparisons, all three lanes use the same **feature-observable** eligible event set:
- beta60 / relative_resilience available;
- Top500 primary / Top300 robustness;
- Large only;
- Fresh age <=24 Top500 / <=23 Top300.

This means the V4 baseline is an observable-sample baseline, not the full canonical Large baseline.

## Frozen execution
- entry: existing following-session open
- lower-edge stop
- target: 60% primary, 80% robustness
- max hold: 20 sessions
- 5 bps each side
- daily-bar stop-first ambiguity convention unchanged

## Lanes
1. OBSERVABLE_BASELINE — all feature-observable events
2. RESILIENT_ONLY — relative_resilience_5d >= 0
3. UNDERPERFORM_ONLY — relative_resilience_5d < 0

## Allocation robustness
Run each lane with fixed requested allocation per entry:
- 5%
- 10% (primary)
- 20%

If simultaneous requests exceed available cash, use the existing proportional cash scaling.

No leverage.

## Time robustness
Independent calendar-year segments:
2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026Q1.

Also report descriptive compounded segment return for:
- discovery: 2019-2022
- validation: 2023-2026Q1
- all segments

Annual segments are independent resets and are NOT an exact continuous NAV.

## Metrics
Per year/lane/cap/target/allocation:
- total return
- MDD
- Sharpe
- average exposure
- completed trades
- PF
- mean trade

Aggregate:
- compounded segment return
- positive-year count
- average annual Sharpe
- worst annual MDD
- average exposure
- total trades
- average PF

## Support standard
A portfolio-level resilience effect is supported if RESILIENT_ONLY versus UNDERPERFORM_ONLY shows:
- higher compounded return in discovery AND validation;
- better or similar worst-year MDD;
- same broad ordering in Top300 and Top500;
- same broad ordering at 60% and 80%;
- ordering not dependent solely on the 10% allocation lane.

OBSERVABLE_BASELINE remains the practical comparator.

No lane is promoted to production from V4.
