# Task 1/4 Stage-3 Evidence Audit V1

Status: research-only / diagnostic-only. No production effect.

This stage is intentionally about evidence quality rather than finding a better-looking historical rule. It consumes already-produced Task 1/4 historical outputs and does not change any frozen Sequence, RMD3, Challenger, or Forward-OOS definition.

## Primary questions

1. How many effectively independent historical Sequence events remain after nearby events are clustered?
2. Does the D+1 entry advantage survive an event-by-event paired test rather than a comparison of two headline means?
3. Does RMD3 retain 10D information after controlling for DUAL severity and broad MA200 phase?
4. Does RMD3 survive a direct permutation test and cluster-level aggregation?
5. Can DUAL Severity / RMD3 improve leave-one-out calibration of the 10D prior-trough-break hazard over the unconditional base rate?
6. Do the main historical findings survive a single-event deletion and equal-year weighting?
7. What happens when the main exploratory p-values are viewed as one multiple-testing family?

## Frozen diagnostic conventions

- Event population: the 12 frozen `D_TO_BOTH_REBOUND_SCORE` historical completion events.
- Primary event-dependence clustering: consecutive completion events separated by <=20 market sessions belong to the same cluster.
- Cluster sensitivity: also report 10-session and 30-session definitions. These are diagnostics only, not alternative rules.
- Primary RMD horizon: 10 trading days.
- D+1 paired horizons: 5D, 10D, 20D.
- RMD3 high/low split used only for hazard calibration: the already-observed historical median from Stage-2; no threshold search is permitted.
- Severity high: the already-frozen Stage-2 diagnostic threshold `DUAL severity > 6pp`.
- Resampling seed: 140315.
- Bootstrap draws: 50,000.
- RMD permutation draws: 100,000.
- Multiple-testing family: Sequence placebo 5/10/20D + D+1 paired 5/10/20D + RMD3 permutation 3/5/10D. Report raw, Bonferroni, and Benjamini-Hochberg values.

## Interpretation constraints

- A small historical p-value is not Forward-OOS evidence.
- Year equal-weighting does not create additional independent years.
- Partial correlations with n=12 are descriptive and unstable by construction.
- Hazard calibration with n=12 is a feasibility diagnostic, not a deployable probability model.
- No result in this file may promote, demote, resize, or otherwise change production or existing OOS shadows.
- Any future promoted rule requires a new preregistration and genuinely future data.
