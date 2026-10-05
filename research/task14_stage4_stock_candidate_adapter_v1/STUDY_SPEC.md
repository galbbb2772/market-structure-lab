# Task 1/4 Stage-4 Stock Candidate Adapter V1 — Frozen Contract

## Purpose

Provide a forward-only interface between an upstream U.S.-equity candidate generator and the existing Task 1/4 Stage-4 execution/paper infrastructure.

This adapter **does not discover, rank, optimize, or backfill stocks**. It only validates and standardizes an already-frozen upstream candidate snapshot.

## Freeze boundary

- Task 1/4 historical development is frozen through market date `2026-10-02`.
- Only candidate snapshots with `as_of_market_date > 2026-10-02` may be marked `forward_eligible=true`.
- Historical/backfilled candidate snapshots may be stored for engineering tests but never count as Forward-OOS evidence.

## Optional upstream feed

Expected path: `docs/data/stock_candidate_feed_v1.json`.

If the file is absent, the adapter must succeed with status `AWAITING_UPSTREAM_FEED` and emit zero candidates. It must never invent a candidate list.

### Feed-level required fields

- `schema`: `STOCK-CANDIDATE-FEED-V1`
- `generated_at`: timestamp
- `as_of_market_date`: `YYYY-MM-DD`
- `source_name`
- `source_version`
- `candidates`: array

### Candidate-level required fields

- `symbol`
- `candidate_id` — immutable upstream identity
- `first_seen_at` — timestamp of first publication
- `rank` — upstream rank only; adapter may not recompute it
- `trigger_reasons` — non-empty array of upstream reasons

Optional point-in-time metadata may include `sector`, `industry`, `price`, `adv20_usd`, `market_cap_usd`, and upstream diagnostic scores.

## Validation rules

1. Symbols must be unique within a snapshot.
2. `candidate_id` must be unique within a snapshot.
3. `trigger_reasons` must be non-empty.
4. The adapter may not add or modify `rank`.
5. No field whose name indicates future outcome/return/PnL may be accepted in candidate payloads.
6. `as_of_market_date` must not be later than the latest upstream market-state date used for alignment.
7. `forward_eligible=true` only when `as_of_market_date > 2026-10-02`.
8. The adapter performs no historical performance selection and no automatic sector exclusion.

## Task 1/4 signal alignment

The adapter reads `docs/data/task14_challenger_forward_oos_v1.json` and reports current forward signal counts for:

- Early Sequence
- RMD2 Price+Score
- D+1 Entry
- DUAL Severity Hazard

A candidate snapshot is considered `signal_aligned=true` only if at least one Task 1/4 forward event has a signal date equal to the snapshot `as_of_market_date`. No nearest-date or future-date matching is allowed.

## Output

Path: `docs/data/task14_stage4_stock_candidate_adapter_v1.json`.

The output is research/paper infrastructure only and must preserve:

- `production_effect = none`
- `broker_orders_enabled = false`
- `historical_results_count_as_forward_oos = false`
- `automatic_stock_selection = false`
- `automatic_policy_promotion = false`

## Promotion / execution guardrail

This adapter is not authorization to trade individual stocks. A separate preregistered candidate-generation rule plus prospective evidence is required before any stock-selection logic can be promoted into execution.