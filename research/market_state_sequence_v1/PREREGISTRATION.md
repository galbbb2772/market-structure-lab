# Market State Sequence V1 — preregistration

Status: research only. No Frozen V4 / MAIN-B rule is changed.

## Question

Do market states contain more information as an ordered transition than as same-day hard gates?

The sequence studied is:

`DUAL_DRAIN / liquidity stress -> weak breadth -> box-bottom structure -> breadth rebound -> Market Score recovery`

The goal is descriptive / conditional forward-return research, not production trading logic.

## Frozen inputs and definitions

- Daily market-state source: `docs/data/market_state_box_v1.json`.
- DUAL_DRAIN uses the already researched definition:
  - net liquidity 4-week change <= -2%; and
  - reserve balances 4-week change <= -2%.
- Macro timing is availability-lagged and shifted one calendar day before it may affect a market date.
- Breadth low: three-index breadth historical percentile <= 20. This reuses the existing V1 threshold; it is not optimized here.
- Box bottom: eligible S&P 500 box position <= 0.25. This reuses the existing V1 threshold; it is not optimized here.
- Market Score recovery: D1 > 0 and D3 > 0. This reuses the existing V1 definition.
- Recent DUAL window: active DUAL or <= 10 trading sessions since the last DUAL day.
- Post-DUAL descriptive windows: 1-3, 4-10, and 11-20 trading sessions after release.
- Breadth recent-low window: previous/current 5 trading sessions.
- Box recent-bottom window: previous/current 5 trading sessions.
- Sequence-event samples are onset events and are de-clustered by at least 5 trading sessions.

## Sequence flags

1. `D_TO_BREADTH_LOW`: recent DUAL and breadth <=20 occurred since the current/recent DUAL anchor.
2. `D_TO_BREADTH_REBOUND`: #1 plus current breadth is above its post-anchor trough and improving versus the prior trading session.
3. `D_TO_BOX_BOTTOM`: recent DUAL and box-bottom occurred since the DUAL anchor.
4. `D_TO_REBOUND_SCORE`: #2 plus Market Score D1>0 and D3>0.
5. `D_TO_BOTH_REBOUND_SCORE`: recent DUAL, both breadth-low and box-bottom occurred since the DUAL anchor, breadth has rebounded from the post-anchor trough, and Market Score is recovering.

No threshold grid or weight optimization is allowed in V1.

## Outcomes

For each DUAL phase and each sequence onset event, report S&P 500 T+1 / T+3 / T+5 / T+10:

- sample count;
- mean and median return;
- positive-return rate;
- p10 / p90;
- 10-day MFE / MAE when available;
- difference in mean return versus the unconditional baseline over the same time segment.

Time stability is reported for:

- full available sample;
- pre-2022;
- 2022+;
- 2024+.

## Guardrails

- No future state values may be used to classify a date.
- Forward returns are outcomes only.
- Same-day all-four V1 is not resurrected by tuning thresholds.
- FRED current-history retrieval can contain revisions; this is not ALFRED vintage data and therefore is not strict point-in-time macro OOS evidence.
- Reconstructed sentiment / Market Score histories retain the same caveat as Market State Box V1.
- Any attractive historical sequence remains research-only until separately frozen and Forward-OOS tested.
