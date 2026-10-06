# Pure Box Transition V1 — Entry Confirmation × Breadth Change

Status: research-only. No production promotion.

## Question
When an individual stock confirms a lower-box reversal, does simultaneous improvement in market breadth identify a higher-quality state transition than static breadth level?

This follows Entry Confirmation V1 and Entry Confirmation × Breadth V2:
- light entry confirmation improved several sleeves;
- requiring high static breadth on the original signal date often destroyed the confirmation edge.

## Frozen strategy context
- Same causal Top300 / Top500 liquid-leader proxy.
- Same Pure Box geometry.
- Long only.
- Stop at box lower.
- Target at box upper.
- 5 bps per side.
- Small requested weight 50%; large 100%.
- Fresh / Wide+Fresh thresholds are the frozen annual walk-forward thresholds from Vitality V2.
- Cross-year bars used for delayed entries.
- Full-history causal breadth series from Breadth Permission V1.

## Frozen entry confirmations
1. hold_then_enter:
   confirmation-day low > box lower AND confirmation close > signal-day close.
2. no_new_low_green:
   confirmation-day low >= signal-day low AND confirmation close > confirmation open.

Entry occurs at the following session open.

## Breadth transition variables
Measured from original signal-date close to confirmation-date close:
- delta_ma50 = pct_above_ma50(confirm) - pct_above_ma50(signal)
- delta_ret20 = pct_ret20_positive(confirm) - pct_ret20_positive(signal)
- delta_newlow = pct_new_20d_low(confirm) - pct_new_20d_low(signal)

No magnitude threshold is searched.

## Pre-registered transition lanes
For each entry-confirmation rule:
1. confirm_only
2. ma50_improving: delta_ma50 > 0
3. ret20_improving: delta_ret20 > 0
4. breadth_either_improving: delta_ma50 > 0 OR delta_ret20 > 0
5. breadth_both_improving: delta_ma50 > 0 AND delta_ret20 > 0
6. no_newlow_worsening: delta_newlow <= 0
7. transition_core:
   (delta_ma50 > 0 OR delta_ret20 > 0) AND delta_newlow <= 0

## Evaluation
Annual walk-forward 2021..2026Q1.
Top500 primary; Top300 robustness.
Sleeves:
- Fresh
- Wide+Fresh

Report:
- annual total return / MDD / Sharpe / exposure
- trade count / PF / mean trade
- transition acceptance rate
- compounded annual walk-forward return

## Decision standard
Transition is materially supported only if:
- at least one sign-based transition lane improves confirmation-only in both Top300 and Top500;
- 2022 improves materially;
- 2026Q1 does not materially worsen;
- gains are not solely due to near-zero exposure;
- direction appears in both Fresh and/or a clearly interpretable subset, rather than one isolated year.

No new numeric threshold may be selected in V1.
