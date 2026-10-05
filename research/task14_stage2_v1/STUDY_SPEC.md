# Task 1/4 Stage-2 Research V1 — Study Specification

Status: **post-discovery diagnostic only**. This file freezes the implementation intent after the first Task 1/4 extended-diagnostics pass. Nothing here changes MAIN, production sizing, existing Sequence V1, RMD3, or any Forward-OOS ledger.

## Ten diagnostic blocks

1. **Regime conditioning** — evaluate frozen full-sequence events by point-in-time S&P 500 MA200 phase and by fixed 20% annualized realized-volatility split.
2. **Leave-one-year-out robustness** — remove each event year in turn, with explicit 2022 removal; report Sequence forward-return summaries and historical RMD3-vs-10D rank association.
3. **Placebo random-date test** — draw 10,000 deterministic random date sets of equal event count from dates with mature 20D outcomes; compare real Sequence 5D/10D/20D means to the placebo distribution. Descriptive only; not a full serial-dependence or multiple-testing correction.
4. **Order necessity** — among DUAL episodes with all four milestones observed, compare strict `Breadth Low -> Box Bottom -> Breadth Rebound -> Score Recovery` ordering with non-strict order and selected alternative order classes.
5. **Continuous Sequence Maturity** — equal-weight, non-optimized 0–100 diagnostic composed of fixed current-information components: DUAL recency, breadth stress, box depth, breadth rebound distance, and positive Market Score D3 recovery.
6. **RMD x DUAL Severity surface** — 2x2 diagnostic using historical RMD3 median and fixed Severity `> 6pp` split. This does not replace either frozen score.
7. **Competing risk** — from each full-sequence signal, test whether +3% / +5% upside is reached before a close breaks the prior DUAL-path trough within 20 sessions.
8. **Entry/Exit timing matrix** — fixed signal delays of 0/1/2/3/5 sessions crossed with fixed 5/10/20-session holding horizons. Diagnostic only; no best cell is automatically selected.
9. **Cross-market confirmation** — at each Sequence event, inspect 5-session direction of QQQ, IWM, HYG, LQD and VIX. Positive ETF direction and falling VIX count as confirmations. Data are fetched from Stooq/FRED with no API key; missing feeds must be reported explicitly.
10. **Historical analogs** — fixed-scale Euclidean neighbors using net-liquidity 4w, reserves 4w, breadth percentile, box position, and market-score percentile/score. Historical validation may use only neighbors at least 20 sessions earlier than the target event.

## Anti-overfit rules

- No weight fitting, threshold search, or cell selection is allowed inside this V1 diagnostic.
- All outputs remain `research_only`, `diagnostic_only`, and `production_effect = none`.
- Any candidate inspired by these results must be separately preregistered and frozen before it can collect independent Forward-OOS evidence.
- Historical performance from this suite can never count as Forward-OOS promotion evidence.
