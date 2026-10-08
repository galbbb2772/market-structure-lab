# Pure Box Simple Core Stale Replacement Robustness V36

Status: robustness validation only. Signal core frozen.

## Candidate under test
Top500 capital candidate baseline:
- H15
- fixed 1.25% risk
- liquidity-first sequential funding
- direct next-session open only
- Bottom<=20%
- 50% single-name cap
- no leverage

Exploratory V35 overlay:
- when a new liquidity-superior signal is cash-constrained,
- only holdings aged >=10 sessions may be displaced,
- holding must have current-open progress toward target <25%,
- displace worst liquidity rank first,
- new signal must have strictly better liquidity rank.

V35 historical result:
- baseline +373.36%
- AGE10_STALE_REPLACE +380.24%
This is NOT promoted yet.

## Tests

### A. Cost robustness
Run full portfolio at:
- 5 bps/side
- 10 bps/side
- 20 bps/side

Compare NO_DISPLACEMENT vs AGE10_STALE_REPLACE.

### B. Cross-universe robustness
Run the exact same rules on:
- Top500
- Top300
No threshold changes.

### C. Temporal attribution (stage 2 only if A/B pass)
Report yearly returns and replacement counts by year.

### D. Replacement anatomy (stage 2 only if A/B pass)
For every replacement:
- date
- displaced symbol
- displaced holding age
- displaced realized return
- displaced progress toward target
- incoming symbol
- incoming liquidity rank
- displaced liquidity rank
- capital released

Report:
- mean/median displaced return
- positive displaced share
- mean age
- mean progress
- replacement count

## Decision rule
The overlay is supported only if:
- Top500 remains directionally better than baseline under 10 and 20 bps,
- it does not materially worsen MDD/rolling stability,
- the benefit is not entirely one calendar year,
- Top300 is at least non-destructive or provides a coherent explanation if different,
- replacement count is sufficient to interpret cautiously.

No tuning of age10 or 25% after results.
