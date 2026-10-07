# Large Selloff Path / Pre-Confirmation Exhaustion V2 — Preregistration

Status: mechanism research only. No production or forward-shadow changes.

## Why
Large Abnormal Selloff V1 rejected the hypothesis that larger absolute/normalized selloff severity is a stable source of mean-reversion edge.

The next question is not HOW FAR price fell, but HOW the selloff arrived at the structural low:
- is downside momentum still accelerating?
- is the signal day already rejecting its low?
- is the last part of the selloff becoming less negative?

This study stays entirely pre-entry and does not alter the frozen confirmation rule.

## Frozen Large setup
- Top500 primary / Top300 robustness
- Large only
- Fresh age <=24 Top500 / <=23 Top300
- signal close in lower 20% of box
- frozen no_new_low_green confirmation
- following-session open entry
- lower-edge stop
- primary target 60% / robustness 80%
- max hold 20 sessions
- 5 bps each side
- normalized 10% initial allocation for portfolio diagnostics

## Predeclared path/exhaustion features
All are known by SIGNAL-DATE close.

1. signal_clv
   = (signal close - signal low) / signal range
   Higher = signal closes farther away from its low.
   Hypothesis: higher is better.

2. signal_lower_wick
   = (min(signal open, signal close) - signal low) / signal range
   Higher = stronger intraday rejection of the low.
   Hypothesis: higher is better.

3. signal_body_recovery
   = (signal close - signal open) / signal range
   Higher = stronger intraday recovery / less bearish body.
   Hypothesis: higher is better.

4. deceleration_1v3
   = signal-day log return - mean(log returns of the two preceding sessions)
   Higher = latest downside impulse is less negative / more positive than the immediately preceding selloff.
   Hypothesis: higher is better.

5. deceleration_2v5
   = mean(last 2 daily log returns) - mean(previous 3 daily log returns)
   Higher = recent two-session selling pressure is improving versus the earlier part of the five-session path.
   Hypothesis: higher is better.

6. down_day_count_5
   = number of negative close-to-close sessions in the last five sessions.
   Diagnostic only; no directional support claim is allowed in V2.

7. signal_volume_ratio20
   = signal-day volume / prior-20-session median volume.
   Diagnostic only; no directional support claim is allowed in V2.

No composite score and no threshold grid.

## Discovery / validation
- discovery: 2019-2022
- validation: 2023-2026Q1
- discovery quintiles frozen separately for Top300 / Top500 and applied unchanged to validation.

## Metrics
For 60% and 80% exits:
- Spearman(feature, net trade return)
- Spearman(feature, target indicator)
- Spearman(feature, stop indicator)
- Q1..Q5 N
- mean / median net trade
- PF
- win rate
- target / stop / max-hold shares
- MFE / MAE
- yearly mean trade and PF

Portfolio diagnostics:
- all observations
- Q1 only
- Q5 only
with identical normalized 10% sizing.

## Support standard for the five directional features
Supported only if:
- rho_return > 0 in discovery AND validation;
- Q5 mean trade and PF > Q1 in discovery AND validation;
- Q5 portfolio > Q1 portfolio in discovery AND validation;
- Top300 and Top500 broadly agree;
- both 60% and 80% exits broadly agree;
- not one-year dominated.

The two diagnostic-only features may be described but cannot be promoted.

No feature is added to the strategy from V2 alone.
