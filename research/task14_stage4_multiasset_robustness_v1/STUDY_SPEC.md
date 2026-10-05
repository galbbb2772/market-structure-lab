# Task 1/4 Stage-4 Multi-Asset Robustness V1

Status: historical diagnostic only. This study must not change Task 1/4 signal definitions, Forward-OOS ledgers, production rules, or broker execution.

## Purpose

Audit the frozen Stage-4 Multi-Asset V1 deployment layer after the primary 11-sector ETF simulation. The audit addresses two pre-specified implementation/robustness questions:

1. Repair the capital-scale maximum-drawdown statistic. The primary V1 called `simulate(..., keep_curve=False)` for the scale sweep while drawdown was computed from the retained curve, mechanically producing zero drawdown. The robustness layer reruns the identical simulations with the equity path retained for calculation, then removes the path from the stored scale records.
2. Test whether the historical multi-asset result is dominated by one sector or by the inverse-volatility allocator.

## Frozen inputs

- Same 11 SPDR sector ETFs as Multi-Asset V1: XLC, XLY, XLP, XLE, XLF, XLV, XLI, XLB, XLRE, XLK, XLU.
- Same SPY benchmark.
- Same historical Early Sequence = 15 and Full Sequence = 12.
- Same next-regular-session-open entry and signal+10-SPY-session close exit.
- Same square-root impact cost model for robustness comparisons.
- Same $100,000 start capital for sector robustness.
- Same 25% sleeve / 100% gross-cap policy for the primary robustness target.

## Capital-scale drawdown repair

Rerun exactly the existing `early_full_stack25_beta100_cap100` + `square_root_impact` simulation at $100k, $1m, $10m, and $100m with the equity path retained while computing max drawdown. No cost, allocation, signal, or exit rule may change.

## Sector Leave-One-Out

For each of the 11 sector ETFs independently:

- remove that ETF from every historical signal context;
- recompute equal/inverse-vol/beta-aware allocations using only information available at that signal date;
- rerun `early_full_stack25_invvol_cap100` with the square-root impact model;
- report return, max drawdown, modeled cost, max ADV participation, max beta, and max sector weight.

The audit reports XLU and XLE explicitly because the primary result showed large negative/positive contribution respectively, but they are not pre-authorized exclusions and must not become production filters from this historical test.

## Allocation comparison

Add one diagnostic-only policy: `early_full_stack25_equal_cap100`, identical to the frozen 25% stack policy except sector weights are equal rather than inverse-volatility. Compare it against the existing inverse-volatility policy under the same square-root impact model.

## P&L concentration

Using the frozen inverse-volatility baseline, report absolute-P&L contribution shares, largest-sector share, top-two-sector share, and HHI of absolute sector P&L. These are concentration diagnostics, not selection criteria.

## Guardrails

- `research_only=true`
- `diagnostic_only=true`
- `production_effect=none`
- `thresholds_changed=false`
- `stock_selection_inferred=false`
- no automatic sector deletion or promotion
- no historical result counts as Forward-OOS
- no broker orders
