# DUAL / FRED Revision Sensitivity Stage-2 V1

Status: research-only / diagnostic-only. No production effect.

Purpose: quantify how sensitive the frozen DUAL trigger and downstream Task 1/4 Sequence event identity are to small plausible revisions / measurement error in the reconstructed 4-week net-liquidity and reserve-balance percentage changes.

## Frozen source and center-reproduction requirement
`docs/data/market_state_sequence_v1.json` is a summary artifact and does not persist its full daily DUAL panel. Therefore this diagnostic must rebuild the center daily DUAL panel once from `docs/data/market_state_box_v1.json` using the exact existing `build_market_state_sequence_v1.add_dual` implementation and current-history FRED source/timing rules.

The diagnostic is invalid and must hard-fail unless the unperturbed center cell reproduces the frozen historical identities:
- 58 raw DUAL episode onsets;
- 15 Early Sequence onsets;
- 12 Full Sequence onsets;
- Full Sequence dates exactly equal the existing frozen 12-event audit dates.

Only after this reproduction check may the synthetic perturbation grid be interpreted. The center rebuild can still inherit current-history FRED revisions; this is why exact reproduction is mandatory.

## Frozen perturbation grid
Apply additive percentage-point perturbations independently to the two rebuilt 4-week fields:
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
- Current FRED history may contain revisions; this perturbation grid is a sensitivity envelope, not a substitute for ALFRED vintage reconstruction.
- +/-0.50 pp is a fixed diagnostic perturbation, not an estimated revision distribution.
- No grid cell may be selected based on historical returns.
- A failure of exact center reproduction invalidates the run instead of being interpreted as sensitivity evidence.