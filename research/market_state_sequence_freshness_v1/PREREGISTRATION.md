# Market State Sequence Freshness / Second-Drop V1 — preregistration

Status: diagnostic research only. No Frozen V4 / MAIN-B / Market State Sequence V1 production rule is changed.

## Question

For the already-frozen `D_TO_BOTH_REBOUND_SCORE` event definition, does the *freshness* of the recovery confirmation help explain why some historical events mean-revert while others suffer a second drop?

This study does **not** redefine the 12 historical events and does **not** search for a new entry threshold.

## Frozen input

- Historical event set: `docs/data/market_state_sequence_event_audit_v1.json`.
- Event definition remains exactly `D_TO_BOTH_REBOUND_SCORE`.
- Historical event count must remain 12 at the time this V1 diagnostic is first run.
- Original Sequence V1 thresholds remain unchanged.

## Ex-ante / state features audited

For every frozen event, inspect only fields known on the event date:

- `confirmation_lag_sessions`: trading sessions from the associated DUAL episode start to full sequence confirmation.
- `ret_5d_pct`, `ret_20d_pct`, `ret_60d_pct`.
- `drawdown_from_60d_high_pct`.
- `breadth_20d_pct` and `min_breadth_pct_since_dual`.
- breadth rebound distance = `breadth_20d_pct - min_breadth_pct_since_dual`.
- `box_position` and `min_box_position_since_dual` when available.
- box rebound distance = `box_position - min_box_position_since_dual` when both exist.
- `market_score`, `market_score_d1`, `market_score_d3`.
- MA200 phase is descriptive only; it is not used to select a rule.

## Fixed freshness bands

These are descriptive coarse bands, fixed before this diagnostic is run; they are **not** optimized and must not be interpreted as validated thresholds:

- confirmation lag: `0-5`, `6-10`, `11-20`, `21+` trading sessions.
- confirmation breadth level: `<=20`, `(20,40]`, `(40,60]`, `>60` percentile.
- prior 20D SPX return: `<=-5%`, `(-5%,0%]`, `>0%`.

No alternative band grid may be searched in V1.

## Outcome / second-drop definitions

Forward outcomes remain labels only:

- T+1 / T+3 / T+5 / T+10 SPX return.
- 10D MFE / MAE.
- `second_drop_5d`: T+5 return < 0.
- `second_drop_10d`: T+10 return < 0.
- `severe_adverse_10d`: 10D MAE <= -5%.

The -5% severe-adverse line is a round risk magnitude chosen before analysis, not fitted to the 12-event sample.

## Statistical diagnostics

- Spearman rank correlation between each continuous state feature and T+5 / T+10 return, plus second-drop incidence where meaningful.
- Leave-one-out range of each feature/return Spearman correlation to expose single-event dependence.
- Fixed-band descriptive summaries: N, mean/median T+5/T+10, positive rate, second-drop rate, mean MFE/MAE.
- Event-by-event table sorted by confirmation lag.
- Explicit checks for year and MA200-phase concentration.

## Decision rule

This V1 diagnostic cannot promote or modify a strategy rule.

At most it may produce a mechanism hypothesis for a separately preregistered future test. The existing observation-only Forward-OOS sequence shadow remains unchanged.

## Guardrails

- No thresholds are selected after viewing this diagnostic.
- No event is removed because it is inconvenient.
- No forward-return value is used to classify event freshness.
- FRED current-history and reconstructed Market Score caveats from Sequence V1 remain in force.
