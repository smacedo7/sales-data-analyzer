# Sales Data Analyzer

A desktop application designed to turn sales records into financial
metrics, product insights, and visual reports.

> Status: planning and initial setup. Application features are not
> implemented yet.

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
- [ ] Implement and test the domain model.
- [ ] Implement CSV import and validation.
- [ ] Implement sales analyses and charts.
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
