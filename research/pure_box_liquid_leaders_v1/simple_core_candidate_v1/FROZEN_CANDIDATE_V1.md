# Pure Box Simple Core Candidate V1

Status: FROZEN_RESEARCH_CANDIDATE / FORWARD_OOS_REQUIRED
Not production. No broker execution.

## Freeze date
2026-10-07

## Frozen thesis
Fresh, wide boxes entered very near the lower boundary create asymmetric payoff:
the invalidation distance is explicit and small relative to available mean-reversion space.

Historical diagnostics V19-V21 further show that many of the strongest opportunities leave the bottom region quickly.
Therefore timing is an execution invariant:
- take the first eligible next-session-open entry,
- if the opportunity is missed and actual execution price is no longer within Bottom<=20%, do not chase.

The "fast escape" behavior is NOT a tradable filter because it is only observable after the original entry time.

## Frozen rules

### Universe
Primary: Top500 liquid-leader proxy.
Robustness: Top300.

### Geometry
Strict Wide + Fresh thresholds remain fixed from the 2019-2022 discovery sample.

Top500:
- Small width >= 0.13255303761158518
- Small age <= 3 sessions
- Large width >= 0.2832764505119453
- Large age <= 7 sessions

Top300:
- Small width >= 0.13149887551263392
- Small age <= 3 sessions
- Large width >= 0.2831081474441409
- Large age <= 7 sessions

### Entry
- Use existing Pure Box signal.
- Entry = next eligible session open.
- Actual entry fraction must be <=20%:
  (entry - lower) / (upper - lower) <= 0.20
- No confirmation filter.
- If execution is missed and later price is >20%, skip; do not chase.

### Exit
- stop = box lower boundary
- target = lower + 0.60 * (upper-lower)
- max hold = 20 market sessions
- stop-first on same-session stop/target ambiguity
- baseline cost model = 5 bps entry + 5 bps exit

### Sizing
Frozen candidate sizing region:
- primary conservative lane: 1.25% account risk to invalidation per entry
- robustness/aggressive reference: 1.50%
For forward candidate decisions, 1.25% is the primary lane.

Requested capital = account risk budget / effective stop distance.
- single-name capital cap = 50% equity
- no leverage
- simultaneous requests scaled pro-rata to available cash
- retain both Small and Large scales

## Historical evidence summary
Historical reconstruction only; not prospective evidence.

Top500, 1.25% primary:
- total return +234.05%
- MDD -17.32%
- Sharpe 1.071
- PF 2.004
- baseline rolling 12m positive share 100%
- worst baseline rolling 12m return +6.45%

Top500, 1.50% robustness:
- total return +256.11%
- MDD -17.58%
- Sharpe 1.114
- PF 1.949
- worst baseline rolling 12m +7.68%

Top300:
- 1.25%: +208.02%, MDD -16.04%
- 1.50%: +236.67%, MDD -16.35%

20 bps per-side cost stress remains profitable:
Top500:
- 1.25% +129.92%, MDD -20.40%
- 1.50% +154.32%, MDD -20.35%
Top300:
- 1.25% +124.07%, MDD -16.45%
- 1.50% +152.62%, MDD -16.84%

## Execution-latency diagnosis
V18 unrestricted delayed entries were an invalid stress for the frozen geometry because they allowed execution above Bottom<=20%.

V20 delayed + revalidated Bottom<=20%:
Top500 1.50%:
- +142.44%, MDD -15.91%, PF 2.288
Top300 1.50%:
- +174.68%, MDD -15.73%, PF 2.650

V21 same-cohort analysis shows latency itself is not the dominant cause of risk deterioration.
The candidates that leave Bottom<=20% before delayed execution are historically very strong when entered on time, but that membership is future-defined and MUST NOT be used as a historical selection filter.

## Freeze discipline
From this point:
- do not retune width, age, Bottom<=20%, target60, H20, or primary 1.25% risk using post-freeze data,
- do not add RSI/MACD/gap/retest/confirmation filters to Candidate V1,
- all new post-freeze observations belong to forward OOS,
- any future variant must receive a new candidate/version name and separate preregistration.

## Promotion
Candidate remains research-only until forward OOS evidence is sufficient.
