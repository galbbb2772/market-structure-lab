# Pure Box Simple Core Single-Name Cap Frontier V43

Status: exploratory risk/capital frontier only. NOT a candidate optimization.

## Context
V42 shows PYRAMID_TO_R250 add-on slices remain positive even excluding 2025:
Top500 ex-2025 mean add-on slice return ~+1.98%, PF ~2.10.
But ~89% of Top500 add-on events are constrained by the frozen 50% single-name capital cap, and realized post-add risk averages only ~1.32% rather than the theoretical 2.50% ceiling.

## Frozen mechanism
- Top500 primary, Top300 robustness
- Strict Wide + Fresh
- Bottom<=20%
- direct next-session open
- lower stop / target60 / H15
- liquidity-first same-day queue
- repeated same-box signals may refill total same-symbol stop risk up to 2.50%
- no leverage
- 5 bps/side baseline

No signal or exit rules change.

## Exploratory cap frontier
At each cap run both SKIP_OVERLAP control and PYRAMID_TO_R250, so cap effects can be separated from pyramiding effects.

Run with single-name capital cap:
- 50% (current reference)
- 60%
- 75%
- 100% (research upper bound, never a recommendation)

## Paired attribution
For each cap report PYRAMID_TO_R250 minus SKIP_OVERLAP return/MDD/Sharpe delta.

## Metrics
- total return / CAGR
- MDD / Sharpe
- rolling 12m min / median / positive share
- yearly returns
- average exposure
- add-on events
- mean/max post-add stop risk
- single-name cap hit count
- blocked/partial new-symbol entries
- top5/top10 funded PnL concentration
- turnover proxy

## Interpretation
This is a risk frontier, not a parameter selection exercise.
Do not promote 60/75/100% based on historical return.
The purpose is to determine whether the 50% cap is a material ceiling and how much incremental return requires how much concentration/drawdown.
