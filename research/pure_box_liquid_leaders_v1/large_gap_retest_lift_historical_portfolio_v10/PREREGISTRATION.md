# Large Gap Retest-Lift Historical Portfolio V10

Status: descriptive replay of the already-frozen V7 mechanism. No threshold search and no production change.

## Question
What is the full historical account-level total return of the frozen Large Gap Retest-Lift candidate?

The V7 study reported event means/PF and explicitly deferred compounded normalized portfolio return. This study fills that missing accounting readout.

## Frozen sample and state labels
- historical test window: 2021 through available 2026Q1 data;
- Top500 primary / Top300 robustness;
- Large Fresh only;
- Fresh age <=24 Top500 / <=23 Top300;
- V7 yearly expanding thresholds are loaded from the already-persisted V7 threshold table;
- fixed -1% gap is robustness only;
- RETEST_LIFT / NO_RETEST_LIFT labels are reproduced exactly from V7;
- no new threshold is searched.

## Portfolio contract
For each lane:
- initial equity = 1.0;
- 10% requested allocation per eligible event;
- no leverage; if simultaneous requests exceed available cash, scale them proportionally;
- one open position per symbol;
- entry = frozen following-session open;
- stop = box lower;
- target = 60% primary / 80% robustness of the box;
- max hold = 20 market sessions;
- 5 bps per side;
- same-day stop + target ambiguity = stop first;
- positions may carry across calendar-year boundaries;
- capital is NOT reset at year end.

## Primary readout
Top500 + EXPANDING + RETEST_LIFT:
- 60% target total return;
- 80% target total return.

Also report FIXED_-1PCT controls, yearly account returns, max drawdown, Sharpe, exposure, trade count, PF and win rate.

This readout must not be interpreted as prospective evidence. V7/V8/V9 and the later holdout/Forward-OOS evidence labels remain unchanged.
