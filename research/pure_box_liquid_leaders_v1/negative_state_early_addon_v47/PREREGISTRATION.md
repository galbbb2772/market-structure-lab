# Pure Box Simple Core Negative-State Early Add-On V47

Status: robustness experiment derived from V46 anatomy. No signal changes.

## Motivation
V46 found a coherent path-state split for Top500 EARLY_R250:
- existing position NEGATIVE_OR_FLAT at add-on open:
  n=39, mean add-on slice return ~+10.5%, PF ~9.24
- existing position POSITIVE:
  n=14, mean ~+0.7%, PF ~1.27, aggregate slice PnL slightly negative

This suggests repeated same-box observations may be most informative when the original position has not yet repaired above its entry.

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
- repeated same-box signal only at existing holding age <=3
- repeat signal does not reset age / stop / target

## Policies
A. SKIP_OVERLAP
No repeat-signal add-ons.

B. EARLY_R250
Current Capital Candidate V2 historical rule:
- age <=3
- total same-symbol stop risk may rise to 2.50%

C. NEGATIVE_STATE_R250
Same as EARLY_R250, but add-on is allowed only when:
- current add-on open <= original position entry price

No other path variable is used.
No age/risk/cap/target changes.

## Robustness matrix
Run unchanged on:
- Top300
- Top500
and at:
- 5 bps/side
- 10 bps/side
- 20 bps/side

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
NEGATIVE_STATE_R250 is interesting only if, versus EARLY_R250:
- it preserves or improves return OR materially improves risk-adjusted quality,
- does not materially worsen MDD,
- remains directionally useful under 20bps,
- result is coherent in Top300 and Top500.

Do not introduce further path-state thresholds after results.
