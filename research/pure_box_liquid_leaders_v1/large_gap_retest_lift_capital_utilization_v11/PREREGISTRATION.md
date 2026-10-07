# Large Gap Retest-Lift Capital Utilization V11

Status: portfolio-layer research only. The V7 Retest-Lift signal/state definition is frozen and MUST NOT change.

## Question
The V10 historical account replay showed positive edge but very low average exposure (~6%-9%) under a fixed 10% request per event.
Can capital utilization be improved by changing only position sizing while preserving the exact same signal set?

## Frozen signal contract
Primary:
- Top500 prior-20 ADV liquid-leader proxy
- Large Fresh only
- EXPANDING extreme-gap definition
- RETEST_LIFT state exactly as V7
- 60% target primary / 80% robustness
- lower stop
- max hold 20 sessions
- 5 bps each side
- same-day stop-first
- no signal/filter/threshold changes

## Sizing grid
Requested allocation per event:
- 10%
- 20%
- 25%
- 33%
- 50%

Portfolio constraints:
- initial equity 1.0
- max gross exposure 100%
- one open position per symbol
- simultaneous entry requests scaled proportionally to available cash
- continuous equity across calendar years

## Metrics
For every sizing / target:
- total return
- CAGR
- max drawdown
- daily Sharpe
- average exposure
- completed trades
- PF / win rate / mean trade
- yearly returns

## Interpretation rule
This is a capital-efficiency study, not a new alpha discovery.
Prefer a sizing region only if the improvement is not merely higher leverage-like exposure:
- return must rise materially;
- max drawdown must remain controlled;
- Sharpe should not collapse;
- behavior should be broadly monotonic across adjacent sizing levels.

No production change follows automatically.
