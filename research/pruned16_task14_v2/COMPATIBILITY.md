# PRUNED16 Task1/4 V2 Compatibility Note

## Why V2 is required

The Market Model was pruned from the pre-2026-10-06 directional set to **PRUNED16**. A downstream replay showed that the frozen Task1/4 Full Sequence event identity is **not invariant** to that Market Score definition change.

The pre-PRUNED16 V1 event set had 12 complete historical events:

- 2019-06-04
- 2022-01-26
- 2022-03-09
- 2022-05-13
- 2022-05-23
- 2022-06-07
- 2022-07-01
- 2022-07-12
- 2022-09-28
- 2022-10-13
- 2022-10-25
- 2023-01-04

PRUNED16 produces 11 complete historical events:

- 2019-06-04
- 2022-01-28
- 2022-05-13
- 2022-05-23
- 2022-06-07
- 2022-07-01
- 2022-07-12
- 2022-09-28
- 2022-10-13
- 2022-10-25
- 2023-01-04

Material identity changes:

1. The January 2022 recovery completion shifts from **2022-01-26** to **2022-01-28**.
2. The **2022-03-09** Full Sequence completion no longer qualifies.
3. The other ten completion dates remain identical.

The compatibility replay also found **169 trading days** where the binary Score-Recovering state changed under PRUNED16.

## Versioning decision

Task1/4 V1 remains frozen under the pre-PRUNED16 Market Score and is not overwritten.

A parallel **PRUNED16 Task1/4 V2** lineage is rebuilt from the new 16-indicator score. Historical recomputation is development evidence, never Forward-OOS evidence.

The V2 prospective boundary is **2026-10-06**. The pre-reset Forward-OOS ledgers contained zero eligible events, so no observed prospective event is discarded by the version transition.
