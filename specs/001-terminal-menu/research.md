# Research and decisions: Functional Terminal Menu

Each entry: decision, rationale, alternatives considered.

## R1. Where session state lives

- **Decision**: a new `application/` package with `SalesSession` and
  `CompanyWorkspace`; the domain is not changed.
- **Rationale**: the domain has no catalog or company registry (products exist
  only inside one import). Those are use-case concerns that levels 3 and 4 also
  need, independent of the terminal.
- **Alternatives**: add a catalog to `Company` (rejected: mixes aggregate
  boundaries and changes a stable, delivered class); keep state inside the menu
  (rejected: GUI would have to duplicate it).

## R2. Repeated imports and duplicate sale IDs (D2)

- **Decision**: refuse the whole import if any sale ID already exists in the
  company; report the count and up to five IDs.
- **Rationale**: matches the level 1 atomic import rule, makes re-importing the
  same file a safe no-op, and needs no heuristics. The user can split or
  rename IDs in the file.
- **Alternatives**: skip existing IDs (rejected: silently hides changed rows
  with the same ID); overwrite (rejected: breaks history); merge items into the
  existing sale (rejected: double counts on re-import).

## R3. Catalog conflicts (D2)

- **Decision**: same ID + same trimmed name and category → reuse the catalog
  product object; same ID + different name or category → refuse the import.
- **Rationale**: product identity is the ID inside a company; a different name
  for the same ID is ambiguous data that the analyst must fix. Reusing the same
  object keeps one product per ID (association, not duplication).
- **Alternatives**: update the catalog with the file's name (rejected: implicit
  edits; editing is out of scope); keep both objects (rejected: two catalog
  entries for one ID).
- **Implementation note**: `CSVImporter` builds its own `Product` objects; the
  workspace rebuilds each imported sale through `Sale.add_item` using catalog
  products, keeping historical prices/costs untouched. The importer itself is
  not modified.

## R4. Atomic application of changes

- **Decision**: build a candidate `SalesDataset` with existing + new sales and a
  candidate catalog dictionary; replace the workspace's references only after
  all `add_sale` calls succeed.
- **Rationale**: reuses domain validation (duplicate ID, awareness, ownership)
  as the final gate without partial state.
- **Alternatives**: validate then append in place (rejected: a late domain error
  would leave a partial state).

## R5. Period input

- **Decision**: user types start and end dates `YYYY-MM-DD`, both inclusive;
  converted to `[start 00:00, end+1day 00:00)` for `SalesDataset.filter_period`.
  For aware data the bounds are UTC.
- **Rationale**: inclusive whole days are how analysts think; the half-open
  domain contract stays intact.
- **Alternatives**: typing date-times (rejected: error prone); exclusive end
  (rejected: surprising to users).

## R6. Time zone for forecasting aware data

- **Decision**: ask for a fixed UTC offset `±HH:MM` (default `+00:00`), built
  with `datetime.timezone`.
- **Rationale**: works on Windows without the `tzdata` package; the forecaster
  already accepts any `tzinfo`.
- **Alternatives**: IANA names via `zoneinfo` (rejected for now: needs `tzdata`
  on Windows, a new dependency; DST precision is not needed for daily
  aggregation in this increment).

## R7. Menu I/O testability

- **Decision**: `TerminalMenu(input_fn, output_fn)` with defaults `input` and
  `print`; tests inject scripted functions.
- **Rationale**: no mocking library needed; deterministic tests.
- **Alternatives**: `cmd.Cmd` (rejected: command-line style rather than
  numbered menu, harder for first-time users); `unittest.mock.patch` on
  builtins (rejected: brittle).

## R8. Entry point

- **Decision**: `sales_data_analyzer.main()` (already the console script target)
  calls `cli.run()`; add `__main__.py`.
- **Rationale**: no `pyproject.toml` change needed; same command on all OSes.

## R9. Display formatting

- **Decision**: money `quantize(Decimal("0.01"), ROUND_HALF_UP)` with thousands
  separator (`1,050.00`); margin as percentage with one decimal; `n/a` for None;
  forecast floats with two decimals.
- **Rationale**: readable and exact for display; stored values untouched.

## R10. Menu language (D1)

- **Decision**: English by default, all strings in one module so a Portuguese
  version is a small, contained change.
- **Rationale**: repository language policy; but the course presentation may
  favour Portuguese, so this is flagged for the maintainer.

## R11. Ruff adoption (D4)

- **Decision**: lint (`ruff check`) now with a conservative rule set; format only
  new code now; whole-repo formatting in a dedicated later PR.
- **Rationale**: avoids a large mixed diff in the level 2 PR.

## R12. CI

- **Decision**: GitHub Actions, `astral-sh/setup-uv`, matrix of three OSes,
  `uv sync --locked`.
- **Rationale**: verifies the macOS/Windows requirement on every PR at no cost
  for a public repository.
