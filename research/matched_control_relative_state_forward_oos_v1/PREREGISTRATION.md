# Matched-Control Relative-State Edge — Forward OOS V1

**Freeze boundary:** market dates through 2026-10-06 are historical development data.  
**Mode:** append-only observation; no production effect.  
**Priority:** T1 core Task1/4 thesis.

## Question

Does a future complete ordered repair transition outperform comparable weak-market states after the event becomes observable?

The historical PRUNED16 robustness grid was positive at 10D and 20D, but historical robustness is not Forward OOS evidence.

## Event

Use the already-frozen complete Sequence onset:
`D_TO_BOTH_REBOUND_SCORE`.

Only event onsets with `event_date > 2026-10-06` may enter this ledger.

## Prospective matching rule

For each new future event, lock controls at first observation.

Primary matching specification is the historical robustness study's **predeclared center cell**:
- K = 5 controls;
- exclusion = 20 market sessions;
- features:
  - ret20_pct
  - rv20_pct
  - net_liq_4w_pct
  - reserves_4w_pct
  - breadth_20d_pct
  - box_position
  - market_score
- Euclidean distance after feature standardization on the eligible point-in-time control pool;
- require at least 5 available feature differences;
- exact MA200 phase match when at least K controls exist, otherwise use the full eligible pool.

This is not a best-cell selection: K=5 / exclusion=20 was explicitly the center cell before the historical robustness grid was run.

## Point-in-time control pool

At a future event index i:
- a control date must be at least 20 market sessions before i, so its 20D outcome is already observable;
- it must have a complete 20D forward outcome;
- it must not be within ±20 sessions of any complete Sequence onset known up to the event;
- the event itself and all future dates are impossible controls.

The chosen control dates, distances, features and already-known control outcomes are immutable once locked.

## Outcomes

For each future event:
- event 10D return;
- event 20D return;
- matched-control mean 10D / 20D return;
- 10D / 20D lift = event return − control mean.

Outcomes may only be filled when they mature. Existing first-seen fields and selected controls are never rewritten.

## Review gate

No formal review until all are true:
- at least 20 mature 20D future events;
- at least 12 calendar months from the first future event;
- at least 8 independent 20-session event clusters;
- no unresolved immutable-field discrepancy.

Passing the gate does **not** change production. It only permits a separate preregistered review.

## Guardrails

- no historical backfill counts as Forward OOS;
- no threshold tuning;
- no alternative K/exclusion cell selection;
- no automatic promotion;
- no MAIN-B or Task1/4 production change.
