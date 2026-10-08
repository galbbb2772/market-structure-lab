# Pure Box Simple Core Instrument-Class Attribution V52

Status: mechanism attribution only. No strategy change.

## Objective
Explain the large performance gap observed in V50 between MIXED_UNIVERSE and STOCK_ONLY.

Do not use this study to tune signal thresholds, age, risk ceiling, or cap.

## Frozen capital overlays
- SKIP_OVERLAP
- AGE3_ONLY_R250

## Frozen instrument classes

### LEVERAGED_INVERSE_ETP
NVDL
QID
SDOW
SDS
SPXS
SPXU
SQQQ
SSO
SVXY
TMF
TNA
TZA
UDOW

### CRYPTO_ETP
ETHA
FBTC
GBTC
IBIT

### COMMODITY_VOL_ETP
GDX
GDXJ
SLV
USO
VXX

### THEMATIC_SECTOR_ETF
ARKK
KRE
KWEB
XME

### SINGLE_STOCK
All remaining symbols in the frozen candidate universe.

No class membership may change after results.

## Analysis

For Top500 primary and Top300 robustness:

1. Candidate-level
- candidate event count by instrument class
- unique symbols by class
- liquidity rank distribution by class

2. Independent trade outcomes
Using the frozen H15 / target60 / lower-stop execution:
- n
- mean / median return
- PF
- win rate
by instrument class.

3. AGE3 add-on slices
- add-on n
- funded capital
- mean / median add-on return
- PF
- signed add-on slice PnL
- absolute PnL share
by instrument class.

4. Portfolio ablations at 5bps
Run:
A. ALL
B. EXCLUDE_LEVERAGED_INVERSE
C. EXCLUDE_CRYPTO
D. EXCLUDE_COMMODITY_VOL
E. EXCLUDE_THEMATIC_SECTOR
F. STOCK_ONLY

for both SKIP_OVERLAP and AGE3_ONLY_R250.

Report:
- total return / CAGR / MDD / Sharpe
- rolling 12m minimum
- return delta vs ALL

## Interpretation
The purpose is to determine whether:
- the strategy is fundamentally a single-stock mean-reversion system,
- or the box structure generalizes across highly liquid exchange-traded instruments,
- and which instrument class creates the historical performance gap.

No class exclusion becomes a production rule from V52 alone.
