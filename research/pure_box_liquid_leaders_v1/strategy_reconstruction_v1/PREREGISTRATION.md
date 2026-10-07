# Strategy Reconstruction V1 — Reversion Path & Selling Exhaustion Map

Status: mechanism research only. No production or frozen candidate rule changes.

## Why
The Pure Box mechanical proxy failed its untouched 2026-04-01..2026-10-05 holdout.
This study does not repair that failed candidate.
It reconstructs the underlying thesis:
temporary mispricing -> structural location -> selling exhaustion -> mean reversion.

## Source / sample
- Frozen Pure Box Liquid Leaders V1 yearly artifacts from run 37424716935.
- 2019-01-01 through 2026-03-31.
- Top500 primary; Top300 robustness.
- Existing box geometry and point-in-time liquidity ranks are unchanged.
- Same-symbol/same-date overlap: prefer large, then later detected_at.
- Cross-year bars are used when available.

Development / validation:
- discovery: 2019-2022
- validation: 2023-2026Q1

## Observation set
Use the already-frozen discovery-median Fresh thresholds from Wide+Fresh OOS V1, fixed for the entire study:
- Top300: small age <= 12, large age <= 23
- Top500: small age <= 12, large age <= 24

These thresholds were defined from the 2019-2022 discovery sample before this reconstruction study and are applied unchanged to validation.

Two observation stages are retained:
1. raw_bottom_signal
   - close is in bottom 20% of the existing box.
   - reference entry = next-session open if strictly inside the box.
2. confirmed_no_new_low_green
   - original next-open strictly inside box;
   - next session low >= signal-day low;
   - next session close > next session open;
   - reference entry = following-session open if strictly inside box.

The confirmation stage is descriptive here; it is not re-selected.

## Reversion-path map
For every usable observation, measure fixed box destinations:
- 50% of box
- 60% of box
- 80% of box
- 100% / upper edge

For each destination, report:
- whether target is reached before lower stop;
- first-hit session;
- 10 / 20 / 40-session target-before-stop probability;
- median sessions to target when hit;
- median and mean entry-to-target gross return;
- unresolved fraction at each horizon.

If entry is already at or above a destination, that destination is not eligible for that observation.

Also report:
- 10 / 20 / 40-session MFE as box-progress fraction;
- 10 / 20 / 40-session MAE as entry return;
- scale = small vs large;
- discovery vs validation;
- raw signal vs confirmed stage.

No target is selected as a production exit in V1.

## Selling-exhaustion features
All are causal and known by confirmation-date close.

Primary mechanism features:
1. low_progress_box
   = (confirmation_low - signal_low) / box_width
   Hypothesis: higher is better; sellers failed to push price lower.

2. rebound_from_low_box
   = (confirmation_close - min(signal_low, confirmation_low)) / box_width
   Hypothesis: higher is better; stronger rejection from the low.

3. range_ratio
   = confirmation_day_range / signal_day_range
   Hypothesis: lower can indicate contraction of the sell impulse.

Secondary diagnostics:
4. confirmation_clv
   = (confirmation_close - confirmation_low) / confirmation_range
   Hypothesis: higher is better.

5. volume_ratio20
   = confirmation volume / prior-20-session median volume.
   Direction is diagnostic only; no hypothesis is promoted.

6. selloff_5d
   = signal close / close five sessions earlier - 1.
   Direction is diagnostic only; distinguishes mild pullback from deep short-term mispricing.

## Exhaustion validation
For each scale separately:
- discovery defines quintile boundaries for each continuous feature;
- apply those fixed boundaries to validation;
- report validation N, mean 10d return, mean max box progress at 20d,
  60%-target-before-stop rate, upper-target-before-stop rate, and stop-first rate;
- Spearman relationship in discovery and validation;
- do not choose a cutoff from V1.

Primary mechanism support requires the hypothesized direction to be broadly similar in
Top300 and Top500 and to survive into validation. Monotonicity is preferred but not required.

## Guardrails
- No new entry rule, target, stop, breadth gate, touch filter, score weight, or position size may be selected from V1.
- The failed 2026-04..10 holdout is not reused as validation for this study.
- Any attractive path target or exhaustion cutoff requires a separately preregistered test.
