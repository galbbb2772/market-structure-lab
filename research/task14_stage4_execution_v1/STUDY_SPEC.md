# Task 1/4 Stage-4 Execution V1 — Study Spec

## Purpose

Start Stage-4 without changing any frozen Stage-2/3 signal definitions. This layer measures how much of historical signal return survives realistic entry timing, simple execution costs, and liquidity/capacity constraints, then maintains a separate append-only paper-execution ledger for future post-freeze events.

## Frozen upstream signal source

- Historical event set: `docs/data/market_state_sequence_event_audit_v1.json`
- Future event source: `docs/data/task14_challenger_forward_oos_v1.json`
- Development/OOS freeze boundary: `2026-10-02`
- Tradable proxy for this V1 execution study: `SPY`

SPY is only an execution proxy for the market-level Sequence signal. This study does not claim that SPY is the final production instrument.

## Historical execution diagnostic

For every frozen Full Sequence event, compare three entry conventions using the same signal-horizon exit date:

1. `signal_close`: enter at SPY close on the signal date.
2. `next_open`: enter at SPY open on the next trading session.
3. `next_close`: enter at SPY close on the next trading session.

Exit horizons are the signal date + 5, +10, and +20 SPY trading sessions, all exited at that session's close. Keeping a common exit date isolates entry-timing drag rather than extending the holding period for delayed entries.

### Cost stress

Apply fixed round-trip cost assumptions of:

- 0 bps
- 5 bps
- 10 bps
- 25 bps

These are scenario assumptions, not estimates of actual broker fills.

### Delay diagnostics

Report:

- signal-close to next-open gap
- signal-close to next-close gap
- return difference between each delayed entry and signal-close entry

### Capacity diagnostic

For SPY only, estimate trailing 20-session average dollar volume (`close * volume`) on each event date and report simple notional capacity at 1%, 5%, and 10% participation. This is a market-liquidity scale diagnostic only; it is not a recommended participation rate.

## Future paper execution ledger

The paper ledger is separate from the Forward-OOS evidence ledger.

- Only post-freeze Full Sequence events already recorded by the frozen challenger ledger are eligible.
- Each paper record is keyed by event date.
- Planned V1 execution policy: next regular SPY session open.
- Base cost convention for ledger reporting: 10 bps round trip.
- First-seen event identity and entry price/date are immutable once observed.
- Later runs may only mature 5D/10D/20D exits and report discrepancies.
- Zero future events is a valid ledger state.

## Guardrails

- `research_only = true`
- `diagnostic_only = true`
- `production_effect = none`
- no signal threshold changes
- no automatic promotion
- no broker orders
- no position sizing recommendation
- no historical result counts as Forward-OOS
- execution evidence and signal evidence remain separately labeled
