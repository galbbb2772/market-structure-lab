# Pure Box Long — Liquid Leaders V1

Research-only. This line tests the user's existing box strategy on a broad daily U.S. market universe rather than the small ETF pilot.

## What is frozen
The alpha rule is unchanged from Pure Box Long V1:
- long only;
- existing Structure Lab V1 box geometry: small = 20 sessions / max 14% width, large = 60 sessions / max 28% width, at least two touches on each side, 2% close-break tolerance;
- a newly detected box is usable only for the following session;
- signal when signal-close is inside the bottom 20% of the active box;
- if both scales qualify, large box wins;
- entry next U.S. session open;
- stop = box lower edge;
- take profit = box upper edge;
- same-day stop+target ambiguity = stop first;
- small requested weight 50%, large requested weight 100%;
- 5 bps per side;
- no RSI, MA, sentiment, regime, trend, volume-ratio, sector, earnings or other alpha filter.

## Dynamic liquid-leader universe
The OHLCV source has ticker + price/volume but no point-in-time market-cap or industry master. Therefore this version must NOT be described as an exact historical "industry leaders" universe.

Daily eligibility is a causal liquidity/large-name proxy:
- simple U.S. ticker: ^[A-Z]{1,5}$;
- signal close >= $5;
- prior-20-session average dollar volume >= $25m;
- rank by prior-20-session average dollar volume, highest first.

Three frozen breadth lanes:
- Top 200;
- **Top 300 primary**;
- Top 500.

Ranking uses only sessions completed before the signal session (ADV20 is shifted one day). Current/future membership is never backfilled into history.

## Data
Monthly source: mito0o852/OHLCV-1m on Hugging Face, regular-session minutes only (America/New_York 09:30-16:00). Current available endpoint used by this research ends at 2026-03.

Each year is built independently with prior-Q4 warmup, then yearly artifacts are combined. Raw minute files and derived full-market bars are artifacts only and are not committed.

## Portfolio plumbing
When multiple entries compete for cash at one open, requested weights are scaled proportionally to remaining cash so total invested capital cannot exceed 100%. This is not an alpha ranking rule.

## Outputs
For Top200/300/500: total return, CAGR, max drawdown, daily Sharpe, average exposure, trade count, win rate, mean/median trade return, profit factor, average hold, exit reasons, small/large breakdown, rejected entries, yearly returns, and a primary Top300 trade/equity ledger.

## Interpretation
This is a broad-market liquidity-leader proxy. A later point-in-time security master + historical market-cap/industry classification is required before calling the universe exact "large-cap industry leaders".
