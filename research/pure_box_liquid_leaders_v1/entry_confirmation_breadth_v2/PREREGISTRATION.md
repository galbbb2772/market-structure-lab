# Entry Confirmation × Breadth V2

Status: research-only. No production promotion.

## Question
Are entry confirmation and market breadth complementary?

Entry Confirmation V1 found two promising, already-frozen confirmation rules:
- hold_then_enter
- no_new_low_green

Breadth Permission V1 found a promising, already-frozen market gate:
- breadth_dual = pct_above_ma50 >= 50% AND pct_ret20_positive >= 50%

This V2 does not search new thresholds.

## Frozen strategy mechanics
- Top300 and Top500 causal liquid-leader proxy.
- Existing Pure Box geometry.
- Long only.
- Stop at box lower.
- Target at box upper.
- 5 bps per side.
- Small requested weight 50%, large 100%.
- Fresh / Wide+Fresh thresholds are annual walk-forward thresholds already frozen in Vitality V2.
- Cross-year bars used for January history and delayed entry.
- Breadth series is the persisted full-history causal series from Breadth Permission V1.

## Entry lanes
1. baseline_next_open
2. hold_then_enter
3. no_new_low_green

## Market lanes
1. no_breadth_gate
2. breadth_dual

Breadth is evaluated on the ORIGINAL signal-date close.
Confirmed variants still enter after one full confirmation session, at the following open.

This prevents the market gate from accidentally using information from the confirmation day.

## Evaluation
Annual walk-forward 2021..2026Q1, Top300 / Top500, sleeves:
- Fresh
- Wide+Fresh

Report:
- yearly return
- MDD
- Sharpe
- exposure
- trades
- PF
- mean trade
- confirmation rate
- compounded annual walk-forward return

## Interaction diagnostic
For each universe/sleeve compare:
- confirmation uplift over baseline without Breadth;
- Breadth uplift over baseline;
- combined uplift over baseline;
- whether combined improvement exceeds what either layer achieves alone.

Do not infer statistical independence from return arithmetic alone; the purpose is practical complementarity.

## Decision standard
Strong support requires:
- combined lane improves risk-adjusted performance in Top300 and Top500;
- 2022 improves materially;
- 2026Q1 does not materially worsen;
- improvement is not explained solely by collapsing exposure.
