# Pure Box Simple Core Early Path-State Add-On Audit V46

Status: diagnostic / mechanism research only. No candidate changes.

## Frozen subject
Simple Core Capital Candidate V2 / EARLY_R250:
- Top500 primary, Top300 robustness
- Strict Wide + Fresh
- Bottom<=20%
- first eligible next-session open
- initial risk 1.25%
- repeated same-box signal may add only at holding age <=3
- total same-symbol stop-risk ceiling 2.50%
- H15 / target60 / same lower stop
- 50% single-name cap
- liquidity-first capital queue
- no leverage

## Objective
Explain why early repeated same-box observations have positive historical add-on edge.

Do NOT change the signal.
Do NOT search thresholds.

## Causal state variables at add-on open
All variables use only information known by the add-on open.

1. POSITION_PNL_STATE
- POSITIVE: current open > original entry price
- NEGATIVE_OR_FLAT: current open <= original entry price

2. TARGET_PROGRESS_STATE
Progress = (current_open - original_entry) / (target - original_entry)
Fixed buckets:
- P0_NEG: progress < 0
- P1_0_25: 0 <= progress < 0.25
- P2_25_50: 0.25 <= progress < 0.50
- P3_50_PLUS: progress >= 0.50

3. PRIOR_DAY_CLOSE_STATE
- ABOVE_ENTRY
- AT_OR_BELOW_ENTRY

4. PRIOR_DAY_DIRECTION
- GREEN: prior close > prior open
- RED_OR_FLAT: prior close <= prior open

5. STOP_HEADROOM_STATE
Distance from add-on open to same lower stop:
- BELOW_MEDIAN
- ABOVE_MEDIAN
Median is descriptive only and computed across all eligible add-on observations; it must NOT be used to create a candidate rule in this study.

6. HOLDING_AGE
- age1
- age2
- age3

## Outputs
For every state/bucket:
- eligible repeat observations
- funded add-ons
- funded capital
- mean / median add-on slice return
- PF
- win rate
- sum add-on slice PnL
- 2025 vs ex-2025 split
- unique symbols

Also report two-way descriptive tables:
- holding age × PNL state
- holding age × target progress bucket
- prior-day direction × PNL state

## Interpretation discipline
This is anatomy only.
No threshold or path filter may be promoted from this audit.
Any promising state must be tested in a separately preregistered V47 robustness experiment with no retuning.
