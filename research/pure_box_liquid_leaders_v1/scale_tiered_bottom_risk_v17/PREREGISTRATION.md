# Pure Box Scale-Tiered Bottom Risk V17

Status: research-only. No production change.

## Hypothesis
V15/V16 indicate Large boxes have much stronger standalone alpha, while Small boxes may still improve diversification/capital utilization.
Test asymmetric risk budgets instead of deleting Small.

## Frozen signal
Strict Wide+Fresh, direct next-session-open, Bottom <=20%.
No confirmation.
Top500 primary; Top300 robustness.

## Exit
Primary: 60% box target, lower stop, H20, 5 bps/side, stop-first.
No leverage. 50% single-name capital cap.

## Baselines
- fixed20 all scales
- equal risk 1.0% both
- equal risk 1.25% both
- equal risk 1.5% both

## Tiered lanes (predeclared)
Large / Small account-risk budget:
- 0.75% / 0.25%
- 1.00% / 0.25%
- 1.00% / 0.50%
- 1.25% / 0.25%
- 1.25% / 0.50%
- 1.50% / 0.25%
- 1.50% / 0.50%
- 1.50% / 0.75%

Requested capital = risk_budget(scale)*equity/effective stop distance.
Same-day requests scaled pro-rata if cash constrained.

## Interpretation
Require broad neighboring support across both Top500 and Top300. Do not choose an isolated maximum.
