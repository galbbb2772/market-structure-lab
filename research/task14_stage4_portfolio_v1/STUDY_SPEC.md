# Task 1/4 Stage-4 Portfolio V1 — Study Spec

## Purpose

Extend the existing Stage-4 execution diagnostic into a portfolio-level diagnostic without changing any frozen Stage-2/Stage-3 signal definition.

This study asks:

1. What happens when Early Sequence and Full Sequence signals overlap on the same tradable proxy?
2. Is naive signal stacking materially different from same-instrument de-duplication?
3. Does simple volatility targeting improve drawdown/exposure behavior without changing signal eligibility?
4. How sensitive are results to a dynamic ADV/volatility impact model as capital scales?
5. Can we establish an append-only future paper-portfolio ledger that remains separate from Forward-OOS signal evidence?

## Frozen inputs

- Frozen-through market date: `2026-10-02`.
- Full Sequence definition is unchanged: `D_TO_BOTH_REBOUND_SCORE` onset, existing 5-session de-cluster.
- Early Sequence definition is unchanged: `D_TO_BREADTH_LOW AND box_bottom_since_dual AND breadth_rebound_since_dual`, onset only, existing 5-session de-cluster.
- Instrument: SPY as the market-level execution proxy only.
- Entry: next regular trading session open after the signal date.
- Primary exit: close at signal-date + 10 trading sessions, matching the existing Stage-4 convention.
- No stop, target, or discretionary exit is introduced.

## Fixed portfolio policies

All policies are research-only and are evaluated in parallel. No winner is promoted automatically.

### P1 — `full_only_100_dedup`

- Full Sequence only.
- Maximum one SPY position at a time.
- Target market exposure: 100% of current equity.
- Any new Full Sequence signal while a position is active is ignored for portfolio entry purposes.

### P2 — `early_full_100_dedup`

- Early Sequence + Full Sequence.
- Maximum one SPY position at a time.
- Target market exposure: 100% of current equity.
- If Early and Full occur on the same signal date, Full has priority.
- Any new signal while a position is active is ignored.

### P3 — `early_full_vol10_dedup`

- Same signal stream and de-duplication as P2.
- Target exposure fraction = `min(1.0, 10% / trailing-20D annualized SPY realized volatility)`.
- No leverage above 100%.

### P4 — `early_full_stack25_cap100`

- Early Sequence + Full Sequence.
- Each accepted signal attempts to open a 25%-of-equity sleeve.
- Sleeves may overlap even though they reference the same SPY proxy.
- Total gross market exposure is capped at 100% of current equity at entry.
- Same-date Full is processed before Early.

## Transaction-cost models

Both models are run; neither is calibrated to a broker.

### C1 — `fixed_10bps_rt`

- Fixed 10 basis points round trip.
- Half charged at entry and half at exit.

### C2 — `square_root_impact`

Research stress model only:

- Round-trip fixed spread/friction floor: 1 bp.
- Daily volatility input: trailing-20D standard deviation of close-to-close SPY returns, in basis points.
- Participation = trade notional / trailing-20D average dollar volume.
- Round-trip cost in bps = `1 + sigma20_daily_bps * sqrt(participation)`.
- Half charged at entry and half at exit.

This is a square-root style impact envelope, not a calibrated execution forecast.

## Capital scales

Primary portfolio comparison starts at USD 100,000.

Capacity sweep for the volatility-targeted de-duplicated policy:

- USD 100,000
- USD 1,000,000
- USD 10,000,000
- USD 100,000,000

## Required diagnostics

For every policy/cost-model pair:

- total return
- max drawdown
- trade count
- skipped-overlap signal count
- exposure-day percentage
- average and maximum gross exposure
- turnover / starting capital
- total modeled cost
- average modeled round-trip cost bps
- maximum ADV participation
- realized trade win rate

Capacity diagnostics must also report event-level notional thresholds implied by the dynamic cost model for 10/25/50 bp round-trip cost levels.

## Beta / sector interpretation

Because V1 uses SPY only:

- portfolio market beta proxy equals gross SPY exposure by construction;
- sector exposure is broad-market SPY exposure and is not decomposed into historical sector weights;
- true multi-asset beta/sector concentration is explicitly deferred to a later Stage-4 version.

## Prospective paper portfolio

A separate append-only paper-portfolio file must consume only post-freeze Forward-OOS Early/Full events.

It may:

- freeze signal identity and first-seen timestamps;
- record next-open execution when available;
- mature the fixed 10D exit later;
- report recomputation discrepancies.

It may not:

- rewrite first-seen event identity;
- count historical development events as forward evidence;
- place brokerage orders;
- change Stage-3 promotion gates.

## Guardrails

- `research_only=true`
- `diagnostic_only=true`
- `paper_only=true` for the prospective portfolio ledger
- `production_effect=none`
- no automatic promotion
- no signal-threshold changes
- no broker order capability
