# Large Selloff Deceleration V2 — Preregistration

Status: mechanism research only. No production or forward-shadow changes.

## Motivation
Large Abnormal Selloff / Mispricing V1 rejected the simple monotonic hypothesis that deeper or more abnormal selloffs should mean-revert better.

The next question is about PATH, not DISTANCE:
Does Large-box mean reversion improve when the selling process is visibly decelerating before / into the confirmation sequence?

This study does not reuse broad-market regime gates and does not change box, entry, exit, or sizing rules.

## Frozen Large setup
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

## Causal path features
All features are known no later than confirmation-date close.

### Signal-date path features
1. ret3_deceleration
   = recent 3-session log return - previous 3-session log return.
   Higher means the most recent 3-session decline is less severe / more recovered than the preceding 3-session path.

2. downside_body_decay
   = prior 3-session average negative candle-body fraction
     minus signal-day negative candle-body fraction.
   Candle-body fraction = max(open-close,0) / (high-low).
   Higher means bearish real-body pressure has contracted on the signal day.

3. signal_clv
   = (signal close - signal low) / (signal high - signal low).
   Higher means the signal closes farther from its low.

4. signal_lower_wick
   = (min(signal open, signal close) - signal low) / (signal high - signal low).
   Higher means stronger rejection wick below the candle body.

### Confirmation-transition path features
5. low_extension_deceleration
   = (signal low - prior-day low)/box_width
     - (confirmation low - signal low)/box_width.
   Higher means downside low-to-low extension slowed or reversed from signal to confirmation.

6. close_reclaim_acceleration
   = (confirmation close - signal close)/box_width
     - (signal close - prior-day close)/box_width.
   Higher means close-to-close direction accelerated upward into confirmation.

No composite score is allowed in V2.

## Discovery / validation
- discovery: 2019-2022
- validation: 2023-2026Q1

For each feature and rank cap:
- discovery defines quintile cutpoints;
- fixed cutpoints applied unchanged to validation.

## Hypothesized direction
Higher is better for all six features.

Support requires:
- positive continuous relationship in discovery and validation;
- Q5 > Q1 event economics in discovery and validation;
- Top300 / Top500 broadly agree;
- 60% / 80% exits broadly agree;
- portfolio Q5 > Q1 in the same direction;
- not carried by one calendar year.

## Metrics
Event:
- Spearman(feature, net trade return)
- Spearman(feature, target indicator)
- Spearman(feature, stop indicator)
- Q1..Q5 N
- mean / median net trade
- profit factor
- target / stop / max-hold shares
- MFE / MAE
- mean holding sessions
- yearly mean trade / PF

Portfolio diagnostics:
- baseline all
- Q1 only
- Q5 only
with normalized 10% initial allocation.

No threshold or feature is promoted from V2 alone.
