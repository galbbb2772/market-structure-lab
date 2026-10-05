# Mechanism Graph Stage-2 V1

Status: research-only / diagnostic-only. No production effect.

Purpose: test whether the observed Task 1/4 stage order has directional transition structure beyond same-regime coincidence.

## Frozen source data
Use `docs/data/cross_family_transition_stage2_v1.json` exactly as produced by the frozen cross-family transition study. Do not reconstruct or alter event definitions.

## Frozen core directed pairs
Primary forward directions:
1. DUAL onset -> Breadth Low
2. Breadth Low -> Box Bottom
3. Box Bottom -> Breadth Rebound10
4. Breadth Rebound10 -> Score Recovery

Secondary structural links:
5. Breadth Rebound10 -> Early Sequence
6. Score Recovery -> Full Sequence
7. DUAL onset -> Early Sequence
8. DUAL onset -> Full Sequence

For each link also evaluate the exact reverse direction.

## Primary horizon
- 20 trading sessions.
Secondary horizons: 5, 10, 40 sessions.

## Existing matched controls
The source transition study already reports, for each source event and horizon, the source transition hit rate and a regime-matched control hit rate. Those definitions are frozen:
- same above/below-SMA200 regime;
- same RV20 >=20% / <20% regime;
- controls outside +/-20 sessions of source events;
- nearest by IQR-normalized trailing 20D return and RV20.

## Bootstrap
Reconstruct source-event first-hit outcomes and source-specific matched-control probabilities using the same event lists and control rule as the frozen transition study, then run deterministic-seed 20,000 event-level bootstrap resamples for each directed link/horizon.
Report:
- treatment hit rate;
- matched-control expected hit rate;
- excess hit-rate pp;
- bootstrap 95% CI of excess;
- one-sided bootstrap probability excess <= 0;
- median first-hit lag among hits.

## Directional asymmetry
For each forward/reverse pair report:
- forward excess hit-rate minus reverse excess hit-rate at 20D;
- forward and reverse bootstrap CIs separately;
- whether the sign pattern is consistent with the hypothesized order (forward excess > reverse excess).
This is descriptive mechanism evidence, not causal proof.

## Guardrails
- No transition may change production or Forward-OOS definitions.
- Event overlap and small source counts reduce effective independence; bootstrap is diagnostic, not a guarantee of IID sampling.
- Do not optimize horizons, links, or event definitions from the results.
- A positive directional asymmetry is not proof of causality.