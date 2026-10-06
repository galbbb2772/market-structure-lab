# Pure Box Geometry / R:R Study V1

Research-only. This study asks whether the missing edge is inside the box geometry itself.

## Frozen strategy context
No external indicator or market filter is added. Universe, box detection, long-only direction, entry timing, transaction cost, target and baseline invalidation remain the same as Pure Box Liquid Leaders V1.

Primary universe: daily causal Top500 by prior-20-session average dollar volume.

Baseline trade mechanics:
- entry: next session open after a valid signal;
- invalidation/stop: box lower edge;
- target: box upper edge;
- if stop and target are both touched in one daily bar, stop first;
- 5 bps each side;
- small box requested weight 50%; large box requested weight 100%.

## Geometry known at entry
For every executable candidate:
- entry_fraction = (entry - lower) / (upper - lower)
- downside_pct = (entry - lower) / entry
- upside_pct = (upper - entry) / entry
- rr = upside_pct / downside_pct
- box_width_pct = (upper - lower) / entry
- box_age_sessions = sessions from detected_at to signal_date

All are causal and known before/at entry.

## Two-stage test
### A. Signal-quality decomposition
Evaluate executable non-overlapping same-symbol opportunities and report quintiles for:
- rr
- entry_fraction
- downside_pct
- upside_pct
- box_width_pct
- box_age_sessions

Metrics: count, mean/median return, win rate, profit factor, target rate, stop rate, average hold.

Report separately for:
- full 2019-2026Q1;
- discovery 2019-2022;
- validation 2023-2026Q1;
- small vs large where sample permits.

A useful geometry variable should show a directionally similar relationship in discovery and validation rather than only a single full-sample optimum.

### B. Portfolio selection
Use the same baseline exits and requested weights. Compare:
1. baseline proportional allocation across all same-day candidates;
2. RR priority: sort same-day candidates by highest rr and allocate requested weights sequentially until cash is exhausted;
3. upside priority: sort by highest upside_pct;
4. lower-edge priority: sort by lowest entry_fraction.

No minimum threshold is used in the primary ranking test. This avoids choosing a cutoff after seeing returns.

Sensitivity-only RR thresholds are 1, 2, 3, and 4 and must be labeled exploratory, not optimized.

## Decision rule
Do not call R/R useful merely because one cutoff has the highest historical return. Prefer evidence if:
- higher-RR bins improve trade expectancy/PF in both discovery and validation; and/or
- RR-priority improves portfolio Sharpe/PF or return/drawdown versus baseline across Top300 and Top500.

## Caveat
The liquid-leader universe is still a point-in-time liquidity proxy, not an exact historical market-cap/industry-leader universe.
