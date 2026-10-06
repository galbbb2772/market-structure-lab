# Structure Decay Portfolio V1.2

Status: post-hoc portfolio diagnostic only. No production promotion.

## Question
Does excluding new entries whose lower boundary has already reached the preregistered 3+ touch-episode cliff improve the actual Pure Box portfolio, rather than only isolated trade statistics?

## Frozen inputs
- Source run: Pure Box Liquid Leaders V1, run 37424716935.
- Validation window only: 2023-01-01 through 2026-03-31.
- Top300 and Top500 causal liquidity universes.
- Long only.
- Next-session open entry.
- Stop at box lower; target at box upper.
- Same-day stop+target -> stop first.
- 5 bps per side.
- Small requested weight 50%; large requested weight 100%.

## Frozen vitality thresholds from 2019-2022 discovery
Small:
- Fresh age <= 8 sessions
- Wide threshold >= 0.1008858137242378

Large:
- Fresh age <= 18 sessions
- Wide threshold >= 0.2025964527335894

## Lanes
1. fresh_all
2. fresh_no3plus: Fresh AND touch_episodes <= 2
3. wide_fresh_all
4. wide_fresh_no3plus: Wide+Fresh AND touch_episodes <= 2

No other touch threshold is tested in this V1.2.

## Decision readout
Compare:
- total return / CAGR / MDD / Sharpe
- PF / mean trade / trade count / exposure
- yearly returns
- 2026Q1 specifically
- Top300 and Top500 consistency

Important: the 3+ cliff was observed before this portfolio test, so this is confirmation on reused validation data, not untouched OOS.
