# Residual Mean-Reversion Distance Forward OOS V1 — freeze

Status: observation-only Forward OOS shadow. No MAIN-B / Frozen V4 / production behavior changes.

## Freeze point

- Sequence event definition remains the already frozen `D_TO_BOTH_REBOUND_SCORE` onset.
- Historical development sample is frozen through market date `2026-10-02`.
- The known 12 historical sequence events remain development / diagnostic evidence only and are never counted as Forward OOS observations.
- Only sequence onsets strictly after `2026-10-02` are eligible Forward OOS events.

## Frozen primary score

RMD3 is the only primary Forward OOS score:

1. `price_residual = 1 - expanding_percentile(SPX trailing 20-session return)` using observations available through the event date only; minimum 252 return observations.
2. `breadth_residual = 1 - breadth_20d_pct / 100`, using the already point-in-time three-index breadth percentile in Market State Box V1.
3. `score_residual = 1 - market_score_pct / 100`, using the already point-in-time expanding Market Score percentile in Market State Box V1.
4. `RMD3 = equal-weight mean(price_residual, breadth_residual, score_residual)`.

No thresholds, optimized weights, nonlinear transforms, RMD4, or post-event data may affect the score.

## Append-only rule

- On first detection of a new eligible Sequence event, record its event date, three component values, and RMD3.
- Once recorded, those event-date component values and RMD3 are immutable.
- Later refreshes may only fill forward outcomes as they mature; they must not recompute or overwrite the frozen event-date score.
- If the current source later disagrees with a frozen event score because upstream historical data were revised, retain the frozen score and expose the discrepancy separately rather than silently rewriting history.

## Outcomes

For each Forward OOS event, later fill when available:

- T+1, T+3, T+5, T+10 S&P 500 return;
- 10-session MFE / MAE where available;
- maturity flags for each horizon.

No outcome can affect event inclusion or RMD3.

## Evaluation gate

- Observation only until at least 20 independent Forward OOS events and 12 calendar months have elapsed from the first Forward OOS event.
- Even after the gate, any production use requires a separate preregistered review.
- MAIN-B, Frozen V4, Sequence V1, UPPER-BOX50, and REGIME-COMBO50 are unchanged by this shadow.

## Known caveats

- FRED current-history inputs can contain revisions and are not ALFRED vintage data.
- Market Score history inherits reconstruction caveats from Market State Box V1.
- The append-only first-seen ledger is specifically intended to prevent later upstream revisions from rewriting recorded Forward OOS scores.
