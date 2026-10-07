# Pure Box Same-Cohort Timing V21

Status: diagnostic only. No tuning.

## Purpose
V20 restored drawdown by revalidating Bottom<=20% at delayed execution, but only ~60% of candidates survived.
This test isolates timing from cohort selection.

## Cohorts
For each Top300/Top500 universe:
A. SURVIVOR cohort = original Bottom<=20% candidates whose +1-session delayed open is also <=20%.
B. SKIPPED cohort = original Bottom<=20% candidates that fail delayed revalidation.

For SURVIVOR cohort compare:
1. direct next-session-open execution
2. +1-session delayed execution
Same signals, same cohort, same 60% target / lower stop / H20 / risk sizing.

For SKIPPED cohort report direct-entry standalone portfolio as attribution.

Risk budgets: 1.25%, 1.50%
Costs: 5 bps per side primary, 20 bps robustness.

## Interpretation
If survivor-direct and survivor-delayed have similar rolling stability, V20 degradation is mostly cohort sparsity.
If survivor-delayed is materially worse than survivor-direct, latency itself still harms path quality even when Bottom<=20% is respected.
