# PRUNED16 V2 Matched-Control Robustness — Preregistration

Frozen before running the robustness grid.

## Question

The PRUNED16 V2 complete Sequence has weak unconditional 5–10D forward returns, but the historical matched-control comparison still shows positive relative lift, especially at 10D and 20D.

This study asks whether that relative-state edge survives reasonable, predeclared matching perturbations.

## Frozen event definition

Use the 11 complete Sequence events from:

`docs/data/pruned16_v2/market_state_sequence_event_audit_v1.json`

No event is added, removed, or relabeled inside this study.

## Frozen matching features

Base feature set:

- ret20_pct
- rv20_pct
- net_liq_4w_pct
- reserves_4w_pct
- breadth_20d_pct
- box_position
- market_score

All features are standardized on the eligible control pool exactly as in Stage2 Final V1.

## Prespecified perturbations

1. Controls per event K = **3, 5, 10**
2. Event exclusion window = **10, 20, 30 market sessions**
3. Exact MA200 phase match when enough controls exist; otherwise relax, same as Stage2 Final V1.
4. Repeat the full grid **without market_score** in the matching feature set.

No cell may be selected as a new rule.

## Prespecified summaries

For 5D / 10D / 20D matched lift:

- mean lift
- median lift
- positive-lift percentage
- min/max across the 9 K × exclusion cells
- share of cells with positive mean lift
- center cell K=5, exclusion=20
- leave-one-event range for the center cell
- 20-session cluster-weighted lift for the center cell
- equal-year weighted lift for the center cell
- control-date reuse

## Interpretation gates

This is a robustness classification, not a promotion test.

- **ROBUST_POSITIVE**: all 9 base-feature grid cells have positive mean 10D lift AND all 9 have positive mean 20D lift; center-cell leave-one-event minimum remains positive at the relevant horizon.
- **BROADLY_POSITIVE_BUT_FRAGILE**: >= 7/9 grid cells positive at 10D and 20D, but at least one leave-one-event minimum crosses zero.
- **METHOD_SENSITIVE**: fewer than 7/9 grid cells are positive at 10D or 20D, or removing market_score changes the sign of the median grid result.
- **NO_EDGE**: median grid mean lift <= 0 at 10D and 20D.

These labels do not change production or Forward-OOS rules.

## Guardrail

Historical robustness cannot replace Forward OOS. No threshold or matching cell is optimized after seeing results.
