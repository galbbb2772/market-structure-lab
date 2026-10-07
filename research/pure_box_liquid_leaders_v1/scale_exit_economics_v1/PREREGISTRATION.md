# Scale-Aware Exit Economics V1 — preregistration

Status: mechanism / execution-economics research only.
No production, forward shadow, or failed Candidate V1 rule is changed.

## Decision question
The existing Pure Box proxy used the same lower-stop / upper-edge target for both Small and Large boxes.
Strategy Reconstruction V1 showed materially different mean-reversion paths by scale.

V1 asks:
For an already-confirmed Fresh setup, what exit depth best describes the economic shape of Small vs Large mean reversion?

This study does NOT choose a new production exit. It compares pre-declared target layers.

## Frozen sample / entry
Source:
- Pure Box Liquid Leaders yearly artifacts from run 37424716935.
- 2019-01-01 through 2026-03-31.
- Top500 primary; Top300 robustness.

Development / validation:
- discovery = 2019-2022
- validation = 2023-2026Q1

Fresh thresholds are frozen from Wide+Fresh OOS V1:
- Top300: Small age <= 12, Large age <= 23
- Top500: Small age <= 12, Large age <= 24

Entry is frozen:
- signal close in lower 20% of active box;
- signal known after close;
- original next-session open strictly inside box;
- no_new_low_green confirmation:
  confirmation low >= signal-day low AND confirmation close > confirmation open;
- enter at following-session open, strictly inside box.

No Breadth gate.
No 3+ touch hard filter.
No sizing quality score.
No post-entry scaling.

## Exit layers
Each scale is evaluated independently at:
- 50% box position
- 60% box position
- 80% box position
- 100% / box upper edge

Stop is always the frozen box lower edge.

If the entry open is already at or above a target, that observation is ineligible for that target lane.

Comparability panels:
- PRIMARY = common_eligible: entry is below the 50% box position, so the exact same entry set is eligible for all four target layers.
- SECONDARY = target_specific: each target uses all observations that are below that target at entry.

The common_eligible panel controls for sample-selection differences between exit layers.

Daily-bar ambiguity:
- opening gap stop/target uses actual open;
- same-day intraday stop + target ambiguity = stop first.

Costs:
- 5 bps entry
- 5 bps exit

## Holding policy panels
Primary economic panel:
- max holding period = 20 sessions.
- if neither stop nor target occurs, exit at session-20 close with exit cost.

Secondary robustness panels:
- max holding period = 10 sessions
- max holding period = 40 sessions

A max-hold exit is used only to make capital occupation and exit economics comparable across target layers.
No horizon may be selected from this V1 as a production parameter without a separate preregistered test.

## Portfolio construction
Small and Large are simulated separately.

Within a scale:
- equal-weight same-day entries subject to cash;
- per-position requested allocation = 10% of opening equity;
- hard max initial single-name allocation = 10%;
- no leverage;
- unused cash remains cash.

Why 10%:
This is an analysis-normalization choice, not an optimized strategy parameter.
It prevents the prior 50%/100% scale sizing convention from mechanically dominating the exit comparison.

The exact same sizing is used for all target layers.

## Metrics
Trade economics:
- completed trades
- win rate
- mean / median net trade
- profit factor
- median holding sessions
- mean holding sessions
- target / stop / max-hold exit shares
- average MFE and MAE during holding period

Portfolio economics:
- annual return
- compounded annual walk-forward-style return across yearly segments
- max drawdown
- Sharpe
- average exposure
- average concurrent positions
- entry count
- turnover = sum initial allocations / mean equity
- capital-days = sum(entry allocation / entry equity * holding sessions)
- return per 100 capital-days
- return / average exposure

## Decision guardrails
A target layer is considered economically interesting only if, in validation:
- direction broadly agrees in Top300 and Top500;
- improvement is not solely from lower exposure;
- trade expectancy and portfolio behavior point in the same direction;
- result is not carried by one year.

Small and Large may have different economic optima.
No target is promoted from this study alone.
