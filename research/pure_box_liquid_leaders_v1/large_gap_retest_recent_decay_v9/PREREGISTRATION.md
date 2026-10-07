# Large Gap Retest Recent-Decay Significance V9 — Preregistration

Date frozen: 2026-10-07

## Question
V8 found a robust 2021-2026 historical Top500 RETEST_LIFT advantage but every 2026 point estimate was negative.
Because 2026 contains only ~6 RETEST_LIFT and 6-7 NO_RETEST_LIFT observations per specification, test whether the apparent decay is statistically unusual under the frozen 2021-2025 state distributions.

## Frozen definitions
- Top500 primary only.
- Same V7/V8 EXTREME_GAP, RETEST_LIFT and NO_RETEST_LIFT labels.
- Target fractions: 0.60, 0.80.
- Gap methods: EXPANDING and FIXED_-1PCT.
- Historical reference: 2021-2025.
- Diagnostic year: 2026.
- No parameter or trade-rule changes.

## Monte Carlo design
For each of four specifications:
- Record 2026 sample sizes and observed state means/difference.
- Draw 20,000 bootstrap samples with replacement from the 2021-2025 RETEST_LIFT pool and NO_RETEST_LIFT pool, using the exact 2026 sample sizes.
- Estimate:
  1. P(simulated difference <= observed 2026 difference)
  2. P(simulated RETEST mean <= observed 2026 RETEST mean)
  3. P(simulated NO_RETEST mean >= observed 2026 NO_RETEST mean)

## Interpretation
- A specification has significant edge decay only when P(sim diff <= observed diff) < 0.05.
- If all four correlated specifications meet that condition: DECAY_EVIDENCE.
- If two or three meet it: DECAY_WARNING.
- Otherwise: SAMPLE_NOISE_PLAUSIBLE.
- Driver label:
  - RETEST_WEAKNESS if RETEST-tail p < 0.05 and NO_RETEST-tail p >= 0.05
  - CONTROL_STRENGTH if NO_RETEST-tail p < 0.05 and RETEST-tail p >= 0.05
  - BOTH if both < 0.05
  - NEITHER otherwise

The four specifications are correlated views of the same events and must not be treated as four independent experiments.
