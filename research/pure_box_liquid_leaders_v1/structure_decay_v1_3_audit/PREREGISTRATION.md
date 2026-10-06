# Structure Decay V1.3 — Cross-Year Boundary Audit

Status: methodology audit of Structure Decay V1/V1.1. No production promotion.

## Why this audit exists
The original yearly source artifacts contain target-year bars only. A box signal in January can have been detected in the prior calendar year, while a December signal can have forward outcomes in the next calendar year. V1 therefore risked:
- undercounting pre-January touch episodes / age;
- censoring December forward 5/10/20-session outcomes;
- treating incomplete 20-session paths as unresolved.

V1.3 repairs calendar-boundary handling before any further interpretation.

## Data handling
For target year Y:
- signal file remains Y only;
- load bars from Y-1, Y, and Y+1 when available;
- use Y-1 history to reconstruct box age and touch episodes;
- use Y+1 data to complete forward outcomes;
- mark history_complete when available symbol history reaches detected_at;
- mark horizon20_complete when a full 20-session post-entry window is available.

2019 may still lack late-2018 bars because no 2018 workflow artifact exists.
2026Q1 naturally has right-censoring after the March-2026 data endpoint.

## Frozen definitions
Touch threshold remains lower + 12% of box width.
Episode definition and 0/1/2/3+ bins remain unchanged.
Fresh / Wide+Fresh thresholds remain discovery-derived.
No threshold is retuned.

## Audit readout
Primary inference uses history_complete observations.
20-session stop/target/MFE/MAE metrics use horizon20_complete observations only.

In addition to the prior linear touch-count model, audit the already-observed 3+ cliff with:
- fwd10 ~ I(3+) + log1p(age) + width + large_box
- stop20 ~ I(3+) + log1p(age) + width + large_box
on complete-history / complete-horizon samples.

If the 3+ effect disappears after this correction, downgrade the Structure Decay finding.
