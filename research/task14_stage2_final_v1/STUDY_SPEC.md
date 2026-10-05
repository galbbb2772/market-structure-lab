# Task 1/4 Final Stage-2 Study Spec V1

Status: post-discovery diagnostic only. No production effect. No existing Forward-OOS ledger or frozen rule may be changed by this study.

This final historical Stage-2 block is frozen before execution and contains exactly five analyses.

## 1. Matched-Control diagnostic

Population: frozen Full Sequence completion onsets.

For every event, candidate controls must be ordinary market dates with mature 20D outcomes, must not be a Full Sequence event, and must be at least 20 market sessions away from every Full Sequence event.

Matching uses only same-day/current-information covariates: MA200 phase (exact-match where available), 20D price return, realized volatility 20D, net-liquidity 4W %, reserve-balances 4W %, breadth percentile, box position, and Market Score. Continuous covariates are standardized on the candidate pool. Up to five nearest controls are retained per event. Controls may be reused across events; this is reported explicitly.

Primary diagnostic: event 10D return minus the mean 10D return of its matched controls. Also report 5D and 20D. No matched-control result changes MAIN.

## 2. Threshold Stability Surface

This is a perturbation/stability test, not parameter optimization.

Frozen grid:
- symmetric DUAL threshold applied to both net-liquidity and reserves: -1.5%, -2.0%, -2.5%;
- Breadth Low: 15, 20, 25 percentile;
- Box Bottom: 0.20, 0.25, 0.30.

All other Sequence logic remains unchanged: recent-DUAL window 10 sessions, path window 20 sessions, Score Recovery `market_score_d1 > 0 AND market_score_d3 > 0`, onset-only event extraction, 5-session declustering.

Report event count and 5D/10D/20D outcomes for all 27 cells. The frozen center is (-2.0%, 20, 0.25). No cell may be promoted because it looks best retrospectively. Stability is descriptive: nearby cells retaining direction/magnitude is supportive; a needle-like center is a warning.

## 3. Lead/Lag Event Study

Anchor: frozen Full Sequence completion onset T0.

Window: T-20 through T+20 market sessions.

Track cross-event mean and median for S&P 500 cumulative return normalized to T0, net-liquidity 4W %, reserve-balances 4W %, breadth percentile, box position, Market Score, Market Score D1/D3, and realized volatility 20D. Missing values remain missing.

Also report descriptive turning offsets (minimum/maximum mean where economically appropriate). These are not trading rules.

## 4. Orthogonal Information Test

Population: frozen Full Sequence historical events.

Primary horizon: 10D.

Use rank-based residualization / partial Spearman to measure incremental information after controlling for DUAL severity and MA200 phase. Test RMD3 and its price/breadth/score components; where box residual is available, test it as a secondary smaller-N diagnostic. Also report simple OLS R-squared increment for transparency, clearly marked unstable at small N.

No variable selection, coefficient fitting for production, or threshold discovery is allowed.

## 5. Indicator Redundancy Map

Population: all daily observations in the Market State Box history after enrichment with DUAL, forward-safe price/regime diagnostics, and Sequence state.

Automatically include numeric current/past-information state variables with at least 500 finite observations. Exclude dates, identifiers, event labels, forward-return/MFE/MAE/outcome fields, future-derived fields, and private index helpers.

Compute pairwise Spearman correlations on overlapping observations. Report all pairs with |rho| >= 0.80 and connected redundancy families under that fixed threshold. Also report the strongest non-redundant links (0.60 <= |rho| < 0.80). The map is diagnostic and cannot by itself delete an indicator from production.

## Shared safeguards

- Historical development data only; no Forward-OOS event is added or rewritten.
- No threshold or weight optimization.
- No automatic production promotion.
- FRED current-history values may contain revisions and are not ALFRED vintages.
- Small event count and 2022 concentration must be carried into interpretation.
