# Pure Box Simple Core Early Pyramiding × Single-Name Cap V44

Status: interaction robustness test only. No signal changes.

## Motivation
Two independently observed findings:
1. V43 Early-R250 (holding age <=3 only) improves FULL_R250 in Top500 across 5/10/20bps.
2. Single-name cap frontier shows 60% cap slightly increases raw return vs 50% under FULL_R250, but worsens MDD/Sharpe/rolling stability. 75% and 100% are clearly worse.

V44 tests whether EARLY_R250 can retain any 60% cap upside while repairing its risk-quality deterioration.

## Frozen core
- Strict Wide + Fresh
- Bottom<=20%
- direct next-session open only
- lower stop
- target60
- H15
- repeated signal uses same box/stop/target
- repeated signal does not reset age
- liquidity-first same-day queue
- no leverage

## Fixed policies
A. EARLY_R250_CAP50
- repeat add-on only if existing holding age <=3
- same-symbol total stop risk may reach 2.50%
- single-name capital cap 50%

B. EARLY_R250_CAP60
- exact same rule
- single-name capital cap 60%

Controls:
C. FULL_R250_CAP50
D. FULL_R250_CAP60

No other cap level or risk target may be introduced.

## Robustness matrix
Top300 and Top500.
5, 10, 20 bps/side.

## Decision rule
CAP60 is supported only if, under EARLY_R250:
- return improvement is material in both universes or clearly stronger in Top500,
- MDD remains close to CAP50,
- rolling 12m minimum does not materially deteriorate,
- Sharpe and concentration do not materially worsen,
- 20bps result remains viable.

Do not select CAP60 from raw return alone.
