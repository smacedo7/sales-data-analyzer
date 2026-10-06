# CSV import contract

`DataImporter.load(path, company) -> SalesDataset` is implemented by `CSVImporter`.
The company is required and reused by identity; the importer never creates or
modifies it. `SalesValidator.validate(values, line)` returns a frozen `ValidatedRow`.
The domain imports no parser or third-party package. The new import uses only the
standard library and adds no dependency or lockfile change.

Required header (order may vary; exact names, no duplicates or unknown columns):

```csv
sale_id,date_time,product_id,product,category,quantity,unit_price,unit_cost
```

Each record is an item. First appearance determines sale order; noncontiguous
records with the same sale ID join the same transaction. Repeated legitimate
items remain separate. Product objects are unique by product ID within one
import; their stripped name/category must agree. All sales share the explicit
company. `Sale.add_item` creates owned items; `SalesDataset.add_sale` associates
completed sales. IDs remain strings including leading zeros. Surrounding field
whitespace is stripped, including IDs and metadata; internal whitespace remains.
Historical prices/costs may differ between records for the same catalog product.

Quantity uses ASCII digits and must be positive. Money accepts plain decimal
notation (optional leading plus), finite and non-negative, directly into Decimal;
no float conversion, currency rounding, thousands separators, underscores or
exponents. Zero prices/costs and sales below cost are valid. Existing domain
arithmetic uses Python's Decimal context (default precision 28); input parsing
preserves the decimal representation, but totals follow that arithmetic context.

Dates require `YYYY-MM-DDTHH:MM:SS`, optionally 1–6 fractional digits and `Z` or
`±HH:MM`. Calendar dates and offsets are validated. Date-only/basic ISO forms
are rejected. A file must be entirely naive (local wall time, no inferred zone)
or entirely aware (normalized to UTC). Repeated sale IDs require the same instant;
different aware offsets for that instant are accepted. For forecasting aware
imports, explicitly pass the company timezone to the forecaster.

UTF-8 with or without BOM, standard CSV quoting, embedded commas/newlines and
CRLF are supported. Blank records are rejected, as are empty/header-only files,
missing fields, wrong column counts and malformed quoting. Errors are
`ImportValidationError(ValueError)` with `line`, `field`, `reason`; line is the
physical start of a logical record (header 1, file-access error 0). Diagnostics
omit raw values and paths. Wrong API argument types raise TypeError.

All catalog/sale collections are local to `load`. Any failure returns no dataset,
mutates no external company/catalog/dataset, and retains no partial importer
state. Calling the same importer again starts a fresh import.

Fixtures: `tests/fixtures/valid_sales.csv` and `invalid_sales.csv` are synthetic.
