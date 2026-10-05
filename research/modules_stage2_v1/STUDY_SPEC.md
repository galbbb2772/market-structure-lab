# Cross-Module Stage-2 Validation V1

Status: research-only / diagnostic-only. No production effect.

Purpose: apply one consistent Stage-2 validation factory to the remaining Market Structure Lab modules after Task 1/4 historical Stage-2 was effectively saturated.

## Modules
1. Box state
2. Sentiment stress
3. Three-index breadth
4. Composite market score
5. Historical streak / concentration analogs

## Common rules
- Historical results are discovery/diagnostic evidence only.
- No existing production rule, frozen Forward-OOS ledger, or Task 1/4 definition may be changed by this study.
- Event studies use false->true onsets and a 5-session de-cluster gap.
- Primary descriptive horizon: 10 trading days. Secondary: 5 and 20 trading days.
- Price-regime conditioning uses S&P 500 relative to its trailing 200-session mean; volatility conditioning uses realized 20D annualized volatility with a fixed 20% split.
- Placebo uses fixed-seed random samples from eligible non-event dates. It is not a multiple-testing-adjusted confirmatory test.
- Matched controls exclude the treatment variable itself, require the same price regime when feasible, exclude dates within +/-20 sessions of any treatment event, and use equal-weight normalized Euclidean distance across available matching covariates.
- LOYO is descriptive sensitivity, not model selection.

## Fixed stability neighborhoods
These are perturbation grids, not optimization grids. The best historical cell must not be promoted.

### Box
- position <= 0.15 / 0.25 / 0.35
- frozen center = 0.25

### Sentiment
- expanding sentiment-stress percentile >= 70 / 80 / 90
- frozen center = 80

### Breadth
- at least 2 of S&P 500 / Nasdaq / Dow 20D up-down balance expanding percentiles <= 15 / 20 / 25
- frozen center = 20

### Composite score recovery diagnostic
- recent 10-session minimum market-score percentile <= 10 / 20 / 30
- followed by frozen recovery confirmation: score D1 > 0 AND D3 > 0
- center diagnostic threshold = 20
- this is a new historical diagnostic, not an existing production rule.

## Score-specific tests
- Spearman rank IC of market-score percentile versus forward 5D/10D/20D return.
- Decile forward-return profile.
- Score-recovery event study using the fixed neighborhood above.

## Concentration / streak analog validation
Re-use the existing V1 feature distance and settings, but evaluate historically rather than only on the latest date:
- targets require abs(streak) >= 2;
- target events are de-clustered 5 sessions;
- analog candidates must be strictly prior to the target and have fully matured 10D outcomes before the target;
- same streak direction, abs(streak) tolerance 1, same MA200 regime;
- top 40 analogs, 5-session candidate de-cluster;
- compare analog prediction with exact-streak historical baseline;
- report 5D/10D walk-forward direction accuracy, MAE, Brier score, and Spearman where available.

## Interpretation guardrails
- Small or clustered event samples remain weak evidence even if means are large.
- A stable neighborhood is more important than the single best grid cell.
- Highly correlated variables count as one information family, not multiple independent confirmations.
- No result in this file is eligible for automatic strategy promotion.
