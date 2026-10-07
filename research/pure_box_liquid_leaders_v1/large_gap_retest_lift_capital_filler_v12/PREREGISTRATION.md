# Large Gap Retest-Lift Capital Filler V12

Status: research-only portfolio expansion. V7 signal/state thresholds remain frozen.

## Goal
Increase capital utilization without changing the frozen RETEST_LIFT definition.

## Frozen core
Primary core remains:
- Top500
- EXPANDING extreme-gap
- Large Fresh
- 60% box target primary / 80% robustness
- lower stop
- max hold 20 sessions
- 5 bps each side
- stop-first
- 20% requested allocation per event as the V11 risk-efficient reference

## Fixed state families
No new thresholds are created.

States are the original V7 states:
- RETEST_LIFT (RL)
- RETEST_WEAK_LIFT (RWL)
- NO_RETEST_LIFT (NRL)
- NO_RETEST_WEAK_LIFT (NRWL)

Tested lanes:
1. RL_ONLY
   - frozen core only.
2. RETEST_POOL
   - RL + RWL, same-day entries treated equally.
3. RL_PRIORITY_RWL_FILLER
   - RL requests are allocated first.
   - RWL is allowed only with cash left after all RL requests on that day.
   - RWL can never displace an RL entry.
4. LIFT_POOL_CONTROL
   - RL + NRL, diagnostic only.
5. EXTREME_ALL_CONTROL
   - all four V7 states, diagnostic only.

## Primary success condition
RL_PRIORITY_RWL_FILLER is interesting only if, versus RL_ONLY at the same sizing:
- total return increases,
- average exposure increases materially,
- max drawdown remains better than -20%,
- Sharpe remains >= 90% of RL_ONLY,
- RL realized trade count is not reduced.

No automatic strategy promotion.