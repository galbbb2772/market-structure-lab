# Task 1/4 Stage-4 Stock Candidate Adapter V1 — Frozen Contract

## Purpose

Bridge the already-frozen Frozen V4 Strict V3 stock candidate engine into Task 1/4 Stage-4 research without creating a second stock-selection model.

The adapter only:
1. fetches the public, versioned candidate feed exported from Frozen V4;
2. validates point-in-time integrity;
3. preserves upstream rank/eligibility without recomputation;
4. aligns candidate snapshots to Task 1/4 Forward-OOS event dates by exact market date.

It does **not** discover, optimize, re-rank, backfill, or authorize stock trades.

## Frozen upstream

Source of truth: `galbbb2772/frozen-v4`.

Canonical feed:
`https://raw.githubusercontent.com/galbbb2772/frozen-v4/main/docs/data/stock_candidate_feed_v1.json`

Public dashboard mirror fallback:
`https://raw.githubusercontent.com/galbbb2772/frozen-v4-dashboard/main/data/stock_candidate_feed_v1.json`

Pinned source identity:
- `source_name = frozen-v4`
- `source_version = FROZEN-V4-STRICT-V3-MASSIVE-EOD-V1`
- upstream contract: `BASE_GENERATOR_CONTRACT.md`

Frozen V4 base candidate logic remains upstream-owned. The Task 1/4 adapter must never reproduce or mutate those rules.

## Task 1/4 freeze boundary

- Historical development frozen through market date `2026-10-02`.
- A snapshot can be Task 1/4 Forward-OOS eligible only when `as_of_market_date > 2026-10-02`.
- Historical or boundary-date snapshots may be retained for engineering/audit but never count as Forward-OOS evidence.

## Feed structure

Feed schema: `STOCK-CANDIDATE-FEED-V1`.

The feed contains an append-style `snapshots` array so delayed workflows cannot erase a prior market day's candidate set.

Each snapshot requires:
- `as_of_market_date`
- `candidate_count`
- `snapshot_sha256`
- `candidates`

Each candidate requires:
- `symbol`
- `candidate_id` — immutable upstream `base_signal_id`
- `first_seen_at`
- `rank` — upstream rank only
- `trigger_reasons` — non-empty upstream reasons

Optional point-in-time fields include security identity, entry date, Frozen V4 selection rank, upstream eligibility, quality score, RSI, DVR, MA20 deviation, ADV20, raw signal close, SPY context, and frozen gate flags.

Future return/PnL/outcome fields are forbidden.

## Multi-date integrity

- Candidate symbols must be unique within one snapshot.
- `candidate_id` must be unique across the complete feed.
- Snapshot dates must be strictly increasing.
- The adapter verifies each `snapshot_sha256`.
- Repeated symbols across different dates are allowed because they represent distinct immutable candidate IDs.

## Source timing / deferred snapshots

Frozen V4 may update before Task 1/4's market-state ledger.

Therefore:
- snapshots with `as_of_market_date > latest_upstream_market_date` are retained as `adapter_snapshot_usable=false`;
- they are not rejected, but they cannot align early;
- once Task 1/4 catches up, the same immutable snapshot becomes usable without rewriting it.

## Exact-date Task 1/4 alignment

The adapter reads `docs/data/task14_challenger_forward_oos_v1.json`.

A stock candidate can be:
- `adapter_forward_eligible=true` only when its snapshot is usable and after 2026-10-02;
- `adapter_signal_aligned=true` only when the snapshot date exactly equals a Task 1/4 Forward-OOS event date;
- `adapter_trade_pool_eligible=true` only when exact-date aligned **and** Frozen V4 already marked the candidate `upstream_eligible=true`.

No nearest-date, next-date, or future-date matching is allowed.

`adapter_trade_pool_eligible` is still research/paper metadata. It is not an execution authorization.

## Cache / transport

The adapter first refreshes the canonical `frozen-v4` repository feed on each run. If that transport is unavailable it may use the public dashboard mirror. The validated payload is stored as a local audit copy at:
`docs/data/stock_candidate_feed_v1.json`.

Transport precedence is frozen as:
1. canonical `frozen-v4` repository feed;
2. dashboard mirror;
3. existing validated local cache.

If both remotes are temporarily unavailable:
- an existing validated local copy may be used as `CACHED_LOCAL_FALLBACK`;
- if no local copy exists, status is `AWAITING_UPSTREAM_FEED`;
- the adapter must never invent candidates.

## Output

`docs/data/task14_stage4_stock_candidate_adapter_v1.json`

Required guardrails:
- `production_effect = none`
- `broker_orders_enabled = false`
- `historical_results_count_as_forward_oos = false`
- `automatic_stock_selection = false`
- `automatic_sector_exclusion = false`
- `automatic_policy_promotion = false`
- `rank_recomputed_by_adapter = false`
- `future_outcome_fields_allowed = false`
- `nearest_date_alignment_allowed = false`
- upstream source version pinned

## Promotion guardrail

This bridge does not change Task 1/4 production. Any future individual-stock execution policy must be separately preregistered and judged on prospective evidence.
