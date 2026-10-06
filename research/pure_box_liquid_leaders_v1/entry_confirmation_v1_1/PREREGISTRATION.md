# Pure Box Entry Confirmation V1.1 — Mechanism Controls

Status: research-only mechanism audit. No production promotion.

## Why this follow-up exists
Entry Confirmation V1 showed that waiting for a simple "no new low + green day" confirmation improved several Fresh sleeves even though the eventual entry price was ~1%+ higher.

V1.1 asks whether the improvement comes from:
1. genuine information in the confirmation day; or
2. merely delaying entry by one session.

## Frozen source / mechanics
Same source, universes, box definitions, costs, sizing, exits, and annual walk-forward Fresh / Wide+Fresh thresholds as Entry Confirmation V1.

## Entry lanes
All lanes start from the same original bottom-zone signal.

1. baseline_next_open
   Enter next-session open.

2. blind_delay_one_day
   Ignore confirmation-day behavior.
   If the following session open is still strictly inside the box, enter then.
   This is the placebo for "waiting itself".

3. no_new_low_green
   Confirmation-day low >= signal-day low AND confirmation close > confirmation open.
   Enter following session open.

4. new_low_or_red
   Complementary adverse group:
   confirmation-day low < signal-day low OR confirmation close <= confirmation open.
   Enter following session open if still inside box.

5. hold_then_enter
   Confirmation-day low > box lower AND close > original signal close.
   Enter following session open.

6. fails_hold
   Complement of hold_then_enter on observations with a valid delayed entry.
   Enter following session open if still inside box.

## Primary mechanism contrasts
For each universe / sleeve:
- no_new_low_green minus blind_delay_one_day;
- new_low_or_red minus blind_delay_one_day;
- hold_then_enter minus blind_delay_one_day;
- fails_hold minus blind_delay_one_day.

If confirmation contains information, favorable groups should outperform blind delay and adverse complements should underperform it.

## Evaluation
Annual walk-forward years 2021..2026Q1.
Top500 primary, Top300 robustness.
Sleeves: All, Fresh, Wide+Fresh.

Report compounded return, yearly returns, Sharpe, MDD, exposure, PF, trade count, confirmation/group rate, and delayed-entry price slippage versus original next-open.

## Decision standard
Mechanism is supported if:
- blind delay alone does not explain most of the improvement;
- favorable confirmation beats blind delay in both Top300 and Top500, especially Fresh;
- adverse complements perform materially worse than favorable confirmation;
- direction repeats across several years.

No threshold search is allowed in V1.1.
