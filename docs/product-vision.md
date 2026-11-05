# Product vision and roadmap

Companion to the project constitution, which holds
the binding principles. This page records what exists today, where the product
is going and in which order.

## Current state (level 1 verified 2026-10-11 on `main` at `e80c49a`; level 2 on `main`; level 3 proposed to `dev`)

| Area | Status | Evidence |
| --- | --- | --- |
| Domain: Company, Product, SaleItem, Sale, SalesDataset | Implemented | `src/sales_data_analyzer/domain/` |
| CSV import with atomic validation | Implemented | `importing/__init__.py`, `docs/csv-import.md` |
| Financial and product analyses (Decimal) | Implemented | `analysis/__init__.py` |
| Daily revenue forecast (linear trend + naive baseline, MAE/RMSE) | Implemented | `forecasting/__init__.py` |
| Automated tests | 323 `unittest` tests passing on the level 3 branch (42 at level 1, 144 at level 2) | `uv run python -m unittest discover -s tests` |
| Executable examples | All three run with the documented outputs | `examples/` |
| UML of implemented model | Four-page draw.io + SVG previews | `docs/diagrams/level-one*` |
| Program entry point | Level 2 terminal menu (`uv run sales-data-analyzer`) | `cli/`, `application/` (on `dev`) |
| Product catalog per company | Implemented in `CompanyWorkspace` (in memory) | `application/workspace.py` (on `dev`) |
| SQLite persistence and data maintenance | Implemented (level 3) | `persistence/`, `docs/database.md` |
| Temporal exploration and period comparison | Implemented with pandas, exact totals | `exploration/` |
| Forecast method comparison against baselines | Implemented (level 3) | `forecasting/methods.py`, `forecasting/comparison.py`, `docs/forecast-comparison.md` |
| Charts | Text bars and Matplotlib PNG files | `charts/` |
| PDF reports, GUI | Not started | — |
| CI and linter | GitHub Actions (3 OSes) and Ruff | `.github/workflows/tests.yml`, `pyproject.toml` |

## Final vision

A desktop application, built in Python with a clean object model, that lets a
small business analyst:

1. Import and clean sales data (CSV first) with clear, line-level diagnostics.
2. See exact business indicators: revenue, cost, gross profit, margin, average
   order value, product rankings.
3. Explore temporal analyses: daily/weekly/monthly revenue and comparisons
   between periods.
4. Visualize indicators and trends in charts.
5. Export PDF reports.
6. Keep companies, catalogs and sales in a local SQLite database.
7. Use everything through a PySide6 graphical interface.
8. Forecast revenue with Machine Learning models that are evaluated
   chronologically against a baseline, with limitations stated to the user.

## Explicitly out of scope

Payments, invoice or tax document issuing (emissão fiscal), inventory/stock
control, payroll and full ERP features. Big-data or cloud technologies (Spark,
NLP, cloud services) are not added unless a concrete requirement appears.

## Incremental roadmap

| Level | Increment | Done when |
| --- | --- | --- |
| 1 | Object model, CSV import, analyses, basic forecast, UML | Merged into `main` (PR #11). Video and submission are student actions. |
| 2 | Functional terminal menu exposing the existing operations, in memory | `specs/001-terminal-menu/` tasks complete and merged |
| 3 | Persistence in SQLite, maintenance, exploration, forecast comparison, charts | Feature branch proposed to `dev` |
| 4 | PySide6 graphical interface over the same application services | To be specified after level 3 |

Temporal analyses, charts and the improved forecast evaluation were delivered
with level 3. PDF reports are scheduled for level 4 or later.
