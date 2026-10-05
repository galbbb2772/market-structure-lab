# Task 1/4 Prospective Evaluation Protocol V1

Status: preregistered evaluation layer only. No automatic promotion and no production effect.

This protocol is frozen after the historical Stage-2/Stage-3 diagnostics and before any Forward-OOS event exists after the existing 2026-10-02 freeze boundary. It evaluates already-frozen ledgers; it does not redefine their signals.

## Shared readiness gate

A conclusion remains `PENDING` until all of the following are true for the relevant test:

- at least 20 mature 10-trading-day Forward-OOS events;
- at least 12 calendar months from the first Forward-OOS event to the latest mature event;
- at least 8 independent event clusters using the frozen diagnostic convention that consecutive eligible events <=20 market sessions apart share a cluster;
- no unresolved immutable-field recomputation discrepancy in the source ledger.

Passing a statistical test does not automatically promote a model. A separate review is required.

## Primary prospective tests

### A. RMD3 Champion diagnostic

Population: frozen Full Sequence completion events after 2026-10-02.

Primary outcome: 10D forward S&P 500 return.

Primary statistic: Spearman correlation between frozen event-date RMD3 and 10D return.

Pass condition after readiness: rho > 0 and two-sided permutation p <= 0.05 using 100,000 fixed-seed permutations.

### B. D+1 Entry Challenger

Population: the same Full Sequence event dates with both Day0 and D+1 10D outcomes mature.

Primary statistic: paired mean difference `D+1 10D return - Day0 10D return`.

Pass condition after readiness: mean paired difference > 0 and exact sign-flip two-sided p <= 0.05.

### C. DUAL Severity Hazard Challenger

Population: mature Full Sequence hazard events.

Primary outcome: `break_prior_trough_10d`.

Primary predictor: frozen `HIGH_DUAL_SEVERITY = severity_pp > 6.0`.

Primary score: leave-one-out Brier score of severity-conditioned Laplace-smoothed probabilities versus leave-one-out unconditional base-rate probabilities.

Pass condition after readiness: severity-conditioned Brier score < unconditional Brier score AND observed break rate is higher in HIGH_DUAL_SEVERITY than in the low-severity group.

### D. Early Sequence Challenger

Population: frozen Early Sequence onset events after 2026-10-02.

Primary outcome: 10D forward S&P 500 return.

Reference: unconditional 10D return over all market dates in the Forward-OOS observation window with a mature 10D outcome.

Pass condition after readiness: Early Sequence mean 10D return > reference mean and positive-return rate > 50%.

## Family-level reporting

The four primary tests are reported together. No single result changes MAIN automatically. Raw evidence is shown first; a Holm-style multiplicity flag is also reported for the two tests with exact/permutation p-values (RMD3 and D+1). Hazard and Early Sequence are treated as predictive/calibration gates, not converted into post-hoc p-values.

## Fixed computation conventions

- Random seed: 140401.
- RMD3 permutations: 100,000.
- Event clustering: <=20 market sessions joins adjacent eligible events.
- All first-seen signal/score fields remain append-only and immutable.
- Historical development events <=2026-10-02 never enter prospective counts.
- Missing or immature outcomes remain missing; they are never imputed as zero.
- Any future modification to these conditions creates a new protocol version and cannot rewrite V1 history.
