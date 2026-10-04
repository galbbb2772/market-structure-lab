# Residual Mean-Reversion Distance V1 — preregistration

Status: diagnostic research only. No MAIN-B / Frozen V4 / existing Sequence Forward-OOS shadow rule is changed.

## Question

For the already frozen `D_TO_BOTH_REBOUND_SCORE` sequence events, does the amount of **remaining mean-reversion distance at confirmation** vary monotonically with subsequent S&P 500 returns?

This is a mechanism diagnostic after Sequence Freshness V1. It is not fresh OOS model selection.

## Frozen event set

- Source event set: `docs/data/market_state_sequence_event_audit_v1.json`.
- Event definition remains `D_TO_BOTH_REBOUND_SCORE`.
- Historical event count must remain exactly 12.
- No event may be added, removed, relabeled, or re-declustered for this study.

## Continuous components

All components are oriented so **higher = more residual mean-reversion distance / less repair already completed**.

1. **Price residual**
   - Compute S&P 500 trailing 20-session return for every market-state date.
   - On each date, compute its expanding historical percentile using only observations available through that date.
   - `price_residual = 1 - percentile(ret20)`.
   - Minimum history for a usable percentile: 252 observations.

2. **Breadth residual**
   - Reuse the already point-in-time three-index breadth percentile `breadth_20d_pct` from Market State Box V1.
   - `breadth_residual = 1 - breadth_20d_pct / 100`.

3. **Market Score residual**
   - Reuse the already point-in-time expanding Market Score percentile `market_score_pct` from Market State Box V1.
   - `score_residual = 1 - market_score_pct / 100`.

4. **Box residual**
   - If an eligible current S&P 500 box exists, use current `box_position`.
   - `box_residual = 1 - clip(box_position, 0, 1)`.
   - Missing current box positions stay missing; they are not backfilled from the historical minimum.

## Frozen composites

- **RMD3 (primary)** = equal-weight mean of `price_residual`, `breadth_residual`, and `score_residual`.
- **RMD4 (secondary subset)** = equal-weight mean of the same three components plus `box_residual`, only for events with current box position available.
- No optimized weights, nonlinear transforms, thresholds, or parameter grids are allowed.

## Diagnostics

For RMD3 and RMD4, report:

- Spearman correlation with T+3 / T+5 / T+10 return;
- leave-one-out min / median / max Spearman;
- same Spearman after removing the known 2022-06-07 failure event;
- rank-ordered event table;
- lower-half vs upper-half descriptive outcomes (split only by rank count, not promoted as a threshold);
- mean score for second-drop vs non-second-drop events;
- mean score for severe-adverse vs non-severe-adverse events when both groups exist.

Component-level Spearman diagnostics are also reported, but components cannot be reweighted from this study.

## Interpretation guardrails

- Higher RMD is hypothesized to mean more unexhausted mean-reversion distance; therefore a positive association with future returns is the hypothesized direction.
- The 12 historical events were already observed before this study, so any attractive relationship is post-discovery diagnostic evidence only.
- RMD3 is primary because it is available for all 12 frozen events. RMD4 is secondary because current box availability is incomplete.
- No result from this V1 may change production, MAIN-B, Frozen V4, or the already frozen Sequence Forward-OOS shadow.
- Any future trading use requires a separate preregistration and independent Forward-OOS sample.
