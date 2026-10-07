# Large Gap Retest-Lift Candidate V1 — Decision Freeze

Frozen: 2026-10-07

## Status
FORWARD_OOS_PENDING / RESEARCH_CANDIDATE

Not a live-trading rule. No automatic execution.

## Frozen finding
Within Top500 liquid leaders, after an EXTREME_GAP event, the RETEST_LIFT state has a persistent historical advantage over NO_RETEST_LIFT.

State construction is frozen to the V7 definitions:
- EXTREME_GAP: either expanding prior-history 20th percentile of gap_component or fixed -1% control.
- RETEST: low_progress_box <= expanding prior-history median among extreme-gap observations.
- LIFT: close_lift_box > expanding prior-history median among extreme-gap observations.
- RETEST_LIFT requires both.
- All expanding thresholds use strictly prior years.

## Evidence chain
### V7 mechanism map
Top500: 4/4 specifications supported the retest mechanism.
- RETEST_LIFT mean trade about +0.85% to +1.11%.
- RETEST_LIFT PF about 1.34 to 1.42.
- NO_RETEST_LIFT mean trade about -1.04% to -1.37%.
- NO_RETEST_LIFT PF about 0.61 to 0.65.

Top300 did not pass the primary V7 support gate.

### V8 robustness audit
Top500: 4/4 specifications BROADLY_ROBUST.
The advantage survives:
- 2.5% / 97.5% winsorization
- symbol-balanced averaging
- deletion of any one year
- deletion of the best year
- symbol-cluster bootstrap

Top500 symbol-cluster bootstrap P(diff > 0):
- 0.6 / EXPANDING: 0.9966
- 0.6 / FIXED_-1PCT: 0.9970
- 0.8 / EXPANDING: 0.9994
- 0.8 / FIXED_-1PCT: 0.9946

### V9 2026 decay significance
2026 point estimates reverse, but the sample is only 6 RETEST_LIFT trades versus 6-7 NO_RETEST_LIFT trades per specification.

Pre-registered V9 result:
- significant decay specs: 1 / 4
- verdict: SAMPLE_NOISE_PLAUSIBLE
- correlated-spec p-values for obtaining a difference this weak under the 2021-2025 distributions:
  - 0.04935
  - 0.05355
  - 0.06550
  - 0.05950

The 2026 RETEST_LIFT mean itself is not significantly abnormal:
- tail p about 0.18 to 0.34.

For the 0.6 target views, the main anomaly is NO_RETEST_LIFT becoming unusually strong:
- upper-tail p about 0.024 to 0.029.

## Decision
1. Do not promote to a production strategy yet.
2. Do not retune thresholds to repair 2026.
3. Do not add Market Regime or new filters based on these six 2026 RETEST_LIFT observations.
4. Freeze the mechanism and observe it prospectively.
5. Keep Top300 as a negative/control universe; primary candidate is Top500 only.

## What would falsify the candidate prospectively
The forward observer should reject promotion if, after the minimum sample/horizon:
- RETEST_LIFT no longer has a positive mean advantage versus NO_RETEST_LIFT,
- or RETEST_LIFT PF <= NO_RETEST_LIFT PF,
- or the symbol-cluster bootstrap does not support diff > 0 at the frozen threshold.

No historical thresholds are to be changed after this freeze.
