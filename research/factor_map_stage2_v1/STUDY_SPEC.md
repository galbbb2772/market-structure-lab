# Cross-Family Factor Map Stage-2 V1

Status: research-only / diagnostic-only. No production effect.

Purpose: test whether the major Market Structure Lab information families are complementary or redundant after the cross-module Stage-2 pass.

## Frozen questions
1. In which fixed regimes does Sentiment Stress >= 80th expanding percentile retain its historical rebound effect?
2. Does Sentiment Stress interact with Box Bottom or a recent Breadth rebound?
3. Is the already-locked S&P 500 bullish price-vs-up/down-ratio divergence signal orthogonal to Task 1/4 Sequence signals?
4. Across Liquidity, Sentiment, Breadth, Box, and Score families, which families add incremental historical explanatory / predictive information after controlling the others?

## Fixed definitions
- Primary outcome: S&P 500 forward 10 trading-day close-to-close return. Secondary: 5D and 20D.
- Sentiment extreme: expanding sentiment_stress percentile >= 80.
- Box Bottom: box_position <= 0.25.
- General Breadth rebound: within the latest 10 sessions, breadth_20d_pct previously reached <=20, and today is after that trough with breadth above the trough and above the previous session.
- Full Sequence: existing D_TO_BOTH_REBOUND_SCORE false->true onset.
- Early Sequence: D_TO_BREADTH_LOW AND box_bottom_since_dual AND breadth_rebound_since_dual false->true onset.
- Bullish Breadth Divergence: the existing S&P 500 locked bullish divergence construction with threshold=1.5, contemporaneous corr>=0.25 and positive ratio-leading corr>=0.25, 20-session cooldown. No re-tuning.
- Locked divergence regime gate diagnostic: NOT_HIGH_VOL from the existing robust cross-era gate study.

## Sentiment regime blocks
Use fixed historical labels only:
- Price regime: above / below SMA200.
- Realized volatility regime: annualized RV20 >=20% / <20%.
- Market Model regime: red / yellow / blue / green as already defined.
- Also report the fixed 2x2 Price x RV20 table.

## Sentiment interaction blocks
At sentiment-extreme onsets, compare outcomes when the following contemporaneous conditions are true versus false:
- Box Bottom.
- General Breadth rebound.
- Early Sequence.
- Full Sequence.
These are post-discovery diagnostics; no interaction is eligible for promotion from historical results.

## Divergence orthogonality
- Reconstruct the locked SPX bullish divergence signal from structure_lab.json.
- Compare exact and +/-5, +/-10, +/-20 trading-session proximity to Full Sequence and Early Sequence events.
- Report divergence-event outcomes conditional on being near / far from Task 1/4 events, and vice versa.
- Repeat proximity counts for the locked NOT_HIGH_VOL divergence subset.

## Five information families
Use fixed representative feature sets:
- Liquidity: net_liq_4w_pct, reserves_4w_pct.
- Sentiment: sentiment_stress_pct.
- Breadth: breadth_20d_pct, breadth D1, breadth D3.
- Box: box_position.
- Score: market_score_pct, market_score_d1, market_score_d3.

Baseline controls: S&P 500 trailing 20D return, RV20, and above/below SMA200 dummy.

For complete-case observations:
- report pairwise Spearman among one fixed representative composite per family;
- report each representative composite Spearman versus forward 5D/10D/20D return;
- fit OLS baseline + all five families;
- report in-sample R2 loss when each family is removed;
- run Leave-One-Year-Out OLS and report pooled MSE change when each family is removed. Positive MSE improvement means the family helped out-of-year prediction.

No feature weights, thresholds, family membership, or horizons may be optimized from these results.

## Guardrails
- Historical findings are diagnostic only and cannot alter Task 1/4 Forward-OOS ledgers.
- FRED current-history inputs may contain revisions and are not ALFRED vintages.
- Small interaction cells must be treated as weak evidence even if returns are large.
- In-sample incremental R2 without positive LOYO contribution is explanatory, not prospective evidence.
- No automatic production promotion.