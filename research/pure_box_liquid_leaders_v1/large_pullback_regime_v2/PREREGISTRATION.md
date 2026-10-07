# Large Box Pullback-vs-Downtrend V2 — Preregistration

Status: mechanism research only. No production or forward-shadow changes.

## Motivation
Large Market Permission V1 rejected simple static volatility/drawdown gating as a stable explanation:
aggregated medium-volatility buckets looked attractive, but yearly and portfolio behavior was inconsistent.

The next mechanism question is narrower:
Does Large-box mean reversion behave differently when a short-term selloff occurs inside a long-term uptrend versus inside a long-term downtrend?

## Frozen Large setup
Same as Large Market Permission V1:
- Top500 primary / Top300 robustness
- Large only
- Fresh age <=24 Top500 / <=23 Top300
- bottom-20% signal
- no_new_low_green confirmation
- next-session open entry
- lower-edge stop
- primary target = 60% box position
- robustness target = 80%
- max hold = 20 sessions
- 5 bps each side
- 10% normalized initial allocation for portfolio diagnostics

## Predeclared market-state classifier
All inputs are known at confirmation-date close.

Long-term trend:
- ABOVE_MA200
- BELOW_MA200

Short-term direction:
- POS_RET20: SPY 20-session return > 0
- NEG_RET20: SPY 20-session return <= 0

Four fixed states:
1. UPTREND_PULLBACK = ABOVE_MA200 + NEG_RET20
2. UPTREND_RISING = ABOVE_MA200 + POS_RET20
3. DOWNTREND_SELLING = BELOW_MA200 + NEG_RET20
4. DOWNTREND_BOUNCE = BELOW_MA200 + POS_RET20

No threshold is optimized.

## Primary hypothesis
- UPTREND_PULLBACK should be the most natural temporary-mispricing / mean-reversion environment.
- DOWNTREND_SELLING should be the weakest environment because lower-box touches are more likely to be continuation rather than temporary dislocation.

UPTREND_RISING and DOWNTREND_BOUNCE are descriptive controls.

## Evaluation
Discovery: 2019-2022
Validation: 2023-2026Q1

For each state and target:
- N
- mean / median trade
- PF
- win rate
- stop / target / max-hold shares
- MFE / MAE
- yearly trade economics

Portfolio include-state-only diagnostics:
- annual return
- compounded segment return
- MDD
- Sharpe
- exposure
- capital efficiency proxy

## Mechanism standard
Support requires:
- UPTREND_PULLBACK stronger than DOWNTREND_SELLING in both discovery and validation;
- same ordering in Top300 and Top500;
- same ordering for 60% and 80% exits;
- not explained solely by one year.

No hard gate is promoted from V2.
