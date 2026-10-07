# Pure Box Core Geometry / Simplicity Audit V13

Status: research-only mechanism audit. No production change.

## Motivation
Earlier Strict Wide + Fresh OOS showed unusually strong 2023-2026Q1 performance.
Later research progressively added confirmation, gap/retest restrictions, time stops and different sizing.
This audit asks whether the simple box-bottom geometry itself was the high-value core and whether later confirmation/portfolio rules suppressed it.

## Frozen historical thresholds
Use the already-discovered 2019-2022 thresholds from Wide Fresh OOS V1. Do not re-fit:
Top300:
- small width_q80 = 0.13149887551263392, age_q20 = 3
- large width_q80 = 0.2831081474441409, age_q20 = 7
Top500:
- small width_q80 = 0.13255303761158518, age_q20 = 3
- large width_q80 = 0.2832764505119453, age_q20 = 7

Strict geometry:
- box width >= scale-specific discovery q80
- box age <= scale-specific discovery q20
- existing Pure Box signal already places signal close in the lower box region per source generator.

## Validation window
2023-01-01 through 2026-03-31.
This is a reconstruction/mechanism audit, NOT new OOS evidence.

## Fixed comparison lanes
1. OLD_EXACT
   - next-session-open direct entry
   - full box upper target
   - no time stop
   - original request weight: Small 50%, Large 100%, cash-scaled
2. DIRECT_20_FULL_NOTIME
   - same direct entry / full upper / no time stop
   - fixed 20% request per event
3. DIRECT_20_FULL_H20
   - direct entry / full upper / 20-session max hold
   - 20% request
4. CONFIRM_20_FULL_H20
   - no_new_low_green confirmation then following-session open
   - full upper / 20-session max hold
   - 20% request
5. DIRECT_20_T60_H20
   - direct entry / 60% box target / H20 / 20%
6. CONFIRM_20_T60_H20
   - confirmation entry / 60% box target / H20 / 20%

Run Top500 primary and Top300 robustness.

## Primary diagnostic
If DIRECT materially outperforms CONFIRM under otherwise identical portfolio rules, confirmation is likely suppressing box-bottom geometry rather than improving it.
If H20 materially harms the old exact lane, long dwell / patient mean reversion is part of the core.
If fixed 20% sizing retains strong risk-adjusted performance, the old result is not merely an artifact of the original aggressive request weights.

No threshold search and no production promotion.