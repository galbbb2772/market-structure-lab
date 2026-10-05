# DUAL / FRED Revision Sensitivity Stage-2 V1

Status: research-only / diagnostic-only. No production effect.

Purpose: quantify how sensitive the frozen DUAL trigger and downstream Task 1/4 Sequence event identity are to small plausible revisions / measurement error in the already reconstructed 4-week net-liquidity and reserve-balance percentage changes.

## Frozen source
Use `docs/data/market_state_sequence_v1.json` as the source of market dates, net_liq_4w_pct, reserves_4w_pct and all non-liquidity market-state fields. Do not fetch a new FRED history in this diagnostic.

## Frozen perturbation grid
Apply additive percentage-point perturbations independently to the two 4-week fields:
- net_liq_4w_pct: -0.50 / 0.00 / +0.50 pp
- reserves_4w_pct: -0.50 / 0.00 / +0.50 pp
Total 9 fixed cells.

In every cell recompute only:
`dual_drain = shifted_net_liq_4w_pct <= -2.0 AND shifted_reserves_4w_pct <= -2.0`
Then rerun the existing frozen `enrich_sequence` state machine without changing Breadth Low, Box Bottom, RECENT_DUAL, PATH_WINDOW, Score Recovery or de-clustering definitions.

## Event sets
For every grid cell report:
- DUAL onset dates;
- Early Sequence onset dates, frozen definition and 5-session de-cluster;
- Full Sequence onset dates, frozen definition and 5-session de-cluster;
- 5D/10D/20D forward-return summaries for Early and Full Sequence.

## Event identity stability vs center cell (0,0)
For DUAL / Early / Full separately report:
- center count and variant count;
- exact-date overlap count and Jaccard;
- center events with a variant event within +/-3 trading sessions;
- variant events with a center event within +/-3 trading sessions;
- median nearest trading-session date gap where a counterpart exists.

Also aggregate across all 8 non-center perturbation cells:
- minimum / median / maximum event count;
- minimum exact Jaccard;
- minimum center-event +/-3-session retention;
- number of cells preserving every center event within +/-3 sessions.

## Interpretation
This is not a threshold search. A cell with better returns is not a candidate rule. The purpose is robustness to measurement/revision noise only.

## Guardrails
- No production or Forward-OOS definition may change.
- Current FRED history itself may contain revisions; this perturbation grid is a sensitivity envelope, not a substitute for ALFRED vintage reconstruction.
- +/-0.50 pp is a fixed diagnostic perturbation, not an estimated revision distribution.
- No grid cell may be selected based on historical returns.