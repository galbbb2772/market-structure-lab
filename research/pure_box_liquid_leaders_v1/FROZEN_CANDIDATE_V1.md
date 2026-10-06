# Pure Box Frozen Candidate V1

Freeze date: 2026-10-06

This file is the research-repo mirror of the frozen candidate now being evaluated in `galbbb2772/frozen-v4`.

## Frozen primary chain

```text
Top500 prior-20 ADV liquid-leader proxy
→ Fresh box only
   small age <= 13
   large age <= 28
→ signal close in lower 20% of active box
→ no_new_low_green confirmation
   next-session low >= signal-day low
   next-session close > next-session open
→ enter following session open
→ same-day Width + Freshness Borda capital ranking
→ 33% maximum initial single-symbol equity weight
→ box lower stop / box upper target
→ 5 bps per side
```

No hard Breadth gate.
No hard 3+ touch filter.
No post-entry adding, reducing or rebalancing.
No leverage.

## Why this variant was frozen
Across Position Sizing V2 at the 33% cap:

- Top300 Fresh + no_new_low_green + width_age_borda:
  compounded annual walk-forward return about +100.9%.
- Top500 Fresh + no_new_low_green + width_age_borda:
  compounded annual walk-forward return about +97.0%.

The alternative Fresh + hold_then_enter + width_age_borda did not replicate in Top500 and was not selected.

## Evidence boundary
All research used for selection ends with the historical source at 2026-03-31.

The first frozen holdout is:
2026-04-01 through 2026-10-05.

This period is labeled UNTOUCHED_POST_SOURCE_HOLDOUT, not true live forward, because the formal candidate freeze occurred on 2026-10-06.

True append-only forward evidence starts after the 2026-10-06 freeze and is maintained in:
`galbbb2772/frozen-v4/research/pure_box_candidate_v1/forward/`

Pre-freeze forward anchor:
2026-10-05, equity 1.0, no positions, no pending events, no historical P&L.

## No-retuning rule
Do not modify:
- Fresh ages
- confirmation rule
- width/age ranking
- 33% cap
- stop/target
- costs
based on the 2026-04..10 holdout.

Any future challenger must receive a new version and a new evidence boundary.
