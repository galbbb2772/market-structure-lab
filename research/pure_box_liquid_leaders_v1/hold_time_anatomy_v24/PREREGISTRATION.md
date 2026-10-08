# Pure Box Simple Core Hold-Time Anatomy V24

Status: mechanism research only. Signal core frozen.

## Frozen signal core
Strict Wide + Fresh
Bottom <=20%
direct next-session open
lower-bound stop
target60
5 bps/side
Top300 and Top500
Primary sizing reference: fixed 1.25% risk

## Purpose
Explain why H15 improved capital efficiency versus H20 in V22/V23.

Do not optimize a new hold parameter.

## Required anatomy
For every accepted entry, reconstruct mark-to-market and barrier-aware path through day 20.

Report by holding-age bucket:
- Day 1-5
- Day 6-10
- Day 11-15
- Day 16-20

For each bucket:
- incremental contribution to trade return
- conditional contribution among trades still open entering the bucket
- fraction of trades still alive at bucket start
- stop/target/time-exit counts
- mean/median unrealized return at bucket boundaries
- fraction with positive incremental contribution
- capital-days consumed
- return per capital-day

Also report:
- H15-forced-exit cohort: what would have happened in days 16-20 under H20
- winners vs losers path decomposition
- Top300 vs Top500 consistency
- yearly decomposition where sample size permits

## Interpretation rule
H15 is mechanistically supported only if day16-20 adds weak or negative incremental return relative to capital-days consumed, consistently across Top300 and Top500, without relying on one year or a tiny cohort.
