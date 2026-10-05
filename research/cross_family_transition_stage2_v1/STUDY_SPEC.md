# Cross-Family Transition Stage-2 V1

Status: research-only / diagnostic-only. No production effect.

Purpose: replace same-day cross-family AND tests with ordered event-transition tests, because the prior factor-map study showed that Sentiment Extreme onsets do not occur on the exact same sessions as Box Bottom / Breadth Rebound / Sequence onsets.

## Frozen event definitions
- Sentiment Extreme: sentiment_stress_pct >= 80, false->true onset, 5-session de-cluster.
- DUAL onset: existing frozen dual_drain false->true onset.
- Box Bottom: box_position <= 0.25, false->true onset, 5-session de-cluster.
- Breadth Low: at least 2 of SPX/Nasdaq/Dow 20D U/D expanding percentiles <=20, false->true onset, 5-session de-cluster.
- Breadth Rebound10: in the latest 10 sessions breadth_20d_pct previously reached <=20, and current breadth is above that trough and above the prior session; false->true onset, 5-session de-cluster.
- Score Recovery: recent 10-session minimum market_score_pct <=20 AND market_score_d1>0 AND market_score_d3>0, false->true onset, 5-session de-cluster.
- Early Sequence and Full Sequence: existing Task 1/4 frozen definitions.

## Transition study
For every source event family and destination family:
- Search only forward from the source date.
- Horizons: 5 / 10 / 20 / 40 trading sessions.
- For different source/destination families, same-day transition lag 0 is allowed.
- For source==destination, require the next distinct event (lag >=1).
- Report hit count/rate, median first-hit lag, and p25/p75 lag.

### Regime-matched transition baseline
For each source event, choose up to 5 control dates that:
- have the same above/below-SMA200 price regime and the same fixed RV20 >=20% / <20% regime;
- are not treatment-event dates and are not within +/-20 sessions of any source event;
- have a matured 40-session future window;
- minimize equal-weight normalized distance in trailing 20D return and RV20.
For each transition/horizon, compare treatment hit rate with the per-source matched-control hit probability. This is a historical diagnostic, not a causal claim.

## Source-centered event-time outcomes
For each source family, report SPX forward 5D/10D/20D return summaries. For Sentiment Extreme specifically, split by whether each destination family is reached within 20 sessions.

## Sparse factor follow-up
The prior five-family factor map found the full dense model did not improve LOYO MSE. Freeze the following post-discovery candidate subsets for diagnostic comparison only:
- baseline controls only;
- baseline + sentiment;
- baseline + liquidity;
- baseline + score;
- baseline + sentiment + liquidity;
- baseline + sentiment + score;
- baseline + liquidity + score;
- baseline + sentiment + liquidity + score.
Baseline controls: trailing 20D SPX return, RV20, and above/below-SMA200 dummy.
Family features are exactly those in factor_map_stage2_v1.

Evaluate each fixed subset with Leave-One-Year-Out OLS for 5D/10D/20D and report pooled MSE relative to baseline. Do not search arbitrary subsets or optimize weights.

## Guardrails
- This study is explicitly post-discovery historical diagnostics.
- No transition or sparse subset may alter production or the existing Forward-OOS ledgers.
- Small transition cells are weak evidence.
- FRED current-history values may contain revisions; not ALFRED vintages.
- A transition association is not proof of causality.