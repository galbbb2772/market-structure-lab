# Pure Box Integrity Portfolio V2.1 — Cross-Year Audit

Research-only. No production promotion.

This audit repairs two methodological issues in Integrity Portfolio V2:
1. annual source bars were target-year only, which could truncate January box history / age;
2. annual breadth was recomputed inside a one-year shard, which lacked full lookback history.

## Repairs
- load Y-1, Y, Y+1 bars when available for each test year;
- compute box age and lower-touch episodes with cross-year history;
- use the persisted full-history causal Breadth Permission V1 daily series;
- keep the same frozen annual walk-forward Fresh / Wide+Fresh thresholds;
- keep integrity gates unchanged: all, avoid_3plus, avoid_3plus_and_cluster;
- keep breadth gates unchanged: none, breadth_dual, avoid_internal_breakdown.

## Years / universes
2021-2026Q1; Top300 and Top500.

## Decision standard
This remains post-hoc because 3+ was discovered before this portfolio test.
Use V2.1 only to answer economic significance and interaction:
- does avoiding 3+ improve actual portfolio risk/return?
- is Breadth complementary to integrity?
- are effects directionally stable across Top300/Top500 and Fresh/Wide+Fresh?
