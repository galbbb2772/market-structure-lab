# Large-Box Market Permission V1 — Preregistration

Status: mechanism research only. No production or forward-shadow change.

## Question
Why did Large Fresh confirmed mean reversion perform poorly in parts of 2019-2022, especially 2022, but strongly in 2023-2025?

This study does not invent a 2022-specific filter.
It applies only market-regime definitions that already existed elsewhere in the repository before this study.

## Frozen trade setup
Universe:
- Top500 primary
- Top300 robustness

Scale:
- Large only

Fresh:
- Top500 Large age <= 24
- Top300 Large age <= 23
(thresholds frozen from Wide+Fresh OOS V1)

Entry:
- signal close in bottom 20% of box
- original next-session open inside box
- no_new_low_green confirmation:
  next-session low >= signal-day low
  AND next-session close > next-session open
- enter following-session open, inside box

Exit economics:
- PRIMARY: 60% box target, lower-edge stop, max hold 20 sessions
- ROBUSTNESS: 80% box target, lower-edge stop, max hold 20 sessions
- 5 bps each side
- same-day stop + target ambiguity = stop first

Sizing:
- diagnostic trade/event analysis uses equal observations
- portfolio regime panels use the same 10% initial allocation normalization from Scale-Aware Exit Economics V1
- no leverage

## Pre-existing causal market states
All labels are computed on the CONFIRMATION-DATE close and therefore known before the following-session entry.

### A. SPY trend
Definition reused from Up/Down Divergence Regime V1:
- ABOVE_MA200
- BELOW_MA200

### B. SPY realized-volatility percentile
Definition reused from Up/Down Divergence Regime V1:
- 20d realized volatility
- percentile versus trailing 252 sessions
- LOW <= 30th percentile
- MID = 30th to 70th
- HIGH >= 70th percentile

### C. SPY 60-session drawdown
Definition reused from Up/Down Divergence Regime V1:
- SHALLOW: > -5%
- MEDIUM: -5% to -10%
- DEEP: <= -10%

### D. Frozen V4 absolute trend/vol states
Definition reused from Regime Research Shadow V1:
- CALM_UPTREND: rv20 < 10% and ret20 > 0
- CALM_WEAK: rv20 < 10% and ret20 <= 0
- STRESS_REVERSAL: rv20 >= 10% and ret20 <= 0
- VOLATILE_UPTREND: rv20 >= 10% and ret20 > 0

No threshold may be changed in this study.

## Predeclared interactions
Only these are allowed:
1. trend x volatility percentile
2. trend x drawdown depth

No triple state and no threshold grid.

## Evaluation
Discovery: 2019-2022
Validation: 2023-2026Q1

For every state report:
- observations
- target / stop / max-hold shares
- mean and median net trade
- profit factor
- mean holding sessions
- mean MFE / MAE
- yearly trade counts and mean returns

Portfolio replay by state:
- baseline Large lane
- INCLUDE-state-only diagnostic
- EXCLUDE-state diagnostic

Report total return, MDD, Sharpe, exposure and capital efficiency.
These are diagnostics only; they do not promote a gate.

## Mechanism support
A state is interesting if:
- poor trade economics appear in discovery AND validation in the same direction;
- Top300 and Top500 broadly agree;
- the effect exists for both 60% primary and 80% robustness exits;
- it is not just one calendar year.

A state that merely explains 2022 retrospectively but does not replicate is rejected.

## Governance
- No market-permission gate is selected from this V1.
- No state is added to the forward shadow from this V1.
- Any candidate gate requires a separately preregistered walk-forward / forward-OOS test.
