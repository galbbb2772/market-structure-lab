# PRUNED16 Market-Score Rebaseline V1

Frozen on 2026-10-06 before any PRUNED16 Forward-OOS event is counted.

## Reason

Market Model V2 reduced the directional Active set from 19 to 16 after a conservative score-preservation pruning audit.

- Archive / no independent vote: `high_yield`
- Context only: `employment`, `geopolitical_risk`, `volume_speed`
- Raw histories are retained.
- The PRUNED16 score-preservation A/B passed with score correlation 0.991472 and 2022+ risk-separation delta +0.1193 pp.

Because Market State Box / Sequence / Task 1/4 use the Market Model composite score, their historical diagnostics must be rebaselined on the new score definition.

## Forward-OOS rule

The pre-PRUNED16 Task 1/4 Forward-OOS ledgers had zero eligible events:

- Market State Sequence Forward OOS: 0
- RMD3 Forward OOS: 0
- Early Sequence challenger: 0
- RMD2 Price+Score challenger: 0
- D+1 challenger: 0
- DUAL Severity challenger: 0

Therefore resetting the Forward-OOS boundary to **2026-10-06** loses no observed Forward-OOS event.

Historical development evidence remains historical. No PRUNED16 historical recomputation may be counted as Forward OOS.

## Compatibility gate

1. Rebuild Market State Box history from PRUNED16 Market Model history.
2. Compare old/new Market Score path and score-recovery flags.
3. Rebuild Sequence / Task 1/4 historical diagnostics.
4. If the frozen 12-event historical completion identity no longer survives, do not silently rewrite V1; create a new versioned historical study.
5. Only after the historical compatibility result is known may the zero-event Forward-OOS ledgers be re-frozen from 2026-10-06.

## Production effect

None beyond the already-approved PRUNED16 Market Model membership change. Task 1/4 remains research/shadow only.
