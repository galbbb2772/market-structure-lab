# Pure Box Simple Core Instrument Purity V50 Stage 2

Status: preregistered robustness audit. No signal retuning.

## Motivation
V49 showed AGE3_ONLY_R250 add-on PnL is highly concentrated, with SPXU the largest historical contributor.
V50 Stage 1 confirmed the candidate universe contains ordinary stocks mixed with ETFs, leveraged/inverse ETFs, commodity funds, volatility products, and crypto funds.

The core research question is whether the capital overlay survives on ordinary single-name equities.

## Frozen signal/capital logic
No rule changes:
- Strict Wide + Fresh
- Bottom<=20%
- first eligible next-session open
- lower stop / target60 / H15
- initial risk 1.25%
- 50% single-name cap
- no leverage
- liquidity-first same-day capital queue

Capital overlays tested:
1. SKIP_OVERLAP
2. EARLY_R250
3. AGE3_ONLY_R250

## Instrument-purity exclusion set
The following are treated as non-single-stock instruments and excluded in STOCK_ONLY lanes:

ARKK
ETHA
FBTC
GBTC
GDX
GDXJ
IBIT
KRE
KWEB
NVDL
QID
SDOW
SDS
SLV
SPXS
SPXU
SQQQ
SSO
SVXY
TMF
TNA
TZA
UDOW
USO
VXX
XME

These are excluded because they are ETFs / ETPs / leveraged or inverse products / commodity, volatility, crypto, or thematic funds rather than ordinary operating-company common stocks.

No symbols may be added or removed after seeing Stage 2 results.

## Comparison lanes
For Top500 primary and Top300 robustness:
A. MIXED_UNIVERSE — current historical universe
B. STOCK_ONLY — same candidate stream after excluding the frozen non-stock list

Important:
- retain the original historical liquidity ranks from the source data.
- do NOT compress or re-rank after exclusions.
This isolates instrument purity from a separate liquidity-universe redesign.

## Costs
Run all lanes at:
- 5 bps/side
- 10 bps/side
- 20 bps/side

## Required outputs
For each universe/policy/cost:
- total return / CAGR / MDD / Sharpe
- rolling 12m min / median / positive share
- yearly returns
- completed trades
- add-on count / add-on capital
- blocked / partial new entries
- top5 / top10 funded PnL concentration

Also report:
- excluded candidate event count
- excluded add-on event count
- excluded symbols actually used by each policy
- return delta STOCK_ONLY minus MIXED
- MDD / Sharpe / rolling-min deltas

## Decision rule
AGE3_ONLY_R250 is considered structurally supported only if STOCK_ONLY:
- remains materially above SKIP_OVERLAP,
- remains viable at 10/20 bps,
- retains acceptable rolling stability,
- and its advantage is not eliminated once ETF/ETP instruments are removed.

Do not retune age, risk ceiling, cap, or instrument list after results.
