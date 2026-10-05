# Task 1/4 Challenger Forward-OOS V1 — Preregistration

Status: **research-only / observation-only**. No production behavior, MAIN strategy rule, existing Sequence V1 event definition, RMD3 score, or existing Forward-OOS ledger may be changed by this study.

## Freeze

- Freeze reference commit: `ec476e7af68ddc33ca021acdba8e4b61a02ed8f6`
- Historical development data are frozen through market date `2026-10-02`.
- Only events with event dates strictly after `2026-10-02` count as forward OOS.
- Historical diagnostics that motivated these challengers are post-discovery evidence and **do not** count toward promotion.
- First-seen event-date fields are immutable. Later refreshes may only fill previously unavailable forward outcomes or record upstream recomputation discrepancies.

## Challenger A — Early Sequence

Purpose: test whether the earlier observable state captures the useful part of Sequence V1 before Market Score recovery confirmation.

Frozen event definition:

`EARLY_SEQUENCE = D_TO_BREADTH_LOW AND box_bottom_since_dual AND breadth_rebound_since_dual`

- Use onset dates only: false -> true transition.
- Use the same 5-trading-session de-cluster rule as Sequence V1.
- Do **not** require `score_recovery_confirmed`.
- No threshold may be altered: Breadth Low = 20th percentile or below; Box Bottom = position <= 0.25; recent DUAL window and path rules inherit frozen Sequence V1.
- Outcomes: S&P 500 forward 1D / 3D / 5D / 10D / 20D returns; 10D and 20D MFE/MAE.

## Challenger B — RMD2 Price+Score

Purpose: independently test the post-discovery finding that Price + Market Score residuals ranked 10D outcomes better than RMD3 historically.

Eligible events: frozen full Sequence event onsets (`D_TO_BOTH_REBOUND_SCORE`) only.

Frozen score:

- `price_residual = 1 - expanding_percentile(SPX 20D return)`
- `score_residual = 1 - market_score_percentile / 100`
- `RMD2_PS = 0.5 * price_residual + 0.5 * score_residual`

No component substitution, reweighting, nonlinear transformation, or threshold optimization is allowed in V1.

Outcomes: S&P 500 forward 1D / 3D / 5D / 10D / 20D returns. Primary rank horizon = 10D. Secondary horizons = 5D and 20D.

## Challenger C — D+1 Entry Timing

Purpose: test whether waiting one full trading session after a frozen full Sequence onset improves the path/return profile.

Frozen rule:

- Signal event = `D_TO_BOTH_REBOUND_SCORE` onset.
- Target entry = close of the **next trading session** (`D+1`).
- No conditional waiting rule is allowed. Every eligible signal receives the same one-session delay.
- Outcomes are measured from the D+1 entry close: forward 1D / 3D / 5D / 10D / 20D returns; 10D and 20D MFE/MAE.

## Challenger D — DUAL Severity Hazard

Purpose: independently test whether severe liquidity drain identifies path risk that RMD does not capture.

Eligible events: frozen full Sequence event onsets (`D_TO_BOTH_REBOUND_SCORE`) only.

At the event date, locate the start of its associated/current-most-recent DUAL episode. Freeze:

`severity_pp = max(0, -2 - net_liq_4w_pct_at_episode_start) + max(0, -2 - reserves_4w_pct_at_episode_start)`

Frozen candidate risk flag:

`HIGH_DUAL_SEVERITY = severity_pp > 6.0`

This 6pp boundary comes from the already-run fixed-band historical diagnostic and is therefore **post-discovery**; only forward OOS observations may support it.

Frozen path outcomes, measured after full Sequence confirmation:

- Prior trough = minimum S&P 500 close from associated DUAL episode start through confirmation date.
- Retest within H = future minimum close through H <= 1.01 * prior trough.
- Break within H = future minimum close through H < prior trough.
- H = 5, 10, 20 trading sessions.
- Primary hazard outcome = 10D prior-trough break.

## Promotion discipline

Each challenger remains observation-only until a separate review is preregistered. Minimum review gate for any challenger:

1. at least 20 forward events for its eligible event family;
2. at least 12 calendar months since the first forward event;
3. no definition changes after the first forward event;
4. evaluation includes event concentration by year/regime and not just pooled averages;
5. any production change requires a new explicit preregistration and must not overwrite existing Task 1/4 history.

No automatic promotion is permitted by this V1 ledger.
