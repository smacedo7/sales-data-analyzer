# Quickstart: validate the terminal menu

Prerequisites: Python 3.14+, uv, repository root as working directory.

```sh
uv sync --locked
uv run python -m unittest discover -s tests -v      # all tests, incl. new ones
uv run ruff check .                                 # after T003
uv run sales-data-analyzer                          # interactive
```

## Scenario A — sample import and analyses (SC-001, SC-003)

1. `1` Create company → `Coffee Shop`, `Retail`.
2. `7` Import CSV → `tests/fixtures/valid_sales.csv` → expect
   `Imported 2 sales, 3 items. Products: 2 new, 0 reused.`
3. `10` → revenue 45.40, cost 18.20, gross profit 27.20.
4. `7` again with the same file → refused, sale IDs `001`, `002` already exist.
5. `8` Period `2026-01-02` to `2026-01-02` → `10` → revenue 5.00.

## Scenario B — catalog conflict (FR-015)

In a **new company**, register product `007` named `Coffee` in `Beverages`, then import
`tests/fixtures/valid_sales.csv` (where `007` is `Coffee, premium`) → refused
naming `007`; `4` List products still shows only the manual product.

## Scenario C — forecast (User Story 5)

New company → import `tests/fixtures/forecast_14_days.csv` → `12` with defaults
→ model/baseline errors, 7 future days, limitations notice. New company, import
`valid_sales.csv` → `12` → "Not enough history: 2 day(s) available...".

## Scripted run (both OSes)

The end-to-end test feeds a scripted stdin to
`python -m sales_data_analyzer` and checks exit code 0 and the scenario A
values. Run it alone with:

```sh
uv run python -m unittest tests.test_cli_end_to_end -v
```
