# PRUNED16 V2 — Surviving Structure After Indicator Pruning

**Date:** 2026-10-06  
**Status:** historical mechanism diagnosis only; no production change.

## 1. Strongest surviving result: relative-state edge, not unconditional alpha

The complete PRUNED16 Sequence has weak unconditional forward returns:

- 10D mean: **+0.485%**
- 10D lift vs unconditional market baseline: **-0.071 pp**
- 20D mean: **+2.273%**
- 20D lift vs unconditional market baseline: **+1.163 pp**

But the matched-control comparison is much more stable.

### Prespecified robustness grid

Across K = {3,5,10} controls and event-exclusion windows = {10,20,30} sessions:

- 10D mean matched lift is positive in **9/9** cells.
- 20D mean matched lift is positive in **9/9** cells.
- 10D grid range: **+0.587 to +3.012 pp**; median **+1.186 pp**.
- 20D grid range: **+1.707 to +3.462 pp**; median **+2.720 pp**.

Removing Market Score from the matching features does not destroy the effect:

- 10D: **9/9 positive**, median **+1.426 pp**.
- 20D: **9/9 positive**, median **+2.880 pp**.

Center configuration K=5 / exclusion=20:

- 10D mean lift: **+1.121 pp**.
- 20D mean lift: **+2.720 pp**.
- Leave-one-event minimum mean lift: **+0.619 pp at 10D**, **+1.497 pp at 20D**.
- 20-session cluster-weighted lift: **+1.900 pp at 10D**, **+4.539 pp at 20D**.
- Equal-year weighted lift: **+2.659 pp at 10D**, **+6.291 pp at 20D**.

Classification: **ROBUST_POSITIVE**, subject to the major sample-size guardrail below.

## 2. The edge is not explained by a single static module

PRUNED16 Stage2 module matched-control results:

### Box-bottom module alone
- 10D matched lift: **-1.345 pp**
- 20D matched lift: **-2.546 pp**

### Breadth-low module alone
- 10D matched lift: **-2.917 pp**
- 20D matched lift: **-2.842 pp**

### Score-recovery module alone
- 10D matched lift: **-0.290 pp**
- 20D matched lift: **-1.219 pp**

### Sentiment-extreme module alone
- 10D matched lift: **+0.292 pp**
- 20D matched lift: **+0.077 pp**

Therefore the complete Sequence edge cannot be attributed to "Box is good", "Breadth low is good", or "Score recovery is good" as independent signals.

## 3. Sequence ablation points to an ordered repair process

Historical sequence stages:

- **S0 DUAL onset:** 10D mean **-0.103%**, 20D **+0.438%**
- **S1 DUAL + Breadth Low:** 10D **-0.608%**, 20D **+0.711%**
- **S2 Low + Box:** 10D **+0.277%**, 20D **+1.989%**
- **S3 Low + Box + Breadth Rebound:** 10D **+0.745%**, 20D **+2.872%**
- **S4 Rebound + Score, without requiring Box:** 10D **-0.845%**, 20D **+1.013%**
- **S5 Full Complete Sequence:** 10D **+0.485%**, 20D **+2.273%**

Interpretation:

1. DUAL stress and Breadth Low are **not entry alpha**. They describe the damaged state.
2. Box context appears to be a **conditioning state**, because removing the Box requirement while keeping rebound+score produces worse outcomes.
3. Breadth rebound is the clearest transition from "damage" toward "repair".
4. Score recovery is better interpreted as **confirmation/timing**, not a standalone alpha source.
5. The useful information is in the **ordered state transition**, not the individual components.

## 4. A more accurate mechanism statement

The surviving PRUNED16 structure is:

> **Stress / liquidity deterioration → broad market weakness → price reaches a constrained/box-like structural location → breadth begins to repair → score confirms repair.**

This does **not** mean every link is causal. The mechanism-graph study explicitly forbids causal claims, and some individual directed links do not beat matched controls.

The defensible statement is narrower:

> The completed transition identifies a market state whose subsequent 10–20D return is historically better than carefully matched states with similar static conditions.

## 5. Why raw Sequence alpha looks weak while matched-control edge survives

PRUNED16 events often occur in difficult market regimes. Their absolute 10D return can be mediocre because the background state itself is poor.

The matched-control study asks a different question:

> "Given a similarly weak / volatile / liquidity-stressed / breadth-poor environment, does the completed repair sequence do better than comparable states that did not complete the same transition?"

Historically, the answer is **yes at 10D and 20D** across the preregistered matching grid.

Thus this is better described as **conditional relative-state alpha** than unconditional market-timing alpha.

## 6. Important negative results that should stay retired

Do not revive these as independent rules:

- Box-bottom alone
- Breadth-low alone
- Market Score recovery alone
- RMD3 as a strong 10D predictor
- DUAL Severity as a calibrated hazard predictor
- simple cross-market confirmation-count gate

These have either negative matched-control evidence or failed to survive PRUNED16.

## 7. Remaining limitation

The complete PRUNED16 Sequence has only:

- **11 historical events**
- **5 effective 20-session clusters**
- **81.8% of events in 2022**

Therefore the matched-control robustness is strong **within the historical sample**, but cannot be promoted to production.

The correct next test is the already-frozen PRUNED16 Forward-OOS ledger from **2026-10-06**.

## Bottom line

After pruning redundant indicators, the most durable Task1/4 finding is no longer RMD3 or a raw Sequence return claim.

It is:

> **A rare, ordered repair transition appears to carry a robust 10–20D relative advantage versus similar static market states, while its individual ingredients do not.**

That is the PRUNED16 V2 mechanism worth carrying forward.
