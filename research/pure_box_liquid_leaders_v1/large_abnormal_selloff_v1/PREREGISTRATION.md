# Large Abnormal Selloff / Mispricing V1 — Preregistration

Status: mechanism research only. No production or forward-shadow changes.

## Motivation
Prior reconstruction results imply:
- box structure alone is insufficient;
- stock-level selling exhaustion contains information;
- static/dynamic broad-market permission did not survive robust validation.

This study asks whether the missing layer is the severity of the stock-specific dislocation itself:
was the selloff unusually large relative to the stock's own normal volatility and/or relative to SPY?

## Frozen trade setup
Unchanged:
- Top500 primary / Top300 robustness
- Large only
- Fresh age <=24 Top500 / <=23 Top300
- signal close in lower 20% of box
- no_new_low_green confirmation
- enter following-session open
- lower-edge stop
- primary target = 60% box
- robustness target = 80% box
- max hold = 20 sessions
- 5 bps each side
- normalized 10% initial allocation for portfolio diagnostics

All mispricing features are computed using information available by SIGNAL-DATE close.
No confirmation-day rebound information is used in V1.

## Predeclared severity features

### 1. selloff_1d_atr
- one-session stock return ending on signal date
- normalized by ATR14% known at the prior close
- oriented so higher = larger negative move relative to normal range

selloff_1d_atr = -stock_ret_1d / prior_ATR14_pct

### 2. selloff_3d_sigma
- 3-session stock log return ending on signal date
- normalized by sqrt(3) * prior 20-session realized volatility
- volatility estimate is frozen BEFORE the 3-session selloff window

Higher = more extreme negative 3-session move relative to prior normal volatility.

### 3. selloff_5d_sigma
Same construction over 5 sessions, with the volatility estimate frozen before the 5-session window.

### 4. spy_relative_3d_sigma
- stock 3-session log return minus SPY 3-session log return
- normalized by the same pre-window stock volatility scale
- oriented so higher = stock underperformed SPY more severely

### 5. spy_relative_5d_sigma
Same construction over 5 sessions.

### 6. own_history_5d_extreme
- current 5-session stock return percentile versus prior 5-session returns
- comparison set uses only 5-session returns ending BEFORE the current 5-session selloff window
- maximum lookback = 252 prior sessions
- minimum usable historical observations = 126
- own_history_5d_extreme = 1 - historical percentile

Higher = current 5-session selloff is deeper in the stock's own left-tail history.

## Guardrails
- No feature weights or composite score in V1.
- No threshold grid.
- No "best of 1d/3d/5d" selection.
- Discovery cutpoints only: 2019-2022 defines quintiles separately for Top300 and Top500.
- Fixed discovery cutpoints are applied unchanged to 2023-2026Q1 validation.

## Primary hypothesis
For each severity feature, higher severity should generally correspond to stronger subsequent mean-reversion economics AFTER the already-frozen no_new_low_green confirmation.

This is intentionally a monotonic hypothesis.
If only one isolated quintile is attractive or direction flips between periods, the feature is rejected.

## Metrics
For both 60% and 80% exits:
- Spearman(feature, net trade return)
- Spearman(feature, target-before-stop)
- Spearman(feature, stop indicator)
- Q1..Q5 N
- mean / median net trade
- profit factor
- win rate
- target / stop / max-hold shares
- mean holding sessions
- MFE / MAE
- yearly mean trade and PF

Portfolio diagnostics:
- baseline all observations
- Q1 only
- Q5 only
with the same 10% normalized sizing.

Report:
- annual return
- compounded segment return
- MDD
- Sharpe
- exposure
- trade count

## Support standard
A severity feature is supported only if:
- continuous return correlation has the hypothesized positive direction in discovery and validation;
- Q5 economically exceeds Q1 in discovery and validation;
- Top300 and Top500 broadly agree;
- 60% and 80% exits broadly agree;
- portfolio direction agrees with event-level economics;
- result is not obviously one-year dominated.

No feature or quintile cutoff may be promoted from V1 alone.

## Next step if supported
Only supported severity variables may be interacted with the already-observed stock-level exhaustion variables
(rebound_from_low_box and low_progress_box) in a separately preregistered Mispricing x Exhaustion study.
