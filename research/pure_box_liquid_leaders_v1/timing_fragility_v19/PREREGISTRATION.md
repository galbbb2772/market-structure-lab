# Pure Box Timing Fragility Anatomy V19

Status: diagnostic only. No rule changes.

## Question
Why does delaying the frozen simple-core entry by one trading session materially worsen drawdown even though total return often remains high?

## Frozen cohort
Strict Wide + Fresh, Bottom<=20%, Top500 primary / Top300 robustness, same frozen geometry as V18.

## Diagnostics
For every direct-entry candidate that also has a valid +1 session delayed entry:
- direct entry fraction in box
- delayed entry fraction in box
- migration delta
- direct and delayed stop distance
- direct and delayed reward/risk to 60% box target
- direct->delay overnight/open gap
- scale (Small/Large)
- year

## Outcome attribution
Using identical 60% target / lower stop / H20:
- compute per-trade return for direct entry
- compute per-trade return for delayed entry
- compute return delta
- identify delayed losers that were direct winners
- identify candidates excluded at delay because price moved outside the valid entry/target region

## Bins
Report by delayed entry-fraction bands:
<=10%, 10-20%, 20-30%, >30%
and by reward/risk deterioration quartiles.

## Drawdown clustering proxy
For delayed-entry trades:
- aggregate losing trade PnL by month and year
- report worst 5 months by mean/sum normalized trade return
- compare concentration versus direct entry.

No optimization. No new guard may be proposed as a candidate until mechanism is diagnosed.
