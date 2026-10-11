# Product vision and roadmap

Companion to the [constitution](../.specify/memory/constitution.md), which holds
the binding principles. This page records what exists today, where the product
is going and in which order.

## Current state (level 1 verified 2026-10-11 on `main` at `e80c49a`; level 2 on `dev`)

| Area | Status | Evidence |
| --- | --- | --- |
| Domain: Company, Product, SaleItem, Sale, SalesDataset | Implemented | `src/sales_data_analyzer/domain/` |
| CSV import with atomic validation | Implemented | `importing/__init__.py`, `docs/csv-import.md` |
| Financial and product analyses (Decimal) | Implemented | `analysis/__init__.py` |
| Daily revenue forecast (linear trend + naive baseline, MAE/RMSE) | Implemented | `forecasting/__init__.py` |
| Automated tests | 144 `unittest` tests passing on `dev` (42 at level 1) | `uv run python -m unittest discover -s tests` |
| Executable examples | Both run with the documented outputs | `examples/` |
| UML of implemented model | Four-page draw.io + SVG previews | `docs/diagrams/level-one*` |
| Program entry point | Level 2 terminal menu (`uv run sales-data-analyzer`) | `cli/`, `application/` (on `dev`) |
| Product catalog per company | Implemented in `CompanyWorkspace` (in memory) | `application/workspace.py` (on `dev`) |
| Persistence, charts, reports, GUI | Not started | — |
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
| 3 | Persistence in SQLite (companies, products, sales survive restarts) | To be specified after level 2 |
| 4 | PySide6 graphical interface over the same application services | To be specified after level 3 |

Temporal analyses, charts, PDF reports and improved ML evaluation are
scheduled into levels 3–4 (or between them) when each is specified; they are
not part of level 2.
