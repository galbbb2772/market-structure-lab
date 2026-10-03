# Market State Sequence V1 — Event Audit Preregistration

Status: research only. This audit does not change Market State Sequence V1 thresholds and does not alter Frozen V4 / MAIN-B.

## Frozen target
Audit only the already-defined onset events of `D_TO_BOTH_REBOUND_SCORE` from Market State Sequence V1:

DUAL_DRAIN -> Breadth <= 20 historical percentile -> Box position <= 0.25 occurred in the same DUAL path -> Breadth rebounded from the post-DUAL trough -> Market Score D1 > 0 and D3 > 0.

No new gate is introduced.

## Event-level fields
For each independent onset event, publish:
- onset date and calendar year
- source DUAL episode start/end and lag from episode start to sequence confirmation
- S&P 500 close
- trailing 5D / 20D / 60D return at onset
- drawdown from trailing 60-session high at onset
- current box position and minimum box position observed since the DUAL episode start
- current Breadth percentile and minimum Breadth percentile observed since the DUAL episode start
- Market Score, D1, D3
- past-only MA200 phase: bull_rising / bull_weakening / bear_falling / bear_recovery, using close vs trailing MA200 and trailing MA200 20-session slope
- forward 1D / 3D / 5D / 10D, MFE10 and MAE10 already present in the V1 state table

## Descriptive grouping
Only existing/non-optimized groupings are allowed:
- calendar year
- pre-2022 / 2022+
- 2024+
- the four pre-existing MA200 phases

Recent returns, drawdown, box depth, Breadth trough and lags remain continuous descriptive fields. Do not create an after-the-fact threshold from them in V1.

## Robustness
Report:
1. full independent-event statistics;
2. leave-one-out range for 5D and 10D mean returns;
3. results after removing the single best 10D event;
4. results after removing the single worst 10D event;
5. year concentration and phase concentration;
6. whether 2024+ contains any independent event.

## Shadow decision rule
This audit may create an **observation-only Forward OOS shadow**, but never a production rule.

Historical evidence is *not sufficient for promotion* unless all are true:
- at least 20 independent historical events overall;
- at least 5 events pre-2022 and at least 5 events from 2022 onward;
- at least 3 historical events from 2024 onward;
- full and 2022+ 5D and 10D mean returns are above their corresponding unconditional baselines;
- no material sign reversal in 2024+.

If these conditions are not met, the only allowed next step is an observation-only shadow that records future sequence onsets and realized 1/3/5/10D outcomes. It must not change selection, position size, entry, exit, or risk.
