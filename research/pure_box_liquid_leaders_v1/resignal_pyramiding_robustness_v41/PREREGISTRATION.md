# Pure Box Simple Core Re-Signal Pyramiding Robustness V41

Status: robustness validation only. No parameter tuning.

## Subject
V40 repeated-same-box capital policies:
- SKIP_OVERLAP
- REFILL_TO_R125
- REFILL_TO_R150
- PYRAMID_TO_R250

Primary new finding:
Top500 PYRAMID_TO_R250 historical return +580.76% vs +373.36% baseline.
Top300 PYRAMID_TO_R250 +398.73% vs +239.29% baseline.

## Frozen rules
No changes to:
- Strict Wide + Fresh
- Bottom<=20%
- direct next-session open
- target60 / lower stop / H15
- liquidity-first same-day queue
- 50% single-name capital cap
- repeated signals do not reset age
- repeated signals use same box/stop/target
- R250 means total same-symbol stop risk may be refilled up to 2.50%

## Tests

### A. Full portfolio cost stress
For Top300 and Top500 run all four policies at:
- 5 bps/side
- 10 bps/side
- 20 bps/side

### B. Cross-universe consistency
Compare return, CAGR, MDD, Sharpe, rolling 12m minimum and positive share in Top300 and Top500.

### C. Year attribution
For each cost level calculate annual return delta:
PYRAMID_TO_R250 minus SKIP_OVERLAP.
Report share of positive annual uplift attributable to 2025.

### D. Risk/concentration
Report:
- add-on events
- mean/max post-add position stop risk
- top5/top10 funded PnL concentration
- turnover proxy
- blocked new entries
- average exposure

## Decision rule
R250 is not supported merely because return is highest.
It must:
- remain materially positive versus baseline at 10 and 20 bps in both universes,
- avoid material MDD deterioration,
- retain acceptable rolling stability,
- and not rely almost entirely on one year.
If 2025 dominates the uplift, keep R250 exploratory even if cost-robust.
