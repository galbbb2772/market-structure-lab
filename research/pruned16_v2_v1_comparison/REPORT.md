# Task1/4 V1 vs PRUNED16 V2 — Conclusion Reassessment

**Date:** 2026-10-06  
**Scope:** Historical diagnostic comparison only. No production change.  
**V1:** legacy Market Score with 19 directional Active indicators.  
**V2:** PRUNED16 Market Score with 16 directional Active indicators.

## 1. Event identity changed

V1 had 12 complete Sequence events. PRUNED16 V2 has 11.

Changes:

- `2022-01-26` shifts to **2022-01-28** under PRUNED16.
- `2022-03-09` disappears from the complete Sequence set.
- The remaining 10 historical event dates are unchanged.

Therefore V2 is not just a cosmetic rescoring of the same event sample. It is a new research lineage and must not overwrite V1.

## 2. Sequence forward return evidence weakens materially

| Metric | V1 | PRUNED16 V2 | Change |
|---|---:|---:|---:|
| Event count | 12 | 11 | -1 |
| Mean 5D return | +0.787% | +0.330% | weaker |
| Mean 10D return | +1.271% | +0.485% | much weaker |
| 10D lift vs unconditional baseline | +0.715 pp | -0.071 pp | sign flips |
| 20-session cluster-weighted 10D mean | +2.475% | +0.986% | weaker |
| Cluster-weighted 10D 95% CI | [0.774, 4.144] | [-0.187, 2.629] | loses positive lower bound |

Interpretation: the raw "complete Sequence -> 5-10D rebound" conclusion is substantially less convincing under the cleaner PRUNED16 score.

## 3. Matched-control evidence survives better than raw-event evidence

| Horizon | V1 mean matched lift | V2 mean matched lift |
|---|---:|---:|
| 5D | +0.0755 pp | +0.1467 pp |
| 10D | +1.3801 pp | +1.1206 pp |
| 20D | +2.0569 pp | +2.7198 pp |

The V2 10D matched-control lift remains positive and 72.7% of events have positive 10D lift. The 20D matched-control lift is actually larger.

Interpretation: **the event itself is not a strong unconditional timing signal, but it may still identify a state that performs better than similar background states.** This is a more defensible formulation than the old "Sequence has strong 10D alpha" wording.

## 4. RMD3 historical evidence collapses

### V1
- RMD3 vs 10D Spearman: **0.720**
- permutation p: **0.0103**
- 20-session cluster-level rho: **0.829**
- leave-one-out median rho: **0.714**

### PRUNED16 V2
- RMD3 vs 10D Spearman: **0.300**
- permutation p: **0.3706**
- 20-session cluster-level rho: **-0.300**
- leave-one-out median rho: **0.285**

The former strong historical RMD3 result does **not** survive PRUNED16.

**Revised status:** downgrade RMD3 from "historically strong Shadow candidate" to **WEAKENED / Forward-OOS watch only**. Do not use the old V1 historical strength as promotion evidence.

## 5. D+1 survives partially, but is weaker

### 10D
- V1 mean improvement: **+1.559 pp**
- V2 mean improvement: **+1.444 pp**
- V1 sign-flip p: **0.0400**
- V2 sign-flip p: **0.0830**
- V2 bootstrap 95% CI: **[+0.056, +2.856] pp**

### 20D
- V1 mean improvement: **+1.241 pp**, sign-flip p **0.0063**
- V2 mean improvement: **+0.720 pp**, sign-flip p **0.2324**

After retrospective multiple-testing correction, V2 D+1 no longer survives as a strong confirmatory result.

**Revised status:** D+1 remains the most credible timing challenger of the old Task1/4 set, but should be labeled **historical weak/moderate evidence; Forward-OOS required**, not "validated."

## 6. DUAL Severity loses its historical calibration advantage

The Stage3 hazard calibration changes materially:

### V1 Brier
- base: **0.2582**
- severity: **0.1880**
- RMD: **0.2585**
- 2D model: **0.2286**

### V2 Brier
- base: **0.2342**
- severity: **0.2346**
- RMD: **0.2631**
- 2D model: **0.2805**

Under V1, severity clearly beat the base-rate model. Under V2, it no longer does.

**Revised status:** DUAL Severity should be downgraded from "historically useful re-breakdown hazard" to **descriptive / Forward-OOS watch only**.

## 7. Event independence remains a serious limitation

V1:
- 12 events
- 6 effective 20-session clusters
- 83.3% of events in 2022

V2:
- 11 events
- 5 effective 20-session clusters
- 81.8% of events in 2022

The V2 sample is slightly less redundant in raw count, but the effective independent-regime sample is actually smaller.

This makes all historical p-values and rank correlations fragile.

## 8. Cross-market confirmation conclusion is unchanged

V2 still does not show a monotonic relationship where "more confirming markets" reliably means better outcomes.

- 0-2 confirmations: 10D mean +0.965%
- 3+ confirmations: 10D mean -0.092%
- 4+ confirmations: 10D mean +1.490%

The non-monotonicity remains. Do not create a simple confirmation-count gate.

## 9. Revised Task1/4 conclusion library

### Keep
- **Matched-control state edge:** survives, especially 10D/20D.
- **D+1:** still worth prospective monitoring, but evidence is weaker.
- **Sequence mechanism / state-transition interpretation:** keep as descriptive research structure.
- **Cross-market confirmation:** keep conclusion that simple count gating is not justified.

### Downgrade
- **RMD3:** strong historical V1 finding does not survive PRUNED16.
- **DUAL Severity:** historical hazard advantage disappears under PRUNED16.
- **Raw complete-Sequence 10D rebound:** substantially weaker; no longer a strong standalone historical alpha claim.

### Still blocked by Forward OOS
- RMD3
- D+1
- DUAL Severity
- Early Sequence
- RMD2 Price+Score

All new PRUNED16 Forward-OOS ledgers are frozen from **2026-10-06** and currently contain zero future events.

## Bottom line

PRUNED16 made the Task1/4 research **less spectacular but more trustworthy**.

The strongest old conclusions were partly dependent on the old 19-indicator score definition. After pruning redundant indicators:

- the unconditional Sequence alpha weakens,
- RMD3 loses most of its historical support,
- DUAL Severity loses its calibration edge,
- D+1 remains interesting but no longer looks confirmatory,
- matched-control 10D/20D relative-state edge is the most persistent result.

This is exactly why the indicator pruning and full downstream rebaseline were necessary.
