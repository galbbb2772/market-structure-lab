# Pure Box Market Permission V1

Research-only. This study adds a market-permission layer to the already observed box-vitality effect.

## Question
Why did box-vitality perform well in 2021 and 2023-2025 but fail in 2022 and 2026Q1?

The objective is not to turn the strategy into a trend strategy. Market features are used only as a causal gate for opening new long box trades.

## Frozen box logic
- long only
- causal Top300 / Top500 liquid-leader proxy
- next-session open entry
- stop at box lower
- target at box upper
- 5 bps per side
- small requested weight 50%, large 100%
- box vitality thresholds are walk-forward and formed from prior years only

Primary box sleeves:
1. fresh-only
2. wide+fresh

## Market-state features
All are calculated from SPY close data and are known at signal-date close before next-session entry:
- SPY close vs MA50
- SPY close vs MA200
- 20-session SPY return
- 63-session SPY return
- 63-session drawdown from rolling high
- 20-session realized volatility
- prior-history rolling median of realized volatility

## Pre-registered gates
1. all: no market gate
2. above_ma200
3. ret20_positive
4. ret63_positive
5. trend_confirmed: above_ma200 AND ret63_positive
6. avoid_confirmed_downtrend: NOT (below_ma200 AND ret63_negative)
7. avoid_dual_negative: NOT (ret20_negative AND ret63_negative)
8. shallow_drawdown: SPY 63-day drawdown > -5%
9. calm_or_trend: above_ma200 OR RV20 <= prior-252-day median

No gate threshold is optimized from test-year returns.

## Evaluation
Annual walk-forward years 2021..2026Q1.
For every test year:
- box width/age thresholds use prior years only;
- market feature values use only information available through each signal close;
- only new entries are gated; existing positions follow the frozen exits.

Report:
- yearly return, MDD, Sharpe, exposure, trade count, PF;
- compounded walk-forward return across annual sleeves;
- positive-year count;
- whether a gate specifically improves 2022 and/or 2026 without destroying 2021/2023/2024/2025.

## Decision rule
Prefer a gate only if improvement is broad:
- helps at least one stress year materially;
- does not rely on one exceptional year;
- works in both Top300 and Top500;
- improves risk-adjusted results, not only raw return.
