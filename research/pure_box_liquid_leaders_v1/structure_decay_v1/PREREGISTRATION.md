# Structure Decay V1 — Box Boundary Consumption

Status: research-only diagnostic. No production rule is changed.

## Question
Does a box support edge decay as its lower boundary is repeatedly tested?

This study isolates box-internal decay before combining it with market breadth.

## Frozen source
- Source artifacts: Pure Box Liquid Leaders V1 run 37424716935.
- Long only.
- Causal Top300 / Top500 liquidity ranks from the source run.
- Existing small / large box geometry is unchanged.
- Entry reference: next-session open.
- Lower box edge is the stop boundary; upper edge is the target boundary.
- No RSI, MA, sentiment, regime, or other external alpha factor.

## Observation unit
Daily bottom-zone signals are NOT treated as independent observations.

For the same symbol + detected_at + scale + lower/upper geometry:
- lower-touch day = daily low <= lower + 12% of box width;
- consecutive lower-touch days form one touch episode;
- for each touch-episode number, keep only the first qualifying signal date.

This prevents a stock sitting near the lower edge for several consecutive days from being counted several times.

## Causal decay features
Known at signal-date close:
- touch_episodes: distinct lower-touch episodes since detected_at;
- touch_days: total lower-touch days since detected_at;
- touch_last10 / touch_last20;
- touch_accel10 = lower-touch days in latest 10 sessions minus preceding 10 sessions;
- bottom_streak = consecutive closes in the bottom 20% ending on signal date;
- days_since_prior_touch;
- age_sessions;
- signal_close_fraction.

## Outcomes
Using next-session open as the entry reference:
- forward 5-session return;
- forward 10-session return;
- 20-session MFE / MAE;
- whether lower stop or upper target is hit first within 20 sessions;
- same-day stop+target ambiguity is counted as stop first.

Signals without enough future sessions are retained for hit-path statistics when possible and excluded from unavailable forward-return fields.

## Discovery / validation
- Discovery: 2019-2022.
- Validation: 2023-2026Q1.
- Top500 primary, Top300 robustness.

Discovery-only medians by scale freeze two validation sleeves:
- Fresh: age <= discovery median age for that scale.
- Wide+Fresh: Fresh AND width >= discovery median width for that scale.

## Fixed descriptive bins
Touch episodes:
- 0
- 1
- 2
- 3+

Touch days in latest 10 sessions:
- 0
- 1
- 2
- 3+

Bottom-close streak:
- 1
- 2
- 3+

Touch acceleration:
- <=0
- +1
- +2 or more

No alternative cut grid is selected after viewing results in V1.

## Confound check
For discovery and validation separately, estimate a descriptive linear model:
forward_10d ~ touch_episodes + log1p(age) + box_width_pct + large_box_dummy

The touch-episode coefficient is used only to check whether the decay relation survives simple age/width control. It is not a production coefficient.

## Decision standard
Structure-decay hypothesis is materially supported only if:
- later touch episodes show worse validation expectancy / hit-path quality;
- direction is similar in Top300 and Top500;
- direction remains within the discovery-frozen Fresh sleeve;
- the touch-episode coefficient remains adverse after age/width control.

No production promotion is allowed from this V1 alone.
