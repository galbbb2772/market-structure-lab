# Pure Box Entry Confirmation V1

Status: research-only. No production promotion.

## Question
Does waiting for evidence that the lower box boundary actually held improve the Pure Box strategy enough to justify entering one session later at a potentially worse price?

## Frozen context
- Same causal Top300 / Top500 liquid-leader proxy.
- Same small / large box geometry.
- Same bottom-zone signal source.
- Long only.
- Stop remains box lower.
- Target remains box upper.
- 5 bps per side.
- Small requested weight 50%; large 100%.
- Fresh / Wide+Fresh thresholds are the already-frozen annual walk-forward thresholds from Vitality V2.
- Cross-year bars are used so January history and delayed entries are not truncated.

## Entry variants
All confirmation rules are evaluated using the full next session after the original signal.
Confirmed variants enter at the following session open, so confirmation never uses same-day future information.

1. baseline_next_open
   - Original rule: enter next session open.

2. hold_then_enter
   - Confirmation day low stays above the box lower edge;
   - confirmation close > original signal close.
   - Enter following session open.

3. no_new_low_green
   - Confirmation day low >= original signal-day low;
   - confirmation close > confirmation open.
   - Enter following session open.

4. lower_touch_reclaim
   - Confirmation day low <= lower + 12% of box width;
   - confirmation close >= lower + 20% of box width.
   - Enter following session open.
   - 12% reuses the fixed lower-touch definition from Structure Decay;
     20% reuses the existing Pure Box bottom-zone boundary.

5. failed_break_reclaim
   - Confirmation day low <= box lower;
   - confirmation close > box lower;
   - confirmation close > confirmation open.
   - Enter following session open.

For every confirmed variant:
- reject if delayed entry open <= lower or >= upper;
- no alternative threshold grid is searched in V1.

## Evaluation
Annual walk-forward years 2021..2026Q1.
Top500 primary, Top300 robustness.
Sleeves:
- all
- Fresh
- Wide+Fresh

Report:
- annual total return / MDD / Sharpe / exposure;
- trade count / PF / mean trade;
- confirmation rate;
- average delayed-entry price relative to original next-open baseline when both exist;
- compounded annual walk-forward return.

## Discovery / interpretation
This is a pre-registered mechanism test.
Do not choose a confirmation rule only because one year is exceptional.
Prefer a rule if:
- PF and Sharpe improve in both Top300 and Top500;
- drawdown does not worsen materially;
- improvement is present in several years;
- gains survive the one-session delayed entry price.
