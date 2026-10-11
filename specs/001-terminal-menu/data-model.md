# Data model: Functional Terminal Menu

Existing domain classes are reused unchanged (see `docs/sale.md`,
`docs/sales-dataset.md`, `docs/csv-import.md`). New classes belong to
`sales_data_analyzer.application`.

## CompanyWorkspace

One company and everything recorded for it in the session.

| Field | Type | Rules |
| --- | --- | --- |
| `company` | `Company` | Fixed at creation |
| `products` (read-only view) | `tuple[Product, ...]` | Ordered by ID; IDs unique; every product's `company is self.company` |
| `sales` (read-only) | `SalesDataset` | All sales of the company; sale IDs unique; one timestamp awareness |

Operations (all-or-nothing):

- `register_product(product_id, name, category) -> Product` — duplicate ID →
  `DuplicateProductError`; domain validation errors propagate.
- `find_product(product_id) -> Product | None` — trims the ID.
- `has_sale(sale_id) -> bool` — trims the ID.
- `record_sale(sale_id, date_time, items: Sequence[ItemInput]) -> Sale` —
  checks in order: duplicate sale ID → `DuplicateSaleError`; empty items →
  `EmptySaleError`; unknown product → `UnknownProductError`; awareness
  mismatch → `TimestampAwarenessError`. Aware date-times are normalized to
  UTC, like the importer.
- `import_sales(path, importer: DataImporter | None = None) -> ImportSummary` —
  validation via `CSVImporter`; then checks in this order: duplicate sale IDs
  (`DuplicateSaleError`, with all conflicting IDs), catalog conflicts
  (`CatalogConflictError`, with conflicting product IDs), awareness
  (`TimestampAwarenessError`). Only then sales are rebuilt with catalog products
  and swapped in.

## ItemInput (frozen dataclass)

`product_id: str`, `quantity: int`, `unit_price: Decimal`, `unit_cost: Decimal`.
Value validation is delegated to `SaleItem` through `Sale.add_item`.

## ImportSummary (frozen dataclass)

`sales_added: int`, `items_added: int`, `new_products: int`,
`reused_products: int`.

## Selection (frozen dataclass)

`start: date | None`, `end: date | None` (both inclusive). `None/None` means all
data. Invariant: both set or both None; `start <= end`; `end < 9999-12-31`
(the exclusive bound is the following day).

## SalesSession

| Field | Type | Rules |
| --- | --- | --- |
| `workspaces` | `tuple[CompanyWorkspace, ...]` | Creation order; names unique case-insensitively after trim |
| `current` | `CompanyWorkspace | None` | Set on create/select |
| `selection` | `Selection` | Reset to all data when the selected company changes |

Operations:

- `create_company(name, sector) -> CompanyWorkspace` (selects it) —
  `DuplicateCompanyError`.
- `select_company(index: int) -> CompanyWorkspace` — 1-based list index;
  `CompanyNotFoundError`.
- `require_current() -> CompanyWorkspace` — `NoCompanySelectedError`.
- `set_period(start: date, end: date)` / `clear_period()` —
  `InvalidPeriodError` when `start > end`.
- `selected_sales() -> SalesDataset` — all sales or
  `filter_period(start 00:00, end+1 00:00)`; bounds use UTC when the data is
  aware.
- `run_financial_analysis() -> AnalysisResult`
- `run_product_analysis() -> AnalysisResult`
- `run_forecast(horizon=7, test_days=2, missing_days="reject",
  utc_offset: timedelta | None = None) -> ForecastResult` — `utc_offset` is
  required when data is aware and ignored otherwise. Raises
  `NoSalesInSelectionError` for an empty selection and
  `InsufficientHistoryError` (with day counts) before calling the
  forecaster when history is shorter than `5 + test_days` days.

## Error hierarchy (`application/errors.py`)

```text
ApplicationError(ValueError)
├── NoCompanySelectedError
├── DuplicateCompanyError
├── CompanyNotFoundError
├── DuplicateProductError
├── UnknownProductError
├── EmptySaleError
├── DuplicateSaleError          (.sale_ids: tuple[str, ...])
├── CatalogConflictError        (.product_ids: tuple[str, ...])
├── TimestampAwarenessError
├── InvalidPeriodError
├── NoSalesInSelectionError
└── InsufficientHistoryError    (.available_days: int, .required_days: int)
```

Subclassing `ValueError` keeps them consistent with domain validation errors.
`str(error)` carries counts only, never IDs, raw values or paths
(constitution IV); adapters read the attributes to show details.

## State transitions

```text
[no company] --create--> [company selected, all data]
[company selected] --select other--> [other company, all data]
[any selection] --set period--> [period] --clear--> [all data]
refused operation: state unchanged (asserted in tests)
exit / EOF: state discarded
```
