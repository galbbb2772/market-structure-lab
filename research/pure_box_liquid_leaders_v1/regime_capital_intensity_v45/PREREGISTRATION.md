# Pure Box Simple Core Regime × Capital Intensity V45

Status: exploratory capital-layer research only. Signal core frozen.

## Objective
Test whether the same frozen Simple Core signal should carry the same capital intensity across different market regimes.

This is NOT a signal filter study.
No signal is removed.
Only capital intensity may differ by regime.

## Frozen signal/execution core
- Top500 primary, Top300 robustness
- Strict Wide + Fresh
- Bottom<=20%
- first eligible next-session open only
- lower stop
- target60
- H15
- liquidity-first same-day queue
- 50% single-name capital cap
- no leverage
- EARLY_R250 repeat-signal logic:
  - same box only
  - existing holding age <=3
  - no age reset
  - no stop/target reset

## Regime definition
Use only causal market data known before each entry open.

Primary market proxy: SPY.

For each entry date, classify using prior-close information:
1. TREND_UP
   - SPY prior close > prior MA200
   - SPY MA50 > MA200
2. TREND_DOWN
   - SPY prior close < prior MA200
   - SPY MA50 < MA200
3. TRANSITION
   - all other cases

Volatility overlay:
- compute prior 20-session realized volatility of SPY returns
- HIGH_VOL if above the expanding historical 70th percentile using only data available up to prior day
- LOW_MID_VOL otherwise

Combined regime labels:
- UP_LOW
- UP_HIGH
- DOWN_LOW
- DOWN_HIGH
- TRANSITION_LOW
- TRANSITION_HIGH

No thresholds may be changed after results.

## Policies

A. CONSTANT
- initial risk 1.25%
- early repeat-signal ceiling 2.50%
- same in all regimes

B. DEFENSIVE_DOWN
- TREND_DOWN: initial 0.75%, early ceiling 1.50%
- TRANSITION: initial 1.00%, early ceiling 2.00%
- TREND_UP: initial 1.25%, early ceiling 2.50%

C. VOLATILITY_AWARE
- HIGH_VOL: initial 0.90%, early ceiling 1.80%
- LOW_MID_VOL: initial 1.25%, early ceiling 2.50%

D. UP_AGGRESSIVE
- TREND_UP + LOW_MID_VOL: initial 1.50%, early ceiling 3.00%
- all other regimes: initial 1.00%, early ceiling 2.00%
- still subject to 50% single-name cap and no leverage

E. ASYMMETRIC
- UP_LOW: 1.50% / 3.00%
- UP_HIGH: 1.25% / 2.50%
- TRANSITION_LOW: 1.10% / 2.20%
- TRANSITION_HIGH: 0.90% / 1.80%
- DOWN_LOW: 0.90% / 1.80%
- DOWN_HIGH: 0.75% / 1.50%

(first number = initial stop-risk target, second = early repeat-signal total stop-risk ceiling)

## Required outputs
For each policy/universe:
- total return / CAGR / MDD / Sharpe
- rolling 12m min / median / positive share
- yearly returns
- average exposure
- blocked / partial new entries
- add-on count / capital
- regime-level trade count / mean trade / PF
- regime-level add-on count / mean add-on return / PF
- contribution to total PnL by regime
- time spent in each regime

## Decision rule
A regime-aware capital policy is supported only if it improves either:
- total return with similar or better MDD/rolling stability, or
- Sharpe / rolling stability with only modest return sacrifice.

No policy may be selected solely because one regime/year dominates historical returns.
No regime rule changes after results.
