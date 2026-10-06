# Sales Data Analyzer

A desktop application designed to turn sales records into financial
metrics, product insights, and visual reports.

> Status: tested domain entities, financial/product analyses and a daily revenue
> forecasting service are implemented. The desktop application remains planned.

## Project Goals

- Import and validate sales records from CSV files.
- Calculate revenue, cost of goods sold, gross profit, gross margin,
  and average order value.
- Rank products by units sold and revenue.
- Analyze daily, weekly, monthly, and yearly sales.
- Identify peak sales hours.
- Generate charts and export PDF reports.
- Store data locally and provide a desktop interface.

## Planned Technology Stack

| Technology | Purpose |
| --- | --- |
| Python | Application development |
| uv | Project and dependency management |
| Pandas | Data preparation and analysis |
| NumPy | Numerical operations |
| Matplotlib | Charts |
| PySide6 | Desktop interface |
| SQLAlchemy + SQLite | Local persistence |
| pytest | Automated tests |
| Ruff | Linting and formatting |

Dependencies will be introduced as their features are implemented.

## Domain Model

- **Company:** the business whose sales are analyzed.
- **Product:** a catalog entry with a name and category.
- **Sale:** a transaction containing one or more sale items.
- **SaleItem:** a product's quantity, unit price, and unit cost
  at the time of a sale.
- **SalesDataset:** a collection of sales prepared for analysis.

Historical prices and costs belong to sale items so that later
catalog changes do not alter previous transactions.

## Planned CSV Format

Each row represents one sale item. Rows sharing the same `sale_id`
belong to the same transaction.

| Column | Description |
| --- | --- |
| sale_id | Transaction identifier |
| date_time | Transaction date and time |
| product_id | Product identifier |
| product | Product name |
| category | Product category |
| quantity | Units sold |
| unit_price | Selling price per unit |
| unit_cost | Historical cost per unit |

## Roadmap

- [x] Initialize the Python package with uv.
- [x] Create the public GitHub repository.
- [ ] Finalize requirements and the UML model in English.
- [x] Implement and test the domain model.
- [ ] Implement CSV import and validation.
- [x] Implement financial and product analyses.
- [x] Add a basic daily revenue forecast with temporal evaluation.
- [ ] Implement temporal analyses and charts.
- [ ] Add reporting and PDF export.
- [ ] Add local persistence.
- [ ] Build the desktop interface.

## Development Workflow

Changes are developed on dedicated branches and reviewed through
pull requests before merging into `main`.

Source code, documentation, and commit messages are written in English.

## Architecture Diagrams

The project includes two editable UML class diagrams:

- [Initial class diagram](docs/diagrams/initial-class-diagram.drawio):
  scope of the first delivery, including sales, imports, and analytics.
- [Planned class diagram](docs/diagrams/planned-class-diagram.drawio):
  proposed extensions for persistence, reporting, and the desktop interface.

Download a diagram and open it in [draw.io](https://app.diagrams.net/)
to inspect or edit it. These diagrams describe the intended design;
they do not indicate implemented features.

### Initial Sales Model

![Initial UML class diagram showing sales and CSV import relationships](docs/diagrams/initial-sales-model.svg)

The editable diagrams linked above include the remaining pages.

## Run the implemented features

Python >=3.14 remains required. `uv sync` installs the locked environment,
including scikit-learn 1.9.1. Tests use the standard-library unittest framework;
pytest and Ruff in the planned stack are not configured tools yet.

```sh
uv sync
uv run python examples/analysis_and_forecast.py
uv run python -m unittest discover -s tests -v
```

If the default cache is inaccessible, prefix commands with
`UV_CACHE_DIR=/tmp/sales-uv-cache`.

## Analysis contracts and architecture

`domain/` owns Company, Product, SaleItem, Sale and SalesDataset. A Sale owns
its items; a dataset associates existing sales of exactly one Company instance.
`analysis/` depends only on this domain and the standard library. `Analysis` is
an abstract base; FinancialAnalysis and ProductAnalysis override `run` so callers
can run either through the same polymorphic interface.

Both return a frozen AnalysisResult associated with the original company.
Financial results contain FinancialMetrics; product results contain immutable
ProductMetrics rows and two ID rankings. This deliberately replaces UML's
arbitrary `dict`/DataFrame with typed fields, removing Pandas from the core.
No empty application/repository layers were introduced: `run` and `forecast`
are the use cases; RevenueForecaster is the scikit-learn adapter.

Revenue and cost sum historical item amounts using Decimal. Gross profit is
revenue minus cost; gross margin is profit/revenue (a ratio, multiply by 100
for percent); average order value is revenue/transaction count. Empty totals
are zero; zero revenue gives None margin; no sales gives None ticket.
Products group by ID within the dataset company, including distinct objects
with the same ID. Rows use ascending ID; rankings use descending quantity or
revenue, then ascending ID for ties. Unsold catalog products are excluded.

## Forecasting policy and limitations

`daily_revenue` aggregates exact amounts over the earliest through latest
recorded calendar day, independently of sale insertion order. Naive timestamps
are treated as local calendar times. Aware timestamps require an explicit
company `tzinfo` (for example `ZoneInfo("America/Sao_Paulo")`), and are converted
before extracting the date. Passing a timezone for naive timestamps is rejected.
The Company entity currently has no timezone field; the caller supplies it.

Missing days raise an error by default. Select `missing_days="zero"` only when
records are complete and absent days mean no sales. This option fills internal
calendar gaps; it does not infer an observation period outside the first/last sale.
Do not use it to disguise incomplete records. Empty history cannot be forecast.

RevenueForecaster uses the day offset from the first observation as its only
feature. At least five training days and two holdout days are required; training
revenue must vary. `test_days` selects the final chronological days. A linear
regression fits only earlier days; a naive baseline repeats the last training
revenue. MAE is mean absolute error; RMSE is root mean squared error, in the
same revenue units. Neither model sees holdout targets during fitting.

Only after computing evaluation metrics does the model refit all observations
and predict `horizon` consecutive days after the last observation. ForecastResult
separates training, actual holdout, holdout predictions, model/baseline errors
and future predictions. Decimal is converted to finite float only for ML.
Noninteger/bool/nonpositive counts and nonfinite numeric conversions are rejected.

This small model learns a straight trend, not seasonality, holidays, promotions
or causality. Its minimum history is a validation floor, not evidence of useful
accuracy. It can lose to the baseline and can produce negative values; predictions
are intentionally not clipped. No confidence intervals or accuracy guarantees
are calculated. Synthetic linear data demonstrates mechanics, not real-world
performance. The independent holdout-change test checks leakage; existing entity
validation continues to reject invalid prices, quantities and company associations.

The example creates fourteen days of synthetic coffee sales (10, 20, ..., 140
revenue), prints financial/product results, evaluates the last three days and
forecasts the next three. It needs no external dataset or private records.

Official references: [LinearRegression](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LinearRegression.html)
and [installation/Python compatibility](https://scikit-learn.org/stable/install.html).
CSV import, GUI, database, TemporalAnalysis and ChartService remain future work.
