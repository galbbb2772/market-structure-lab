# Pure Box Position Sizing V1 — Quality-Aware Capital Allocation

Status: research-only. No production promotion.

## Question
Does the strategy leave meaningful alpha on the table because simultaneous confirmed opportunities receive capital without regard to relative setup quality?

This study changes ONLY the initial allocation among same-day eligible entries.
It does not pyramid, add, reduce, rebalance, or alter an open position after entry.

## Frozen strategy
- Same Top300 / Top500 causal liquid-leader proxy.
- Same box geometry.
- Same long-only stop at lower edge / target at upper edge.
- Same 5 bps per side.
- Same annual walk-forward Fresh / Wide+Fresh thresholds from Vitality V2.
- Same cross-year handling.
- Entry confirmations are frozen from Entry Confirmation V1:
  - hold_then_enter
  - no_new_low_green
- No Breadth gate and no 3+ hard filter in V1.

## Capital-budget invariant
On every entry day, compute the exact same requested dollar budget as the original engine:
- small candidate max request = 50% of opening equity;
- large candidate max request = 100% of opening equity;
- total new-entry budget = min(available cash, sum of those requests).

Every sizing lane receives the SAME total entry-day budget.
Only the allocation of that budget across simultaneous candidates changes.
No leverage is added.

## Pre-registered allocation lanes
1. baseline_pro_rata
   Existing behavior: scale all candidate requests by the same factor when cash constrained.

2. width_age_borda
   Rank same-day candidates:
   - wider box is better;
   - younger box is better.
   Borda quality = width rank points + freshness rank points.
   Allocate the fixed budget in proportion to Borda quality, respecting each candidate's original 50% / 100% max request.

3. confirmation_borda
   Rank by confirmation strength only:
   - hold_then_enter: (confirmation close - signal close) / box width;
   - no_new_low_green: (confirmation close - confirmation open) / box width.
   Higher is better.
   Allocate the fixed budget by rank points with original per-candidate max requests.

4. composite_borda
   Equal-rank-points combination of:
   - box width;
   - box freshness (lower age);
   - confirmation strength.
   Allocate the same fixed budget with the same per-candidate max requests.

No continuous coefficient, multiplier, or cutoff is fitted.

## Allocation algorithm
Weighted water-filling:
- start with score-proportional allocation;
- cap any candidate at its frozen max request;
- redistribute excess among uncapped candidates in score proportion;
- repeat until budget is allocated or all candidate caps are filled.

## Evaluation
Annual walk-forward 2021..2026Q1.
Top500 primary, Top300 robustness.
Sleeves:
- Fresh
- Wide+Fresh
Entry rules:
- hold_then_enter
- no_new_low_green

Report:
- annual return / MDD / Sharpe / exposure;
- trades / PF / mean trade;
- average entry-day concentration HHI;
- average largest new-position allocation share;
- number/fraction of cash-constrained entry days;
- compounded annual walk-forward return.

## Decision standard
Quality-aware sizing is useful only if:
- it improves return and/or Sharpe in both Top300 and Top500 for at least one frozen entry rule;
- improvement is not solely explained by extreme concentration;
- 2022 and 2026Q1 do not materially deteriorate;
- the result is directionally coherent across Fresh / Wide+Fresh.

This is a capital-allocation study, not a new alpha-filter study.
