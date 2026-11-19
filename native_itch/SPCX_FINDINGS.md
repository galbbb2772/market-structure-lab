# SPCX Native TotalView Findings — 2026-06-12

Status: **PARTIAL_L3 / mechanism replication, not predictive validation**

## Source

- Nasdaq public Historical TotalView-ITCH 5.0 sample: `S061226-v50.txt.gz`
- Native XNAS order lifecycle + NOII.
- Benchmark comparison: BMLL 13-venue/SIP analysis of SPCX first day.

## Auction / NOII — PASS

Native IPO Cross:

- Time: 11:46:45.910363820 ET
- Cross price: **$150.00**
- Cross shares: **58,206,084**
- Stock locate: **10536**
- IPO/Halt NOII records: **7,005**

Selected NOII path:

| ET | Paired | Imbalance | Side | Near | Imbalance / Paired |
|---|---:|---:|---|---:|---:|
| 09:50:00 | 7,343,573 | 191,773 | Sell | 162 | 2.61% |
| 10:00:00 | 12,168,741 | 2,300,978 | Buy | 175 | 18.91% |
| 11:30:00 | 42,024,154 | 832,505 | Buy | 155 | 1.98% |
| 11:32:29 | 44,245,752 | 10,087,066 | Buy | 150 | 22.80% |
| 11:35:01 | 45,349,501 | 10,314,934 | Buy | 150 | 22.75% |
| 11:46:45 | 58,206,084 | 4,640,510 | Buy | 150 | **7.97%** |

Key observations:

- Paired quantity grew roughly **7.93x** from the first IPO NOII snapshot to the cross.
- Near price reached **$175** before falling to the $150 cross as additional interest entered.
- The first $150 near-price snapshot still had ~**10.09M** unmatched buy imbalance (~22.8% of paired).
- The final pre-cross state still had **4.64M** unmatched buy imbalance (~7.97% of paired).

Interpretation: residual demand remained at the final clearing price. The NOII time series alone does **not** separately identify shifts in supply vs demand curves, so this is not a causal elasticity estimate yet.

## Auction-cleanup contamination — identified

The original continuous-flow replay falsely classified a large post-cross block as aggressive selling/buying.

Root cause:

- Native ITCH `C` = Order Executed With Price.
- Correct layout: offset 31 = Printable; execution price starts at offset 32.
- Immediately after the IPO Cross, pre-cross orders were released through non-printable `C` executions at exactly **$150**.
- They persisted for ~**680 ms** after the Cross.

Identified cleanup quantity:

- Passive bid-side cleanup: **36,876,612 shares**
- Passive ask-side cleanup: **5,576,662 shares**
- Total identified cleanup: **42,453,274 shares**

These messages must update the order book but must **not** be interpreted as continuous aggressive flow.

Frozen cleanup rule:

`C + Printable=N + execution price=IPO cross price + pre-cross order + <=1s after IPO cross`

Burst/recovery analysis starts at **11:46:47 ET**, after the cleanup interval.

## XNAS-only Recovery — preliminary replication

Important: this is **XNAS-only** displayed depth around the **XNAS local midpoint**. BMLL uses displayed depth across 13 lit venues around the **SIP midpoint**, so absolute depth levels are not directly comparable.

Burst proxy:

- 1-second classified XNAS flow
- >98th percentile absolute signed notional proxy
- >=70% directional purity
- 120-second non-max suppression
- Selected: **28 buy bursts / 42 sell bursts**

### Frozen baseline: median depth from t-60s to t-10s

| Horizon | Ask recovery after BUY | Bid recovery after SELL | Ask/Bid ratio |
|---|---:|---:|---:|
| 10s | 55.1% | 45.0% | 1.22 |
| 60s | 50.8% | 67.1% | **0.76** |
| 300s | **41.5%** | **73.5%** | **0.56** |

### Sensitivity baseline: median depth from t-60s to t-1s

| Horizon | Ask recovery after BUY | Bid recovery after SELL | Ask/Bid ratio |
|---|---:|---:|---:|
| 10s | 37.9% | 45.3% | 0.84 |
| 60s | 43.3% | 62.7% | **0.69** |
| 300s | **29.4%** | **69.4%** | **0.42** |

BMLL cross-venue/SIP benchmark:

- 10s: ask 44.1%, bid 70.5%
- 300s: ask 36.4%, bid 81.9%
- 300s LRA ~= 0.44

## Current conclusion

The **5-minute persistent asymmetry is robust to baseline choice** in the XNAS-native replay:

`AskRecovery_300 < BidRecovery_300`

and the resulting XNAS-only 5-minute LRA is roughly **0.42–0.56**, directionally close to BMLL's cross-venue ~0.44.

The **10-second result is not robust** in XNAS-only data and must not be treated as confirmed.

Therefore:

- Liquidity Recovery status remains **SHADOW**.
- Evidence is upgraded from “published case evidence only” to **native one-case mechanism replication**.
- This is **not** OOS predictive evidence.
- The next valid test requires independent IPO cases; no threshold should be tuned to make SPCX fit better.

## Data limitation

BMLL's near-mid metric uses consolidated SIP midpoint and displayed depth across 13 venues. XNAS local-midpoint depth can include orders that would fall outside a 20bp SIP-midpoint band, especially during the opening. Therefore absolute XNAS depth must not be benchmarked directly against BMLL's $527k/$726k consolidated figures without SIP/NBBO alignment.
