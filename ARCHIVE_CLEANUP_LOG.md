# Archive Cleanup Log — 2026-10-25

This cleanup removes only standalone rejected research artifacts whose exact source blobs were verified in `galbbb2772/box-strategy-archive` before deletion.

Archive destination prefix:
`01_REJECTED/sources/market-structure-lab/`

The following families were removed from the active repository because they are rejected in the master research index and are not referenced by the public HTML pages:
- Up/Down index strategy V1 and V2
- Up/Down short strategies V1, V2 and V3
- Entry Heat DCA and delayed DCA
- Interaction-tree validation

No live index data builder, current Market Structure Lab page, historical analog engine, Task 1/4 Forward-OOS, paper execution ledger, or current box/sequence research was removed.

All removed paths:
- `backtest_updown_index.py` → `https://github.com/galbbb2772/box-strategy-archive/blob/main/01_REJECTED/sources/market-structure-lab/backtest_updown_index.py`
- `.github/workflows/backtest_updown_index.yml` → `https://github.com/galbbb2772/box-strategy-archive/blob/main/01_REJECTED/sources/market-structure-lab/.github/workflows/backtest_updown_index.yml`
- `docs/data/updown_index_backtest.json` → `https://github.com/galbbb2772/box-strategy-archive/blob/main/01_REJECTED/sources/market-structure-lab/docs/data/updown_index_backtest.json`
- `backtest_updown_index_v2.py` → `https://github.com/galbbb2772/box-strategy-archive/blob/main/01_REJECTED/sources/market-structure-lab/backtest_updown_index_v2.py`
- `.github/workflows/backtest_updown_index_v2.yml` → `https://github.com/galbbb2772/box-strategy-archive/blob/main/01_REJECTED/sources/market-structure-lab/.github/workflows/backtest_updown_index_v2.yml`
- `docs/data/updown_index_backtest_v2.json` → `https://github.com/galbbb2772/box-strategy-archive/blob/main/01_REJECTED/sources/market-structure-lab/docs/data/updown_index_backtest_v2.json`
- `backtest_updown_short_v1.py` → `https://github.com/galbbb2772/box-strategy-archive/blob/main/01_REJECTED/sources/market-structure-lab/backtest_updown_short_v1.py`
- `.github/workflows/backtest_updown_short_v1.yml` → `https://github.com/galbbb2772/box-strategy-archive/blob/main/01_REJECTED/sources/market-structure-lab/.github/workflows/backtest_updown_short_v1.yml`
- `docs/data/updown_short_v1.json` → `https://github.com/galbbb2772/box-strategy-archive/blob/main/01_REJECTED/sources/market-structure-lab/docs/data/updown_short_v1.json`
- `backtest_updown_short_v2.py` → `https://github.com/galbbb2772/box-strategy-archive/blob/main/01_REJECTED/sources/market-structure-lab/backtest_updown_short_v2.py`
- `.github/workflows/backtest_updown_short_v2.yml` → `https://github.com/galbbb2772/box-strategy-archive/blob/main/01_REJECTED/sources/market-structure-lab/.github/workflows/backtest_updown_short_v2.yml`
- `docs/data/updown_short_v2.json` → `https://github.com/galbbb2772/box-strategy-archive/blob/main/01_REJECTED/sources/market-structure-lab/docs/data/updown_short_v2.json`
- `backtest_updown_short_v3.py` → `https://github.com/galbbb2772/box-strategy-archive/blob/main/01_REJECTED/sources/market-structure-lab/backtest_updown_short_v3.py`
- `.github/workflows/backtest_updown_short_v3.yml` → `https://github.com/galbbb2772/box-strategy-archive/blob/main/01_REJECTED/sources/market-structure-lab/.github/workflows/backtest_updown_short_v3.yml`
- `docs/data/updown_short_v3.json` → `https://github.com/galbbb2772/box-strategy-archive/blob/main/01_REJECTED/sources/market-structure-lab/docs/data/updown_short_v3.json`
- `research_entry_heat_dca.py` → `https://github.com/galbbb2772/box-strategy-archive/blob/main/01_REJECTED/sources/market-structure-lab/research_entry_heat_dca.py`
- `.github/workflows/research_entry_heat_dca.yml` → `https://github.com/galbbb2772/box-strategy-archive/blob/main/01_REJECTED/sources/market-structure-lab/.github/workflows/research_entry_heat_dca.yml`
- `docs/data/updown_entry_heat_dca.json` → `https://github.com/galbbb2772/box-strategy-archive/blob/main/01_REJECTED/sources/market-structure-lab/docs/data/updown_entry_heat_dca.json`
- `research_entry_heat_dca_delay.py` → `https://github.com/galbbb2772/box-strategy-archive/blob/main/01_REJECTED/sources/market-structure-lab/research_entry_heat_dca_delay.py`
- `.github/workflows/research_entry_heat_dca_delay.yml` → `https://github.com/galbbb2772/box-strategy-archive/blob/main/01_REJECTED/sources/market-structure-lab/.github/workflows/research_entry_heat_dca_delay.yml`
- `docs/data/updown_entry_heat_dca_delay.json` → `https://github.com/galbbb2772/box-strategy-archive/blob/main/01_REJECTED/sources/market-structure-lab/docs/data/updown_entry_heat_dca_delay.json`
- `research_interaction_tree.py` → `https://github.com/galbbb2772/box-strategy-archive/blob/main/01_REJECTED/sources/market-structure-lab/research_interaction_tree.py`
- `.github/workflows/run_interaction_tree_validation.yml` → `https://github.com/galbbb2772/box-strategy-archive/blob/main/01_REJECTED/sources/market-structure-lab/.github/workflows/run_interaction_tree_validation.yml`
- `docs/data/interaction_tree_validation.json` → `https://github.com/galbbb2772/box-strategy-archive/blob/main/01_REJECTED/sources/market-structure-lab/docs/data/interaction_tree_validation.json`

Verification before deletion: 24/24 source blob SHAs matched the archived copies.
