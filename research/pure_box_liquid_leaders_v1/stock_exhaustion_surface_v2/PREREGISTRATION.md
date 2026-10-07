# Large Stock Exhaustion Surface V2 — Preregistration

Status: mechanism research only. No production / forward-shadow changes.

## Motivation
Across the reconstruction program, two stock-level confirmation features repeatedly survived:
1. rebound_from_low_box
2. low_progress_box

Market-regime, market-recovery, relative-resilience, and abnormal-selloff severity hypotheses did not pass full robustness standards.

V2 asks whether the two surviving stock-level exhaustion variables are:
- complementary,
- redundant,
- or only useful when both are strong.

## Frozen sample
Use the existing Strategy Reconstruction V1 observations only.
No re-extraction and no new trade selection.

Filters:
- stage = confirmed_no_new_low_green
- scale = Large
- Top500 primary / Top300 robustness
- Fresh flags exactly as stored in Strategy Reconstruction V1
- discovery = 2019-2022
- validation = 2023-2026Q1

No market-state variable is used.

## Frozen quintile boundaries
Reuse the exact discovery quintile boundaries already persisted by Strategy Reconstruction V1.
Do NOT recompute cutpoints in V2.

Top300 Large:
- rebound_from_low_box: [0.0836437292, 0.1184405191, 0.1596507838, 0.2170920776]
- low_progress_box: [0.0212690810, 0.0420472317, 0.0702824600, 0.1091389339]

Top500 Large:
- rebound_from_low_box: [0.0851900393, 0.1220014993, 0.1639344262, 0.2204325817]
- low_progress_box: [0.0206461895, 0.0418768920, 0.0704091342, 0.1100164204]

## Descriptive 5x5 surface
Report the full 5x5 grid for:
- 20-session 60%-target-before-stop rate
- 20-session 80%-target-before-stop rate
- 20-session stop-first rate
- mean 10-session return
- mean 20-session MFE box progress
- sample size

The 5x5 grid is descriptive only. No individual cell may be selected as a production rule.

## Predeclared high/low interaction corners
Convert frozen quintiles into broad groups:
- HIGH = Q4 or Q5
- LOW = Q1 or Q2
- Q3 is excluded from the primary corner test.

Four corners:
1. BOTH_HIGH = rebound HIGH + low_progress HIGH
2. REBOUND_ONLY = rebound HIGH + low_progress LOW
3. LOW_PROGRESS_ONLY = rebound LOW + low_progress HIGH
4. BOTH_LOW = rebound LOW + low_progress LOW

## Primary complementarity hypothesis
For BOTH discovery and validation:
- BOTH_HIGH should have higher 60% target-before-stop rate than REBOUND_ONLY and LOW_PROGRESS_ONLY;
- BOTH_HIGH should have lower stop-first rate than REBOUND_ONLY and LOW_PROGRESS_ONLY;
- BOTH_HIGH should be stronger than BOTH_LOW.

This ordering should broadly agree in Top300 and Top500.

## 80% robustness
Repeat the same comparisons using the 80% target.

## Redundancy diagnostics
Report:
- Spearman(rebound_from_low_box, low_progress_box)
- within each rebound quintile, monotonic relationship of low_progress quintile with 60% target rate
- within each low_progress quintile, monotonic relationship of rebound quintile with 60% target rate

If one variable has little conditional information after fixing the other, classify the pair as mostly redundant rather than complementary.

## Support standard
Complementarity is supported only if:
- BOTH_HIGH beats each single-high corner in discovery and validation;
- Top300 and Top500 broadly agree;
- 60% and 80% target results broadly agree;
- sample counts are not pathologically small;
- conditional diagnostics show incremental information from both axes.

No new score, cutoff, or trading rule is promoted from V2 alone.
