# Pure Box Simple Core Early Re-Signal Pyramiding V43

Status: post-anatomy robustness experiment only. No signal changes.

## Motivation
V42 shows the historical add-on edge is concentrated in very early repeated same-box observations:
- Top500 age 1-3 add-ons: n=54, PF ~5.98, positive slice PnL
- age 4-5: weak
- age 6-10: negative
The full R250 overlay is also strongly 2025-dependent and concentrated.

V43 tests one simple causal restriction derived from that anatomy:
only repeated same-box signals observed while existing holding age <=3 may add capital.

This is exploratory and must NOT replace the frozen Capital Candidate V1 without new forward OOS.

## Frozen signal/execution core
- Strict Wide + Fresh
- Bottom<=20%
- direct next-session open only
- lower stop
- target60
- H15
- same box / stop / target for re-signals
- re-signals do not reset holding age
- liquidity-first same-day queue
- 50% single-name cap
- no leverage

## Policies
A. SKIP_OVERLAP
B. FULL_R250
- existing V40 PYRAMID_TO_R250, all valid repeat ages
C. EARLY_R150
- only if existing holding age <=3
- total same-symbol stop risk may be refilled up to 1.50%
D. EARLY_R250
- only if existing holding age <=3
- total same-symbol stop risk may be refilled up to 2.50%

No other age cutoff or risk target may be introduced after results.

## Robustness matrix
Top300 and Top500.
5, 10, 20 bps/side.

## Metrics
- total return / CAGR / MDD / Sharpe
- rolling 12m min / median / positive share
- yearly returns
- add-on count / capital
- blocked new entries
- average / max post-add position risk
- top5 / top10 funded PnL concentration
- turnover proxy

## Decision rule
EARLY_R250 is interesting only if it retains most of FULL_R250's return gain while improving at least two of:
- Sharpe
- rolling 12m minimum
- concentration
- blocked new entries
and remains directionally superior under 20bps in both universes.

Do not choose based on raw return alone.
