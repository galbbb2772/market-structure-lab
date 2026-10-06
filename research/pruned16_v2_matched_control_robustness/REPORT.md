# PRUNED16 V2 Matched-Control Robustness

Classification: **ROBUST_POSITIVE**

## Base-feature grid

| Horizon | Positive cells | Min mean lift | Median mean lift | Max mean lift |
|---|---:|---:|---:|---:|
| 5D | 7/9 | -0.1362 pp | +0.1655 pp | +0.8161 pp |
| 10D | 9/9 | +0.5873 pp | +1.1857 pp | +3.0119 pp |
| 20D | 9/9 | +1.7069 pp | +2.7198 pp | +3.4616 pp |

## Grid without Market Score

| Horizon | Positive cells | Min mean lift | Median mean lift | Max mean lift |
|---|---:|---:|---:|---:|
| 5D | 8/9 | -0.1196 pp | +0.1302 pp | +0.3550 pp |
| 10D | 9/9 | +0.8180 pp | +1.4257 pp | +2.0699 pp |
| 20D | 9/9 | +1.8598 pp | +2.8795 pp | +3.2589 pp |

## Center cell K=5 / exclusion=20

- 5D: mean +0.1467 pp; median +1.7374 pp; positive 72.73%; LOO mean range [-0.2499, +1.1176] pp; cluster-weighted +1.6677 pp; equal-year +2.1279 pp.
- 10D: mean +1.1206 pp; median +1.2410 pp; positive 72.73%; LOO mean range [+0.6191, +2.1104] pp; cluster-weighted +1.9003 pp; equal-year +2.6592 pp.
- 20D: mean +2.7198 pp; median +4.2015 pp; positive 63.64%; LOO mean range [+1.4969, +4.3909] pp; cluster-weighted +4.5385 pp; equal-year +6.2905 pp.

## Guardrail

Historical robustness only. No grid cell is selected for production and no Forward-OOS definition is changed.
