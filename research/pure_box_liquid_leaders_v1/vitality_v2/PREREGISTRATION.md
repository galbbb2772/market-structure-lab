# Pure Box Vitality V2 — Width × Freshness Walk-Forward

Research-only. No external factor is added.

## Hypothesis
The prior geometry study suggested that pure box edge is related to box "vitality":
- wider boxes tend to have stronger expectancy;
- newer/fresher boxes tend to have stronger expectancy;
- extreme theoretical R/R by itself was not robust.

This study tests whether width and age interact and whether the relation survives walk-forward evaluation.

## Frozen inputs
Same causal liquid-leader universe and box definitions as Pure Box Liquid Leaders V1.
Primary universe: Top500 by prior ADV20. Top300 retained as robustness.
Entry/exit mechanics remain baseline:
- long only;
- next-session open;
- stop at box lower;
- take profit at box upper;
- same-day stop+target -> stop first;
- 5 bps each side;
- small requested weight 50%, large 100%.

## Tests

### 1) Discovery-frozen 5x5 grid
Use 2019-2022 only to define quintile cut points separately for small and large boxes:
- width quintile 1..5;
- age quintile 1..5.

Apply those fixed cut points to 2023-2026Q1 opportunities.
Report each width×age cell:
- N
- mean / median trade return
- PF
- win rate
- target rate
- average hold

This directly tests whether "wide + fresh" is an interaction rather than two unrelated marginal effects.

### 2) Annual walk-forward
For each test year 2021..2026:
- build width and age medians / 80th / 20th percentiles using all prior years only;
- freeze thresholds before the test year;
- test baseline, fresh-only, wide-only, wide+fresh, strict wide+fresh in that year.

Aggregate yearly walk-forward equity by compounding yearly returns.
No test-year data is allowed in threshold formation.

### 3) Vitality score ranking
Within each scale, compute discovery-period percentile transforms:
- width_score = percentile(width)
- fresh_score = 1 - percentile(age)
- vitality_score = 0.5*width_score + 0.5*fresh_score

For validation only, map each candidate using the frozen discovery empirical distributions.
Compare opportunity quintiles by vitality score and a same-day priority portfolio that ranks higher vitality first.

This is a ranking sensitivity study, not a production rule.

## Decision standard
Call the box-vitality hypothesis materially supported only if:
- the favorable width×age corner is stronger in validation;
- fresh/wide-fresh improves multiple walk-forward years, not one year only;
- direction holds in Top300 and Top500;
- improvements are not solely due to dramatically lower exposure.
