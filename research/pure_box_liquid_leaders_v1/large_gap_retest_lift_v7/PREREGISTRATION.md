# Large Gap Retest-vs-Lift Decomposition V7 — Preregistration

Status: mechanism refinement only. No production / forward-shadow change.

## Motivation
V5 found that within extreme overnight-gap observations, stronger rebound_from_low_box and stronger low_progress_box were worse.
V6 showed:
- stronger confirmation does enter materially higher in the box and has worse raw R/R;
- entry geometry does not fully explain the negative effect;
- the negative effect is most stable for low_progress_box in Top500.

Because the confirmation rule already requires confirmation_low >= signal_low:
rebound_from_low_box can be decomposed exactly into:

rebound_from_low_box
= low_progress_box
+ close_lift_box

where:
close_lift_box = (confirmation_close - confirmation_low) / box_width.

This separates two economically different ideas:
1. low_progress_box:
   how far the confirmation-day LOW stays above the signal low.
   Lower means a closer RETEST of the original low.

2. close_lift_box:
   how strongly price closes above the confirmation-day low.
   Higher means stronger intraday rejection / lift after the retest attempt.

## Frozen sample
Same Fresh Large confirmed sample and extreme-gap definitions as V6:
- Top500 primary / Top300 robustness
- 60% primary / 80% robustness
- expanding prior-history 20th-percentile gap tail
- fixed -1% gap tail robustness
- test years 2021-2026
- same stop / max hold / costs

## Primary continuous model
Within EXTREME_GAP, separately for cap / target / gap method:

net_return ~ intercept
           + z(low_progress_box)
           + z(close_lift_box)
           + z(entry_fraction)
           + z(gap_component)
           + year fixed effects

Report coefficients in return units per one within-sample SD.

Primary mechanism expectation after V6:
- low_progress_box coefficient < 0:
  closer retest of the signal low is better.
- close_lift_box is diagnostic:
  if positive after controlling low_progress and entry geometry,
  then "retest + lift" is distinct from simply bouncing far away from the low.

No p-value threshold is used; signs and stability are the diagnostic.

## Expanding 2x2 state map
For each test year Y / cap / gap method:
- use only historical EXTREME_GAP candidates from years < Y;
- freeze medians of low_progress_box and close_lift_box;
- apply to year Y.

States:
1. RETEST_LIFT
   low_progress <= prior median AND close_lift > prior median
2. RETEST_WEAK_LIFT
   low_progress <= prior median AND close_lift <= prior median
3. NO_RETEST_LIFT
   low_progress > prior median AND close_lift > prior median
4. NO_RETEST_WEAK_LIFT
   low_progress > prior median AND close_lift <= prior median

Primary ordering question:
RETEST_LIFT > NO_RETEST_LIFT.

Secondary question:
Within RETEST observations, does LIFT improve over WEAK_LIFT?

## Metrics
For each state:
- N / mean trade / PF
- target / stop shares
- MFE / MAE
- yearly mean trade
- compounded normalized portfolio return is descriptive only if replayed later.

Support for the retest mechanism requires:
- continuous low_progress coefficient < 0 across both target choices and both gap definitions in Top500;
- RETEST_LIFT > NO_RETEST_LIFT in aggregate and in at least 4/6 test years for Top500;
- Top300 is robustness, not required to be identical.

No trading rule is promoted from V7 alone.
