# Pure Box Long V1 — preregistration

Research-only branch. Production / Frozen V4 rules remain unchanged.

## Goal
Test whether the user's existing range-box definition has standalone long-only edge before adding any other factor.

## Frozen box source
Use the existing Structure Lab V1 point-in-time boxes exactly as published:
- small: 20 sessions, max width 14%
- large: 60 sessions, max width 28%
- at least two touches on each side
- detected after `detected_at` close; first eligible trade is next session
- no completed-box duration, final score, future breakout or future bars may be used for entry

## Trading rule
- Long only. No shorts.
- Signal at close when price is inside the bottom 20% of an active box:
  `lower <= close <= lower + 0.20 * (upper-lower)`.
- If both a small and large box qualify on the same symbol/date, use the large box.
- Entry: next available session open.
- If next open is already <= lower or >= upper, reject the entry as stale/invalid rather than synthesize an impossible fill.
- Stop: chosen box lower edge.
- Take profit: chosen box upper edge.
- If stop and target are both touched intraday with no intraday sequence data, assume stop first (conservative).
- No time stop, no RSI/MA/regime/sentiment/volume/sector filter, no cooldown and no parameter tuning.

## Sizing
- small box target weight = 50% of account equity
- large box target weight = 100%
- if several entries compete for cash at the same open, requested weights are scaled proportionally so total invested capital cannot exceed 100%; this is portfolio plumbing, not an alpha filter.

## Costs and sample
- 5 bps per side, matching the lab's standard historical cost convention.
- First pilot uses only directly investable instruments already present in public Structure Lab: SPY, QQQ, DIA and the 11 Select Sector SPDRs.
- Evaluation window: 2019-01-01 through the latest complete bar in the dataset.
- This ETF pilot is not the final all-stock 2019-2026 conclusion.

## Required outputs
Portfolio equity, CAGR, max drawdown, daily Sharpe, exposure, trade count, win rate, mean/median trade return, profit factor, average holding period, exit reasons, and small-vs-large breakdown.
