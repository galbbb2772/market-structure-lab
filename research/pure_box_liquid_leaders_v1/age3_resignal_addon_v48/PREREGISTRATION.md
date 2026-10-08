# Pure Box Simple Core Age-3 Re-Signal Add-On V48

Status: robustness experiment derived from V46 anatomy. No signal changes.

## Motivation
V46 Top500 anatomy:
- age2 add-ons: n=38, mean slice return ~+1.81%, PF ~1.98
- age3 add-ons: n=15, mean slice return ~+23.4%, PF ~23.6

The age3 result is much stronger but sample size is small and may be concentrated.
This study tests the simplest fixed temporal restriction without adding any price-state filter.

## Frozen core
- Top500 primary, Top300 robustness
- Strict Wide + Fresh
- Bottom<=20%
- first eligible next-session open only
- initial stop risk 1.25%
- H15 / target60 / same lower stop
- liquidity-first capital queue
- 50% single-name cap
- no leverage
- repeated same-box observations do not reset age / stop / target
- total same-symbol stop-risk ceiling 2.50%

## Policies
A. SKIP_OVERLAP
No add-ons.

B. EARLY_R250
Current V2 historical rule:
- add-on allowed at holding age <=3

C. AGE3_ONLY_R250
- add-on allowed only when existing holding age ==3
- all other repeated observations are ignored

D. AGE2_ONLY_R250
- diagnostic control
- add-on allowed only when existing holding age ==2

No other rule changes.

## Robustness matrix
Top300 and Top500.
5, 10, 20 bps/side.

## Required metrics
- total return / CAGR / MDD / Sharpe
- rolling 12m min / median / positive share
- yearly returns
- add-on count / capital
- blocked / partial new entries
- top5 / top10 funded PnL concentration
- average exposure
- PF / mean trade

## Decision rule
AGE3_ONLY_R250 is interesting only if:
- it improves or closely preserves EARLY_R250 return while improving risk-adjusted quality,
- remains directionally useful at 20bps,
- does not rely entirely on one year,
- and produces a coherent result in both universes.

Do not introduce further age thresholds after results.
