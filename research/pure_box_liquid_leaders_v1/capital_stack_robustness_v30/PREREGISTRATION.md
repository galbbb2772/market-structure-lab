# Pure Box Simple Core Capital Stack Robustness V30

Status: robustness validation only. Signal core frozen.

## Context
V29 produced two universe-specific best historical capital stacks:
- Top300: Exposure-Aware + Low-entry-first + H15
- Top500: Fixed R1.25 + Liquidity-first + H15

These are NOT promoted yet.

## Frozen signal core
Strict Wide + Fresh
Bottom <=20%
direct next-session open
lower-bound stop
target60
H15
5 bps/side
50% single-name cap

## Primary candidates
Top300 candidate:
- Exposure-aware risk: <25% exposure 1.50%, 25%-60% 1.25%, >60% 1.00%
- Low-entry-fraction-first sequential capital queue

Top500 candidate:
- Fixed 1.25% risk
- Liquidity-first sequential capital queue

## Controls
For each universe compare against:
- fixed 1.25% + pro-rata + H15
- exposure-aware + pro-rata + H15
- fixed 1.25% + corresponding priority route

## Robustness tests
1. Year-by-year portfolio returns
2. Rolling 6m and rolling 12m minimum / median / positive-share
3. Leave-one-calendar-year-out trade-level performance
4. Concentration:
   - top 5 symbols absolute PnL share
   - top 10 symbols absolute PnL share
5. Cost stress:
   - 5 bps/side baseline
   - 10 bps/side
   - 20 bps/side
6. One-session execution delay with actual-entry Bottom<=20 revalidation
7. Exposure and blocked-entry path diagnostics

## Decision rule
A capital stack is supported only if:
- advantage is not dependent on a single year,
- remains positive under 20 bps/side,
- delay-revalidated execution remains viable,
- concentration does not worsen materially versus H15 pro-rata,
- rolling stability remains acceptable.

Do not promote solely from historical total return.
