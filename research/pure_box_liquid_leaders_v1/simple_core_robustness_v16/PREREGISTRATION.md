# Pure Box Simple Core Robustness V16

Status: research-only robustness audit.

## Frozen simple-core hypothesis
- Top500 primary / Top300 robustness
- Strict Wide + Fresh thresholds fixed from 2019-2022
- source Pure Box signal already occurs with signal close in lower 20%
- following-session OPEN must also remain in lower 20% of the box
- direct entry at that open
- target = 60% of box
- stop = box lower
- max hold = 20 sessions
- 5 bps each side
- same-day stop-first
- fixed 20% requested allocation in the portfolio readout

No confirmation rule, gap filter, RSI/MACD, market regime or ranking.

## Robustness readout
On 2023-01-01 through 2026-03-31:
- event N / mean / PF / win rate
- yearly event mean / PF / N
- 2.5%/97.5% winsorized mean
- symbol-balanced mean
- leave-one-year-out mean
- symbol-cluster bootstrap, 5000 resamples, seed 20261007
- concentration: top-5 symbols' share of absolute gross event P&L

The previously reconstructed portfolio result is also reported for reference.

No production promotion from this study.