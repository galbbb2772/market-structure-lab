# Simple Core Capital Candidate V2 Forward OOS Preregistration

Status: FORWARD_OOS_PENDING

## Frozen candidate
Use SIMPLE-CORE-CAPITAL-CANDIDATE-V2 exactly as documented in FROZEN_CANDIDATE_V2.md.

## Primary lane
Top500 / fixed 1.25% risk / H15 / Liquidity-First queue.

## Observation rules
- append-only
- no broker execution
- no post-freeze retuning
- first eligible next-session-open only
- actual entry must remain Bottom<=20
- if missed, skip; no delayed chase
- log requested capital, funded capital, queue position, blocked/partial decisions, costs, exits and daily equity

## Minimum promotion gate
No promotion before BOTH:
- >=100 closed primary-lane trades
- >=12 calendar months from first eligible forward date

Interim data may be observed but must not be used to modify Candidate V2.
