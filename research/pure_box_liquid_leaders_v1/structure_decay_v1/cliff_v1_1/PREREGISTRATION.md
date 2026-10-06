# Structure Decay V1.1 — 3+ Touch Cliff Confound Diagnostic

Status: post-V1 mechanism diagnostic only. No new OOS claim and no production promotion.

## Motivation
Structure Decay V1 did NOT support a simple linear "each additional touch is worse" model:
the validation linear touch-count coefficient was not adverse after age/width control.

However, the preregistered fixed episode bins showed a distinct 3+ episode tail:
0/1/2 episodes behaved differently from 3+ episodes, especially in Fresh and Wide+Fresh sleeves.

V1.1 tests whether this pre-existing 3+ bin effect is merely an age/width/scale artifact.

## Frozen data
Use only the already-produced:
research/pure_box_liquid_leaders_v1/structure_decay_v1/episode_observations.csv.gz

No episode threshold is changed.
- exposed group: touch_episodes >= 3
- reference group: touch_episodes <= 2

## Models
For Top300 and Top500; discovery and validation separately; All/Fresh/Wide+Fresh:

1. Linear return model:
fwd10 ~ I(3plus) + log1p(age_sessions) + box_width_pct + large_box_dummy

2. Linear probability stop model:
I(first_hit20 == stop) ~ I(3plus) + log1p(age_sessions) + box_width_pct + large_box_dummy

These are descriptive controls, not production models.

## Coarsened matched diagnostic
Match 3+ and <=2 observations only within the same:
- scale;
- fixed age band: 0-4, 5-8, 9-12, 13-18, 19+ sessions;
- width quartile defined from 2019-2022 discovery data separately by scale.

Within each cell containing both groups:
- compare mean fwd10;
- compare 20-session stop rate;
- weight each cell by min(N_3plus, N_reference).

## Interpretation
The cliff mechanism is strengthened if validation shows:
- negative controlled 3plus coefficient for fwd10;
- positive controlled 3plus coefficient for stop probability;
- matched fwd10 difference < 0 and matched stop-rate difference > 0;
- similar direction in Top300 and Top500.

This V1.1 cannot promote a production rule because it is a follow-up analysis on already-observed V1 data.
