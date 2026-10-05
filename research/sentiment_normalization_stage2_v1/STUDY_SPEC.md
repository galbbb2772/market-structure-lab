# Sentiment Normalization Robustness Stage-2 V1

Status: research-only / diagnostic-only. No production effect.

Motivation: the sentiment drift audit found that the existing expanding percentile had 22 >=80 onsets, all in 2018-2021, while fixed 252D and 756D rolling percentiles of the same raw sentiment_stress produce post-2022 extremes. The source sentiment history itself already uses 756-session rolling percentile transforms inside component construction, so adding an expanding percentile in Market Structure Lab creates a second normalization layer.

## Frozen variants
All use the exact same raw sentiment_stress from market_state_box_v1 and threshold 80 with false->true onset and 5-session de-clustering:
- EXPANDING_EXISTING: existing sentiment_stress_pct.
- ROLLING_252_DIAGNOSTIC: trailing inclusive 252-session percentile, min 60 finite observations.
- ROLLING_756_DIAGNOSTIC: trailing inclusive 756-session percentile, min 60 finite observations.

ROLLING variants are diagnostics only and are not eligible to replace the existing definition from this study.

## Fixed eras
- 2017-2019
- 2020-2021
- 2022-2026
Also report EXCLUDE_2020_2021 across all remaining years.

## Outcomes
For each variant and era:
- onset count and dates;
- SPX forward 5D/10D/20D mean, median and positive rate;
- independent 20-session event clusters.

## Historical controls
For each variant's full-history event set:
- 5,000 deterministic-seed placebo samples with the same event count from matured eligible dates; primary statistic = mean 10D return.
- Regime-matched controls: same above/below-SMA200 regime and same RV20 >=20% / <20% regime; nearest in trailing 20D return and RV20, 5 controls/event, excluding +/-20 sessions around treatment events. Report treatment-minus-control 10D mean lift.

## Stability interpretation
Report whether 10D mean return is positive in every fixed era with at least 5 events. This is descriptive only; no optimization, threshold selection, or production promotion is allowed.

## Guardrails
- Historical sentiment values are reconstructed from current Yahoo/FRED history, not point-in-time archived outputs.
- The source sentiment composites themselves already contain rolling-percentile transforms; this study is about normalization robustness, not a claim that a rolling variant is cleaner or causal.
- No production or Forward-OOS change may result automatically.