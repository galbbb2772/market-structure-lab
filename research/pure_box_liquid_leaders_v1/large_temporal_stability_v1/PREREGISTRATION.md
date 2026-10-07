# Large Temporal Stability / Structural Break Audit V1

Status: diagnostic audit only. No production changes and no new alpha selection.

## Why
Multiple independent studies show a repeated pattern:
- Large-box mean reversion is weak in much of 2019-2022;
- materially stronger in 2023-2026Q1;
- several feature directions flip across the same boundary.

Before adding more factors, audit whether this reflects:
1. a genuine economic regime shift;
2. changing opportunity geometry;
3. changing liquid-universe composition;
4. changing data coverage / source characteristics.

## Frozen trade setup
- Large Fresh only
- Top500 primary / Top300 robustness
- Fresh age <=24 Top500 / <=23 Top300
- no_new_low_green confirmation
- following-session open entry
- lower-edge stop
- primary 60% target
- robustness 80% target
- max hold 20 sessions
- 5 bps each side
- no new filter

## Time resolution
Report:
- calendar year
- calendar quarter
- rolling trailing 4-quarter event economics

No breakpoint date is optimized.

## Trade stability metrics
Per quarter and year:
- N
- mean / median net trade
- PF
- win rate
- target / stop / max-hold shares
- mean holding sessions
- MFE / MAE

## Opportunity-geometry diagnostics
Per quarter / year:
- box width %
- box age
- entry box position
- stop distance from entry
- target distance from entry
- liquidity rank
- ADV20

## Universe / data-coverage diagnostics
Per year:
- unique signal symbols
- unique traded symbols
- median / mean liquidity rank
- median ADV20
- number of source trading dates
- candidate count
- confirmed count
- events retained after full-horizon eligibility

## Predeclared stability controls
To test whether post-2023 strength is just geometry/composition drift:
- discovery 2019-2022 defines fixed quintiles for box width and box age;
- report 2023-2026Q1 event economics within the same width quintiles and age quintiles;
- report common central geometry subset:
  width Q2-Q4 AND age Q2-Q4, using discovery cutpoints.

If post-2023 improvement remains inside fixed geometry bins, geometry drift alone is insufficient.

## Interpretation
This audit may identify a structural break but may NOT create a trading gate.
No year/date threshold may be used in production.
If a break is real, the next research question must explain the economic mechanism rather than simply trade only after the break.
