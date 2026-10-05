# Task 1/4 Stage-4 Multi-Asset V1 — Study Spec

## Purpose

Extend Task 1/4 Stage-4 from the single-SPY execution proxy into a real multi-asset execution and portfolio-risk diagnostic while preserving all frozen Stage-2 and Stage-3 signal definitions.

The upstream signal is market-level. Therefore V1 deliberately does **not** invent a historical stock-selection rule. Instead it deploys the same signal into the complete U.S. sector-ETF cross-section and makes the execution engine stock-ready for a later, separately frozen stock-candidate stream.

## Frozen boundary and signal sources

- Development / Forward-OOS boundary: `2026-10-02`.
- Historical signal definitions are unchanged.
- Full Sequence: frozen `D_TO_BOTH_REBOUND_SCORE` onset with the existing 5-session de-cluster.
- Early Sequence: frozen `D_TO_BREADTH_LOW AND box_bottom_since_dual AND breadth_rebound_since_dual` onset with the existing 5-session de-cluster.
- Future events must come only from `docs/data/task14_challenger_forward_oos_v1.json`.
- Historical results never count as Forward-OOS evidence.

## Frozen tradable universe

The V1 sector-ETF proxy universe is fixed before inspecting portfolio results:

- `XLC` — Communication Services
- `XLY` — Consumer Discretionary
- `XLP` — Consumer Staples
- `XLE` — Energy
- `XLF` — Financials
- `XLV` — Health Care
- `XLI` — Industrials
- `XLB` — Materials
- `XLRE` — Real Estate
- `XLK` — Technology
- `XLU` — Utilities

`SPY` is fetched only as the market benchmark / beta reference and is not one of the 11 sector sleeves.

V1 is a sector-ETF execution proxy, not a claim that these ETFs are the final production instruments.

## Market data and look-ahead controls

For every signal date and every asset, only information available on or before the signal close may be used for sizing / diagnostics:

- trailing 20-session realized volatility;
- trailing 20-session average dollar volume (`close * volume`);
- trailing 60-session beta versus SPY using close-to-close returns.

Entry is the next regular session open. The primary exit is the close at signal-date +10 SPY trading sessions, matching Stage-4 Portfolio V1. Missing or stale asset bars cause the affected asset/event to be rejected rather than forward-filled through the execution date.

## Fixed asset-allocation rules

No allocation rule is selected after looking at returns. All are evaluated in parallel.

### A1 — Equal weight

- Equal weight across all eligible sector ETFs.
- Sector weight cap: 20%.
- Any residual caused by data ineligibility remains cash.

### A2 — Inverse volatility

- Raw weight = inverse trailing-20D annualized volatility.
- Normalize across eligible sector ETFs.
- Apply an iterative 20% single-sector cap and redistribute excess only among uncapped eligible sectors.
- No leverage.

### A3 — Inverse volatility with beta cap

- Start from A2 weights.
- Ex-ante portfolio beta = weighted mean of trailing-60D asset beta versus SPY.
- If ex-ante beta exceeds 1.00, scale total sleeve gross by `1 / beta`.
- If beta is <=1.00, do not lever up.
- Single-sector cap remains 20% of sleeve gross.

## Fixed signal / sleeve policies

### P1 — `full_eq_sector_100_dedup`

- Full Sequence only.
- A1 equal-weight sector allocation.
- Maximum one active signal sleeve at a time.
- Target gross exposure: 100% of current equity.

### P2 — `full_invvol_sector_100_dedup`

- Full Sequence only.
- A2 inverse-volatility allocation.
- Maximum one active signal sleeve at a time.
- Target gross exposure: 100% of current equity.

### P3 — `early_full_stack25_invvol_cap100`

- Early Sequence + Full Sequence.
- Each accepted signal attempts a 25%-of-current-equity sleeve.
- A2 inverse-volatility allocation inside each sleeve.
- Multiple signal sleeves may overlap.
- Total gross exposure cap: 100% of current equity.
- Same-date Full Sequence has priority over Early Sequence.

### P4 — `early_full_stack25_beta100_cap100`

- Same signal stacking as P3.
- A3 inverse-volatility allocation with ex-ante beta cap.
- Total gross exposure cap: 100% of current equity.

## Execution-cost model

V1 evaluates two round-trip models in parallel.

### C1 — `fixed_10bps_rt`

- Fixed 10 bps round trip per asset trade.
- Half charged at entry and half at exit.

### C2 — `square_root_impact`

For each asset trade:

- round-trip floor = 1 bp;
- `sigma20_daily_bps` = trailing-20D daily return standard deviation in bps;
- participation = asset trade notional / trailing-20D asset ADV;
- round-trip cost bps = `1 + sigma20_daily_bps * sqrt(participation)`.

This is a stress envelope, not a calibrated broker fill model.

## Capital scales

Primary historical comparison starts at USD 100,000.

The multi-asset capacity sweep is fixed at:

- USD 100,000
- USD 1,000,000
- USD 10,000,000
- USD 100,000,000

The sweep uses `early_full_stack25_beta100_cap100` with the square-root impact model.

## Required diagnostics

For every policy / cost-model pair report:

- total return;
- maximum drawdown;
- trade / sleeve count;
- skipped-overlap count;
- exposure-day percentage;
- average and maximum gross exposure;
- average and maximum ex-ante beta exposure;
- turnover;
- total modeled cost;
- average modeled round-trip cost bps;
- maximum asset-level ADV participation;
- realized sleeve win rate;
- sector concentration: average / maximum sector weight and HHI;
- per-sector aggregate notional and P&L contribution;
- per-asset ADV / volatility / beta diagnostics.

## Sector and beta interpretation

Unlike SPY-only Stage-4 V1, sector exposure is now explicit because each tradable sleeve maps to one frozen sector ETF. Beta is still an estimate, not a structural factor model: trailing-60D covariance beta versus SPY is used only as an execution / risk diagnostic and for the A3 gross scaler.

## Stock-ready boundary

The engine must keep asset metadata, sizing, ADV, beta, costs, and portfolio accounting separated from the upstream signal stream so a future stock-candidate file can replace the sector proxy universe without changing the frozen Sequence definitions.

A later stock version must have its own preregistration specifying candidate eligibility and ranking. Historical stock candidates must not be selected using future return information.

## Prospective paper multi-asset portfolio

A separate append-only paper ledger must consume only post-`2026-10-02` Forward-OOS Early / Full events.

It may:

- freeze signal identity and first-seen timestamps;
- freeze the sector-ETF allocation, beta estimate, ADV, entry date and next-open prices when first available;
- mature the fixed 10D exit later;
- mark open positions to the latest complete market session;
- report immutable recomputation discrepancies.

It may not:

- rewrite first-seen decisions;
- count historical development events as future evidence;
- place brokerage orders;
- modify Stage-3 promotion gates.

## Guardrails

- `research_only=true`
- `diagnostic_only=true`
- `production_effect=none`
- `thresholds_changed=false`
- no automatic promotion
- no broker orders
- no historical result counts as Forward-OOS
- no new stock-selection rule is inferred from this study
