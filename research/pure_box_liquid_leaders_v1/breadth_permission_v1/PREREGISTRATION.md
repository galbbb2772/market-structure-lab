# Pure Box Breadth Permission V1

Research-only. No production effect.

## Question
Can point-in-time cross-sectional market breadth distinguish healthy pullbacks from environments where long box mean reversion is likely to fail?

This follows Market Permission V1, where SPY-only trend filters partially helped 2022 but did not fully explain 2026Q1.

## Frozen strategy context
Same causal liquid-leader universe and Pure Box rules:
- long only
- next-session-open entry
- lower box edge stop
- upper box edge target
- 5 bps each side
- small requested weight 50%, large 100%
- primary sleeves: fresh-only and wide+fresh
- box width/age thresholds are annual walk-forward and formed from prior years only

## Daily breadth universe
Reconstruct daily causal Top500 / Top300 from the stored daily bars:
- prior-20-session average dollar volume
- close >= $5
- ADV20 >= $25M
- rank descending by ADV20
- no future membership information

Because the source lacks a full historical security-type master, this remains a high-liquidity listed-instrument proxy rather than a perfect historical common-stock universe.

## Breadth features
All features are computed using signal-date close only:
- pct_above_ma50
- pct_above_ma200
- pct_ret20_positive
- pct_ret63_positive
- pct_up_1d
- median_ret20
- median_ret63
- pct_new_20d_low (close at/under prior rolling 20d low)
- pct_new_63d_low
- cross_section_ret20_dispersion

## Pre-registered gates
No threshold is optimized on test-year returns.

Natural 50% gates:
1. all
2. breadth_ma50: pct_above_ma50 >= 50%
3. breadth_ret20: pct_ret20_positive >= 50%
4. breadth_ma200: pct_above_ma200 >= 50%
5. breadth_dual: pct_above_ma50 >= 50% AND pct_ret20_positive >= 50%
6. breadth_any: pct_above_ma50 >= 50% OR pct_ret20_positive >= 50%
7. avoid_internal_breakdown: NOT (pct_above_ma50 < 35% AND pct_ret20_positive < 35%)
8. avoid_broad_weakness: NOT (pct_above_ma200 < 40% AND pct_ret63_positive < 40%)
9. low_new_lows: pct_new_20d_low < 20%
10. composite_3of4: at least 3 of {ma50>=50%, ma200>=50%, ret20>=50%, ret63>=50%}

## Evaluation
Annual walk-forward 2021..2026Q1.
For each year:
- box vitality thresholds use only prior years;
- breadth is point-in-time and uses only contemporaneously eligible liquid leaders;
- gates apply only to new entries.

Report yearly returns, MDD, Sharpe, exposure, trade count, PF, and compounded annual walk-forward return.
Decision preference:
- materially improve both 2022 and 2026Q1;
- not destroy 2021/2023-2025;
- direction consistent in Top300 and Top500;
- improve risk-adjusted performance, not just raw return.
