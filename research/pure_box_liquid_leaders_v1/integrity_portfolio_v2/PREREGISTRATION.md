# Pure Box Integrity Portfolio V2

Research-only. No production promotion.

## Objective
Test whether the previously observed 3+ lower-boundary touch cliff improves portfolio-level results when used as a causal entry filter.

## Frozen evidence carried forward
- Structure Decay V1/V1.1 found that 3+ lower-touch episodes were associated with worse validation outcomes, especially in Fresh / Wide+Fresh sleeves.
- The 3+ threshold is NOT re-optimized here.
- Fresh / Wide+Fresh definitions remain annual walk-forward using prior years only.
- Same Pure Box entry/exit/cost mechanics as prior studies.

## Entry filters
For every candidate:
- baseline sleeve: no integrity filter
- avoid_3plus: require touch_episodes <= 2
- avoid_3plus_and_cluster: touch_episodes <=2 AND touch_last10 <=2

## Market permission overlays
Run each integrity lane under:
- no breadth gate
- breadth_dual: Top500/Top300 internal pct_above_ma50 >= 50% AND pct_ret20_positive >= 50%
- avoid_internal_breakdown: NOT (pct_above_ma50 <35% AND pct_ret20_positive <35%)

Breadth is reconstructed causally using the same methodology as Breadth Permission V1.

## Walk-forward
Years: 2021, 2022, 2023, 2024, 2025, 2026Q1.
For each test year:
- box age/width thresholds use only earlier years;
- touch features use only data through signal-date close;
- breadth uses only signal-date cross-section;
- filter only affects new entries.

## Decision standard
A useful integrity filter should:
- improve 2026Q1;
- not materially worsen 2022;
- improve Sharpe / MDD or PF across Top300 and Top500;
- not merely reduce exposure to near-zero;
- direction should hold in both Fresh and Wide+Fresh if possible.

No production promotion from V2 alone.
