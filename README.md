# Sales Data Analyzer

A Python project for sales analytics and basic daily revenue forecasting,
with a desktop application planned for a later stage.

The current implementation provides validated sales entities, financial and
product analyses, atomic CSV import, and a small Machine Learning forecasting service. Features
are available through an interactive terminal menu (level 2), the Python API and
executable synthetic-data examples.

## Implemented Features

- Company, Product, SaleItem, Sale and SalesDataset domain entities.
- CSV import through DataImporter/CSVImporter and field-level SalesValidator diagnostics.
- Historical prices and costs stored as `Decimal` on each sale item.
- Company ownership, transaction ID and timestamp consistency validation.
- Dataset filtering over half-open periods `[start, end)`.
- Revenue, cost, gross profit, gross margin and average order value.
- Product quantity, revenue and gross profit totals with deterministic rankings.
- Daily revenue aggregation with explicit missing-day and timezone policies.
- Linear regression forecasting, chronological holdout evaluation and a naive baseline.
- Typed results, English docstrings and automated tests using `unittest`.
- Terminal menu (level 2): companies, per-company product catalog, manual
  sales, CSV import, inclusive periods, analyses and the revenue forecast.

Charts, PDF reports, persistence and a desktop interface remain planned.

## Getting Started

Requirements: Python **3.14 or newer** and [uv](https://docs.astral.sh/uv/).
Run these commands from the repository root:

```sh
uv sync --locked
uv run python examples/import_and_analyze.py
uv run python examples/analysis_and_forecast.py
```

The CSV example imports the included synthetic fixture and prints 2 sales,
3 items, revenue 45.40, cost 18.20 and gross profit 27.20.

The forecasting example creates fourteen days of synthetic coffee sales, with daily revenue
from 10 to 140. It prints financial and product results, evaluates the last three
days and forecasts the following three. No external sales data is needed.
Dependencies are installed by `uv sync`.

Expected accounting results:

| Metric | Value |
| --- | ---: |
| Revenue | 1,050 |
| Cost | 420 |
| Gross profit | 630 |
| Gross margin | 0.6 (60%) |
| Average order value | 75 |

## Running the Terminal Menu

The same commands work in macOS/Linux shells and Windows PowerShell:

```sh
uv sync --locked
uv run sales-data-analyzer
# or: uv run python -m sales_data_analyzer
```

The menu lists numbered options: create/select a company, register, list and
find products, record a sale, import a CSV, set or clear a period, run the
financial and product analyses, and forecast revenue. Type the option number
and answer the prompts; invalid values are explained and asked again, and no
input ends the program with an error trace.

**Data is kept in memory only.** Everything is lost when you exit (option `0`,
which asks for confirmation) or press Ctrl+C / Ctrl+D. Persistence arrives in
level 3.

Try it with the included fixture: create a company, choose `7`, type
`tests/fixtures/valid_sales.csv` (quotes from drag-and-drop are accepted), then
`10` for revenue 45.40, cost 18.20 and gross profit 27.20. For a forecast,
import `tests/fixtures/forecast_14_days.csv` into a new company and choose `12`.

Import and entry policies:

- A CSV import is all or nothing. It is refused when any sale ID already exists
  in the company (so importing the same file twice is refused) or when a
  product ID has a different name or category than the catalog; the refusal
  lists the IDs.
- Products already in the catalog with the same name and category are reused;
  new ones are added to the catalog. Prices and costs stay historical per item.
- A company's sales either all carry UTC offsets or none do; offsets are
  normalized to UTC, and periods are read as UTC days for such data. The
  forecast asks which UTC offset to use for grouping days.
- Periods include both the start and the end date.
- Manual sales use products from the catalog and need at least one item.

## Tests

```sh
uv run python -m unittest discover -s tests -v
```

Tests cover the application layer, terminal parsing, formatting and scripted
menu sessions, an end-to-end run of the real entry point, CSV validation, atomic import, ID preservation, domain validation, exact accounting, empty/zero/loss cases, product
identity, ranking ties, temporal ordering, holdout isolation, baseline errors,
missing days, timezone conversion and invalid forecast inputs.

If the default uv cache is inaccessible, prefix commands with
`UV_CACHE_DIR=/tmp/sales-uv-cache`.

Lint and format checks (Ruff, a development dependency):

```sh
uv run ruff check .
uv run ruff format --check src/sales_data_analyzer/application src/sales_data_analyzer/cli
```

GitHub Actions runs the tests on Ubuntu, macOS and Windows plus the Ruff
checks on every pull request to `main` or `dev` and every push to `dev`.

## Current Technology Stack

| Technology | Current purpose |
| --- | --- |
| Python >=3.14 | Domain model, analyses and forecasting |
| uv | Environment, dependencies and lockfile |
| Standard library `decimal` | Exact accounting amounts |
| Standard library `unittest` | Automated tests |
| scikit-learn | Linear regression |
| NumPy and SciPy | Numerical dependencies of scikit-learn |
| Ruff (development only) | Lint and format checks |
| GitHub Actions | Continuous integration on Ubuntu, macOS and Windows |

Pandas, Matplotlib, PySide6 and SQLite are candidates for future features.

## Architecture and Object Model

```text
src/sales_data_analyzer/
├── domain/        # Sales entities and shared validation
├── importing/     # Import contract, CSV adapter and row validation
├── analysis/      # Abstract Analysis, implementations and typed results
├── forecasting/   # Daily aggregation and scikit-learn forecasting adapter
├── application/   # Level 2: session, company workspaces, use-case errors
└── cli/           # Level 2: terminal menu, input parsing, output formatting
examples/
├── import_and_analyze.py
└── analysis_and_forecast.py
tests/
docs/
```

The domain and descriptive analyses depend only on the standard library.
The forecasting module imports scikit-learn when a forecast is requested.
The `application` layer coordinates the existing classes into use cases that
any interface can reuse (terminal now, GUI later) and never reads input or
prints; `cli` is the only package that does. Dependencies point downwards only.

| Component | Responsibility |
| --- | --- |
| `Company` | Business associated with products and sales |
| `Product` | Company-scoped catalog identity, name and category |
| `SaleItem` | Product reference, quantity and historical unit price/cost |
| `Sale` | Transaction that creates and owns its items |
| `SalesDataset` | Collection associating existing sales of one Company instance |
| `DataImporter` | Abstract `load(path, company) -> SalesDataset` contract |
| `CSVImporter` | Atomic UTF-8 CSV loading and domain construction |
| `SalesValidator` | Typed row validation with line/field/reason diagnostics |
| `Analysis` | Abstract `run(data: SalesDataset) -> AnalysisResult` contract |
| `FinancialAnalysis` | Exact financial metrics |
| `ProductAnalysis` | Product grouping and rankings |
| `AnalysisResult` | Frozen result associated with the dataset company |
| `RevenueForecaster` | Temporal evaluation and future revenue predictions |
| `SalesSession` | Companies, selected company and active period of one run |
| `CompanyWorkspace` | One company's catalog and sales; manual sales and import policies |
| `Selection` | All data or an inclusive date period |
| `ApplicationError` | Base of the use-case refusals (duplicates, conflicts, history) |
| `TerminalMenu` | Numbered menu over the session with injectable input/output |

FinancialAnalysis and ProductAnalysis inherit from Analysis and implement the
same method, allowing callers to use them polymorphically. AnalysisResult holds
FinancialMetrics or ProductMetrics rows and ranking tuples. These explicit
fields replace the UML's original arbitrary dictionary/DataFrame contract.
Forecasting uses a separate ForecastResult because its predictive contract
includes dates, evaluation metrics and future estimates.

See [Sale](docs/sale.md) and [SalesDataset](docs/sales-dataset.md) for the
existing entity contracts.

## CSV Import Contract

`CSVImporter.load(path, company)` returns a complete SalesDataset for the supplied
Company instance. It validates all records before returning a dataset; failures
leave no partial result or importer state. It uses only the standard library.

Required columns (order may vary; names must match exactly):

```csv
sale_id,date_time,product_id,product,category,quantity,unit_price,unit_cost
```

Each row is an item. Rows sharing a sale ID join one transaction, even when
noncontiguous; repeated legitimate items remain separate. IDs stay strings,
including leading zeros, with surrounding whitespace stripped. Product IDs must
have consistent names/categories; each sale ID must have a consistent timestamp.

Quantities are positive integers. Prices/costs use plain finite nonnegative
Decimal notation, preserving historical values without float conversion.
Dates require ISO timestamps with seconds; aware timestamps normalize to UTC,
and naive/aware values cannot mix within a file. UTF-8 BOM and CSV quoting are
supported. Empty/header-only files and blank or malformed records are rejected.

`ImportValidationError` exposes physical `line`, `field` and `reason`, without
raw input values or paths. Wrong API argument types raise TypeError. See the
[complete CSV contract](docs/csv-import.md) for supported formats and arithmetic
precision rules. For forecasting aware imports, supply the company timezone.

## Accounting Rules

Revenue and cost sum historical sale-item amounts using `Decimal`. Catalog
changes do not replace historical prices or costs.

- Gross profit = revenue − cost.
- Gross margin = gross profit / revenue, expressed as a ratio.
- Average order value = revenue / number of transactions.
- Empty datasets have zero totals. Margin is `None` at zero revenue;
  average order value is `None` without sales.
- Products group by ID within the dataset company, including distinct objects
  with the same ID. Unsold catalog products are excluded.
- Product rows use ascending ID. Rankings use descending quantity or revenue,
  with ascending ID as the tie breaker.

## Forecasting Rules and Limitations

Daily aggregation covers the earliest through latest recorded sale date.
Naive timestamps represent local calendar times. Aware timestamps require an
explicit common company `tzinfo`, such as `ZoneInfo("America/Sao_Paulo")`, and
are converted before extracting dates. Passing a timezone for naive timestamps
is rejected. The caller supplies the timezone; Company has no timezone field.

Missing days raise an error by default. Select `missing_days="zero"` only when
records are complete and absent dates mean no sales. This fills internal gaps;
it does not infer an observation period outside the first and last sale.

The model uses the calendar-day offset from the first observation as its only
feature. At least five training days and two test days are required, with
varying training revenue. `test_days` selects the final chronological days.
Regression fits only earlier observations. The baseline repeats the last
training-day revenue throughout the test period.

MAE measures average absolute error; RMSE is root mean squared error. Both use
the revenue unit. After evaluation, a separate refit uses all observations to
predict `horizon` consecutive future days. ForecastResult exposes training
observations, test actuals/predictions, model/baseline errors and future dates.
Accounting stays in Decimal; ML converts revenue to finite float. Invalid
counts, insufficient history and numeric/calendar overflow are rejected.

This model learns a straight trend and does not account for seasonality,
holidays or promotions. It can lose to the baseline and produce negative
predictions, which are not clipped. No confidence intervals or accuracy
guarantees are calculated. Good results on synthetic linear data demonstrate
the mechanics, not real-world performance.

Reference: [scikit-learn LinearRegression](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LinearRegression.html).

## UML and Level 1 Delivery

The authoritative implemented model is [level-one.drawio](docs/diagrams/level-one.drawio),
with four pages and matching previews:

- [Domain](docs/diagrams/level-one-domain.svg): entities and ownership.
- [Import](docs/diagrams/level-one-import.svg): importer inheritance and validation.
- [Analysis](docs/diagrams/level-one-analysis.svg): polymorphism and typed results.
- [Forecast](docs/diagrams/level-one-forecast.svg): prediction/evaluation contracts.

The level 2 layers are modeled in [level-two.drawio](docs/diagrams/level-two.drawio)
([preview](docs/diagrams/level-two.svg)); the feature is specified in
[specs/001-terminal-menu](specs/001-terminal-menu/spec.md).

See the [delivery checklist](docs/level-one-delivery.md) for implementation and
test evidence, and the [Portuguese video script](docs/video-script-pt.md) for a
planned presentation under three minutes. Recording, publication and submission
remain student actions; prepared materials are not a submitted delivery.

The [initial diagram](docs/diagrams/initial-class-diagram.drawio) is design history.
The [planned diagram](docs/diagrams/planned-class-diagram.drawio) describes future
extensions. Open editable files in [draw.io](https://app.diagrams.net/).

## Roadmap

- [x] Initialize the Python package and public repository.
- [x] Implement and test the sales domain model.
- [x] Implement financial and product analyses.
- [x] Add basic daily revenue forecasting with temporal evaluation.
- [x] Document the implemented domain/import/analysis/forecast model in UML.
- [x] Prepare delivery evidence and a video script.
- [ ] Record/publish the video and submit the delivery links.
- [x] Implement CSV import and validation.
- [x] Level 2: interactive terminal menu over the existing operations (in memory).
- [x] Continuous integration and Ruff lint checks.
- [ ] Implement descriptive temporal analyses and charts.
- [ ] Add reporting and PDF export.
- [ ] Add local persistence.
- [ ] Build the desktop interface.

## Development Workflow

Work is integrated on the `dev` branch and proposed to `main` through a
`dev → main` pull request reviewed before merging. Features are specified with
Spec Kit in `specs/`. Source code, documentation, commits and PR descriptions are in English.
