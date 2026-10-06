# Pure Box Position Sizing V2 — Concentration-Cap Robustness

Status: research-only robustness audit. No production promotion.

## Motivation
Position Sizing V1 found:
- Fresh sleeves often improved when same-day capital favored wider + younger boxes.
- Wide+Fresh / hold_then_enter sometimes improved when capital favored stronger confirmation.
- Cash was constrained on roughly 95%-99% of entry days.
- Average largest same-day new allocation was still large, often ~50%-70%.

V2 asks whether the sizing edge survives realistic per-symbol concentration caps.

## Frozen alpha / entry logic
No new signal or filter is introduced.

Primary sizing rules frozen from V1:
1. Fresh:
   - no_new_low_green + width_age_borda
   - hold_then_enter + width_age_borda
2. Wide+Fresh:
   - hold_then_enter + confirmation_borda

Baseline pro-rata versions of the same sleeves/entries are retained for comparison.

## Per-position equity caps
At entry, each new position is capped at:
- uncapped_v1: original small=50% / large=100% request cap
- 50%
- 33%
- 25%
- 20%
- 10%
of current opening equity.

The cap applies to the new position's total initial allocation.

## Capital-budget rule
For each entry day:
- compute the exact V1 requested new-entry budget;
- attempt to allocate that same budget using the frozen sizing score;
- enforce the per-symbol equity cap;
- if the cap set makes full deployment impossible, leave residual cash idle;
- do not redirect residual cash into existing positions;
- no leverage.

This deliberately separates:
- allocation quality;
- concentration;
- deployability.

## Metrics
Annual walk-forward 2021..2026Q1, Top300 / Top500:
- total return
- MDD
- Sharpe
- exposure
- trade count / PF / mean trade
- average entry HHI
- average largest new-position equity weight
- requested vs actually deployed new-entry budget
- fraction of entry days with residual unallocated budget
- compounded annual walk-forward return

## Decision standard
A sizing edge is materially robust only if:
- a capped version retains a meaningful fraction of the uncapped return uplift;
- Sharpe / MDD do not deteriorate materially;
- direction is similar in Top300 and Top500;
- result does not require >33% single-name initial weight.

This is a robustness audit, not a new optimization grid.
