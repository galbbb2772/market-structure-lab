# Pure Box Simple Core Capital Architecture V22

Status: capital-layer research only. Signal logic frozen.

## Frozen signal core
Strict Wide + Fresh
Bottom <= 20%
direct next-session open
target60
lower-bound stop
H20
Top300 and Top500 both evaluated
5 bps/side baseline costs

No signal filter changes are allowed in V22.

## Questions

### A. Capital occupancy efficiency
Measure:
- fraction of eligible entries blocked or scaled by insufficient cash
- fraction of time cash is idle
- average / median gross exposure
- concurrent-position distribution
- missed requested risk because of capital cap/cash constraint
- marginal PnL of signals arriving when portfolio is already highly invested

### B. Dynamic risk-budget utilization
Do NOT optimize a continuous parameter.
Compare only preregistered discrete policies:

1. FIXED_R125
2. FIXED_R150
3. EXPOSURE_AWARE:
   - base 1.25%
   - if opening exposure <25%, request 1.50%
   - if opening exposure >60%, request 1.00%
   - otherwise 1.25%
4. SIGNAL_DENSITY_AWARE:
   - base 1.25%
   - if today's eligible signal count <=1, request 1.50%
   - if >=4, request 1.00%
   - otherwise 1.25%

Single-name capital cap remains 50%, no leverage.

### C. Exit capital recycling
Compare frozen entry cohort under:
1. H20 anchor
2. H15
3. H10
4. EARLY_STALE_EXIT:
   - exit at close on day 10 if trade has not reached +10% of box progress from entry toward target
   - otherwise retain H20

Targets and stops unchanged.
This is capital-recycling research, not a signal filter.

## Primary metrics
- total return / CAGR / MDD / Sharpe
- average exposure
- cash idle share
- completed trades
- PF / mean trade
- capital-turnover proxy
- blocked/scaled entry count
- requested risk vs realized planned risk
- equity contribution from entries made at high opening exposure
- yearly returns
- rolling 12m minimum / positive share

## Decision philosophy
Prefer a capital rule only if it improves return or capital efficiency WITHOUT materially worsening drawdown, rolling stability, or cross-universe consistency.
Do not select a rule based only on maximum historical total return.
