# Pure Box Integrity V1

Research-only. No production effect.

## Question
Can box-boundary consumption plus breadth deterioration identify long-box setups whose apparent support is being exhausted?

## Frozen strategy
Same causal liquid-leader universe and Pure Box rules:
- long only
- next-session open
- stop at lower box edge
- target at upper box edge
- 5 bps per side
- small requested weight 50%, large 100%
- primary sleeves: fresh-only and wide+fresh
- annual walk-forward box width/age thresholds use prior years only

## Box-integrity features
All are computed only through signal-date close:
- post_detection_lower_touch_days: number of days after detected_at with low in lower 12% of box
- post_detection_lower_touch_episodes: number of distinct lower-touch episodes; consecutive touch days count as one episode
- touch_days_last10: lower-touch days during last 10 sessions
- touch_days_last20: lower-touch days during last 20 sessions
- days_since_prior_lower_touch: sessions since the prior touch before the current signal
- lower_zone_close_streak: consecutive closes in bottom 20% of box ending at signal date
- signal_close_fraction: (close-lower)/(upper-lower)

Interpretation: repeated or clustered tests may indicate boundary consumption.

## Breadth deterioration features
Using the causal daily Top300/Top500 breadth series:
- d5_ma50 = pct_above_ma50(t) - pct_above_ma50(t-5)
- d10_ma50
- d20_ma50
- d5_ret20breadth = pct_ret20_positive(t) - pct_ret20_positive(t-5)
- d10_ret20breadth
- d20_ret20breadth
- d5_newlow = pct_new_20d_low(t) - pct_new_20d_low(t-5)
- d10_newlow

## Pre-registered integrity gates
No test-year optimization.

1. all
2. low_consumption: post_detection_lower_touch_episodes <= 1
3. not_clustered: touch_days_last10 <= 2
4. short_bottom_streak: lower_zone_close_streak <= 2
5. integrity_core: episodes <=1 AND touch_days_last10 <=2 AND bottom_streak<=2

## Pre-registered deterioration gates
1. no_fast_breadth_break: d5_ma50 >= -0.10 AND d5_ret20breadth >= -0.10
2. no_medium_breadth_break: d10_ma50 >= -0.15 AND d10_ret20breadth >= -0.15
3. no_newlow_acceleration: d5_newlow <= +0.05
4. deterioration_core: no_fast_breadth_break AND no_newlow_acceleration

## Combined gates
- integrity_plus_fast_breadth
- integrity_plus_deterioration_core

## Evaluation
Annual walk-forward 2021..2026Q1 for Top300 and Top500, Fresh and Wide+Fresh sleeves.

Decision preference:
- materially improves 2026Q1 without simply eliminating most exposure;
- helps or at least does not worsen 2022;
- direction is similar in Top300 and Top500;
- improvement is present in PF / Sharpe / drawdown, not only raw return.
