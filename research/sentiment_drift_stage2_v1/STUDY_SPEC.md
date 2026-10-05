# Sentiment Drift / Data-Quality Stage-2 V1

Status: research-only / diagnostic-only. No production effect.

Motivation: the prior cross-module study found 22 Sentiment Extreme onsets (expanding sentiment_stress percentile >=80), but all occurred in 2018-2021 and none in 2022-2026. Before treating Sentiment as a strong independent family, audit whether this is a genuine market-state fact or a historical reconstruction / percentile-drift issue.

## Frozen primary series
- Raw sentiment_stress = existing mean(pessimism, total_negative, 100-euphoria) from market_state_box_v1.
- Existing production-independent historical diagnostic percentile = sentiment_stress_pct, expanding point-in-time percentile.
- Existing Sentiment Extreme = sentiment_stress_pct >=80 false->true onset, 5-session de-cluster.

## Required diagnostics
### Calendar-year profile
For each year:
- finite observation count;
- missingness of optimism, pessimism, total_negative, euphoria, raw stress, expanding percentile;
- raw stress mean / median / p10 / p90 / max;
- expanding percentile mean / median / max;
- day counts and false->true onset counts at fixed 70 / 80 / 90 percentiles;
- SPX forward 10D summary for >=80 onsets.

### Fixed eras
- 2017-2019
- 2020-2021
- 2022-2026
Report the same threshold-onset counts and forward outcomes for each era, without changing thresholds.

### Rolling-percentile sensitivity diagnostics
Using the same raw sentiment_stress only, calculate trailing inclusive percentiles with fixed windows:
- 252 trading sessions;
- 756 trading sessions.
Require at least 60 finite observations.
These rolling percentiles are diagnostic comparators only and are NOT candidate rules. Report yearly max percentile, >=80 day/onset counts, correlation with the existing expanding percentile, and overlap of >=80 onsets within +/-5 sessions.

### Distribution shift
For each year and era report raw-stress quantiles and standardized mean shift versus 2018-2021 reference using the reference mean/std. Also report percentile occupancy by decile for the existing expanding percentile.

### Component behavior
Per year report means/stds and pairwise finite correlations for pessimism, total_negative and inverted euphoria (100-euphoria). Flag years with near-zero component variance or material missingness.

## Interpretation guardrails
- Rolling percentile results are not eligible for threshold replacement or model promotion.
- Historical sentiment/model history is reconstructed and not a fully publication-time archive.
- A lack of expanding-percentile extremes after 2021 may reflect changing distribution, source construction, or a genuine regime shift; do not assume which without evidence.
- No production or Forward-OOS definition may change from this study.