# Local database (level 3)

The terminal program keeps companies, catalogs and sales in one SQLite file.
This page describes where the file is, what it contains and what is guaranteed.

## Location

| System | Default file |
| --- | --- |
| macOS | `~/Library/Application Support/Sales Data Analyzer/sales.sqlite3` |
| Windows | `%LOCALAPPDATA%\Sales Data Analyzer\sales.sqlite3` |
| Other | `$XDG_DATA_HOME/sales-data-analyzer/sales.sqlite3`, or `~/.local/share/sales-data-analyzer/` |

The folder is created when missing. `--database PATH` selects another file; the
project's `data/` folder is ignored by Git and suits demo databases. Keeping the
default file outside the code means it survives deleting or re-cloning the
repository and can never be committed by mistake.

## Schema (version 1)

Four `STRICT` tables, defined with SQLAlchemy Core in
`src/sales_data_analyzer/persistence/schema.py`:

| Table | Holds | Key rules |
| --- | --- | --- |
| `company` | name, sector | `name_key` (case-folded trimmed name) is unique |
| `product` | company-scoped code, name, category | `(company_id, code)` unique |
| `sale` | company-scoped code, ISO 8601 timestamp | `(company_id, code)` unique |
| `sale_item` | position, product, quantity, unit price, unit cost | composite foreign keys make the sale and the product belong to the same company; quantity > 0; amounts in plain decimal text |

Integer `id` columns exist only for foreign keys and insertion order. The file
is marked with `PRAGMA application_id` (ASCII "SADA") and
`PRAGMA user_version = 1`; other files are refused, never modified.

## Guarantees

- **Exact amounts.** Unit prices and costs are stored as text such as `10.50`
  or `0.0000000` and read back with `Decimal`, keeping value and decimal places.
  SQLite has no exact decimal type and SQLAlchemy's `Numeric` reads through
  floating point (`0.1` came back as `0.10000000000000000555` in a check), so it
  is not used. Totals are never stored; analyses recompute them.
- **History.** Items keep the price and cost recorded at sale time.
- **All or nothing.** Each import, manual sale, edit and deletion is one
  `BEGIN IMMEDIATE` transaction. The session is updated only after the commit,
  so a failure leaves both the file and the program unchanged.
- **Validated loading.** Rows are rebuilt through the domain constructors at
  start-up; invalid rows (for example edited by hand) stop the start-up with a
  table name and count.
- **Safe deletions.** A product used by any sale item cannot be deleted (the
  program refuses first and the schema's `RESTRICT` key backs it up). Deleting
  a sale removes its items through `ON DELETE CASCADE`. Companies are not deleted.
- **Edits keep history.** Renaming a product changes how it is shown everywhere,
  while item prices and costs stay as recorded. An edit or deletion that finds
  no matching row (changed by another copy) is rolled back and reported.
- **Foreign keys on.** Every connection enables and checks
  `PRAGMA foreign_keys`.

## Limitations

- Use one running copy per file. A second copy that tries to write while the
  first holds the lock is told the database is busy; data loaded earlier by one
  copy does not refresh when the other writes.
- Quantities above 9,223,372,036,854,775,807 cannot be stored and are refused.
- Timestamps keep their kind: values with offsets are stored in UTC, local
  times without offset stay local.
- There are no migrations yet; a later version will add them when the schema
  changes.
