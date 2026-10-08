# Pure Box Simple Core Replacement Fragility V38

Status: post-hoc fragility diagnosis only. No rule changes.

Subject:
- Top500
- AGE10_STALE_REPLACE overlay from V35-V37
- 9 historical replacement events
- 8 paired counterfactual events

Purpose:
Quantify whether the apparent benefit is dominated by one or two replacement events.

Required:
- signed sum of pair deltas
- top1 / top2 / top3 signed contribution share
- leave-one-event-out mean pair delta for every paired event
- leave-top1-out / leave-top2-out / leave-top3-out mean pair delta
- positive pair share
- year contribution split

Interpretation:
This study cannot promote or retune the rule.
If contribution is highly concentrated, keep AGE10_STALE_REPLACE as exploratory shadow even if average pair delta is positive.
