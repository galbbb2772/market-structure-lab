# Task 1/4 Stage-4 Stock Paper Execution V1

Status: FROZEN prospective paper-execution protocol.

## Purpose
Consume only the Task 1/4 Stage-4 Stock Candidate Adapter V1 trade pool and measure individual-stock execution prospectively. This study does not generate, re-rank, or backfill stock candidates.

## Freeze boundary
- Task 1/4 historical development is frozen through 2026-10-02.
- Only exact-date aligned candidates with as_of_market_date > 2026-10-02 are eligible.
- Historical/backfilled candidates never count as prospective evidence.

## Upstream source
- docs/data/task14_stage4_stock_candidate_adapter_v1.json
- adapter_trade_pool_eligible must be true.
- Frozen V4 source version remains pinned by the adapter.

## Portfolio rule
- Long only.
- Signal decision time: signal-date close.
- Entry: next regular SPY trading session open.
- Exit: close of signal date +10 SPY trading sessions.
- Event sleeve target: 25% of portfolio NAV.
- Single-name target cap: 10% of portfolio NAV.
- If fewer candidates exist, unallocated sleeve capital stays in cash.
- Total portfolio gross cap: 100%.
- Candidates within an event are equal-weighted before the single-name cap.
- No leverage, no shorting, no post-hoc sector exclusion.
- Upstream rank is recorded for audit only and does not change V1 weights.

## Cost models
Both are frozen and run prospectively:
1. fixed_25bps_rt: 25 bp round-trip cost per stock position.
2. fixed_50bps_rt: 50 bp round-trip stress case.

Half of the round-trip cost is charged at entry and half at exit.

## Risk diagnostics
- 60-session trailing beta versus SPY, computed using information available through signal date.
- Upstream frozen ADV20 in USD.
- Entry notional / ADV20 participation.
- Gross exposure.
- Beta exposure.
- Maximum single-name portfolio weight.
- Sector exposure is not inferred in V1 because the frozen candidate contract does not contain a point-in-time sector classification.

Risk diagnostics do not modify selection or sizing.

## Immutability
Once first observed, the following are immutable:
- candidate_id
- symbol
- signal_date
- candidate_first_seen_at
- upstream_rank
- target_portfolio_weight
- accepted/skip decision
- entry date and entry price once populated
- ADV20 and beta60 captured for the execution decision

Recomputation mismatches fail the build; they are never silently rewritten.

## Guardrails
- research_only=true
- paper_only=true
- production_effect=none
- broker_orders_enabled=false
- automatic_stock_selection=false
- rank_recomputed=false
- historical_results_count_as_forward_oos=false
- no threshold optimization
- no historical candidate backfill
- no automatic promotion

## Evidence rule
This ledger is prospective execution evidence only. It cannot promote a production rule automatically. Any later change to sizing, holding period, cost model, or candidate rule requires a new preregistered version.
