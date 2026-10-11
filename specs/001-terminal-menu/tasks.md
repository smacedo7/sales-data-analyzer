---

description: "Task list for the level 2 functional terminal menu"
---

# Tasks: Functional Terminal Menu (Level 2)

**Input**: Design documents from `specs/001-terminal-menu/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Required. The constitution (Principle III) makes tests mandatory for
every behaviour change, so every implementation task includes its tests.

**Organization**: Setup and foundational tasks first, then one phase per user
story in the order that respects dependencies (US1 → US2 → US3 → US4 → US5).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on unfinished tasks)
- **[Story]**: user story from spec.md (US1–US5)
- Each task lists **Files**, **Acceptance**, **Tests** and **Done when**.
- Global done rule for every task: full suite green
  (`uv run python -m unittest discover -s tests -v`), new public code typed and
  documented, one Conventional Commit on `dev`.

## Path Conventions

Single project: `src/sales_data_analyzer/`, `tests/` at repository root.

---

## Phase 1: Setup (tooling, no product behaviour)

**Purpose**: cross-platform test command, CI and Ruff, before feature code.

- [X] T001 Make `test_dependency_isolation` independent of the caller's `PYTHONPATH` in tests/test_importing.py
  - **Files**: `tests/test_importing.py`, `CLAUDE.md`, `README.md`, `.claude/skills/project-verification/SKILL.md`, `.specify/memory/constitution.md` (PATCH 1.0.1 via `/speckit-constitution`: test command without prefix)
  - **Acceptance**: the subprocess receives `env={**os.environ, "PYTHONPATH": <abs path to src>}`; `uv run python -m unittest discover -s tests` passes with no prefix on macOS/Linux/Windows; docs show the prefix-free command (keep a note that the old prefix still works).
  - **Tests**: existing 42 tests pass without `PYTHONPATH=src`; still pass with it.
  - **Done when**: both commands give `Ran 42 tests ... OK`; constitution reads v1.0.1 with the prefix-free command; commit `test: run dependency isolation check without external PYTHONPATH`.

- [X] T002 Add GitHub Actions test workflow in .github/workflows/tests.yml
  - **Files**: `.github/workflows/tests.yml`
  - **Acceptance**: triggers on `pull_request` to `main`/`dev` and `push` to `dev`; matrix `ubuntu-latest`, `macos-latest`, `windows-latest`; `astral-sh/setup-uv` pinned to a major version with Python 3.14; `uv sync --locked`; runs the unittest command; no secrets; `permissions: contents: read`.
  - **Tests**: workflow green on the first push of `dev` containing it (all three OSes).
  - **Done when**: a green run is linked in the task's commit or PR notes; commit `ci: run unit tests on Linux, macOS and Windows`.

- [X] T003 Introduce Ruff lint configuration in pyproject.toml
  - **Files**: `pyproject.toml` (`[dependency-groups] dev = ["ruff>=…"]`, `[tool.ruff]` `target-version = "py314"`, `line-length = 100`, `[tool.ruff.lint] select = ["E4","E7","E9","F","B"]` (import sorting `I` deferred to the style PR, D4, because it would edit `domain/` and `importing/`)), `uv.lock`
  - **Acceptance**: `uv sync --locked` installs Ruff; `uv run ruff check .` passes. Findings in existing files are not fixed in this task if they are in `domain/`, `importing/`, `analysis/` or `forecasting/`; they is listed in the commit body and suppressed per-line with a reason. No `ruff format` run on existing files.
  - **Tests**: full suite unchanged and green.
  - **Done when**: `ruff check .` exits 0; diff touches only `pyproject.toml`, `uv.lock` and per-line suppressions; commit `chore: add Ruff linting with a conservative rule set`.

- [X] T004 Add Ruff steps to CI in .github/workflows/tests.yml
  - **Files**: `.github/workflows/tests.yml`
  - **Acceptance**: one job (ubuntu) runs `uv run ruff check .` and `uv run ruff format --check src/sales_data_analyzer/application src/sales_data_analyzer/cli tests/test_application_*.py tests/test_cli_*.py` (paths created later; step tolerates missing paths until T005 by listing only existing ones, or is added with T005).
  - **Tests**: CI green.
  - **Done when**: lint job green on `dev`; commit `ci: check Ruff lint and formatting of new packages`.

**Checkpoint**: tooling ready; no product behaviour changed.

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: packages, errors, parsing, formatting primitives and the menu shell.

- [X] T005 Create application package, error hierarchy and session skeleton in src/sales_data_analyzer/application/errors.py
  - **Files**: `src/sales_data_analyzer/application/__init__.py`, `src/sales_data_analyzer/application/errors.py`, `src/sales_data_analyzer/application/session.py` (skeleton), `tests/test_application_errors.py`
  - **Acceptance**: classes exactly as in data-model.md "Error hierarchy"; `ApplicationError(ValueError)`; `DuplicateSaleError.sale_ids` and `CatalogConflictError.product_ids` are `tuple[str, ...]`; `str(error)` contains only counts, never IDs, values or paths (constitution IV); the terminal shows IDs from the attributes. Also a `SalesSession` skeleton in `application/session.py` with `current` (initially `None`) and `require_current()` raising `NoCompanySelectedError`, so the menu shell can be built on it.
  - **Tests**: subclassing, attributes, messages without IDs, `require_current()` on an empty session.
  - **Done when**: tests pass; commit `feat: add application error hierarchy`.

- [X] T006 [P] Implement typed text parsing in src/sales_data_analyzer/cli/parsing.py
  - **Files**: `src/sales_data_analyzer/cli/__init__.py`, `src/sales_data_analyzer/cli/parsing.py`, `tests/test_cli_parsing.py`
  - **Acceptance**: `InputError(ValueError)`; `parse_text`, `parse_positive_int`, `parse_amount` (plain non-negative decimal → `Decimal`, same grammar as `SalesValidator`), `parse_date` (`YYYY-MM-DD`, rejecting 9999-12-31 because the period end needs the following day), `parse_datetime` (same grammar as CSV import), `parse_utc_offset` (`±HH:MM` → `timedelta`, hours ≤ 23, minutes ≤ 59), `parse_yes_no` (blank = no), `parse_path` (strip whitespace and one pair of matching quotes; on POSIX also undo backslash-escaped spaces `My\ File.csv` produced by macOS Terminal drag-and-drop). No float conversion.
  - **Tests**: table-driven valid/invalid cases; parity test: for a list of timestamp and amount samples, `parse_datetime`/`parse_amount` accept exactly what `SalesValidator.validate` accepts.
  - **Done when**: tests pass; commit `feat: add terminal input parsing`.

- [ ] T007 [P] Implement display primitives in src/sales_data_analyzer/cli/formatting.py
  - **Files**: `src/sales_data_analyzer/cli/formatting.py`, `tests/test_cli_formatting.py`
  - **Acceptance**: `format_money(Decimal) -> str` (`ROUND_HALF_UP` to 0.01, thousands separator: `1,050.00`, negative as `-3.00`); `format_percent(Decimal | None)` (ratio → one decimal `59.9%`, `None` → `n/a`); `format_optional_money` (`None` → `n/a`); `format_float(float)` two decimals. Input values are never mutated.
  - **Tests**: rounding half-up boundary (`0.005` → `0.01`), large values, negatives, `None`.
  - **Done when**: tests pass; commit `feat: add result formatting primitives`.

- [ ] T008 Implement the menu shell and entry points in src/sales_data_analyzer/cli/menu.py
  - **Files**: `src/sales_data_analyzer/cli/menu.py`, `src/sales_data_analyzer/cli/__init__.py` (`run() -> int`), `src/sales_data_analyzer/__init__.py` (`main()` calls `cli.run()`), `src/sales_data_analyzer/__main__.py`, `main.py` (delegate, decision D3), `tests/test_cli_menu.py`
  - **Acceptance**: `TerminalMenu(session, input_fn=input, output_fn=print)`; banner and data-loss notice at start (FR-001); header line per contracts/terminal-menu.md; numbered options 0–12 with handlers not yet implemented printing `Not done: create or select a company first.` when no company; invalid option message (FR-029); exit asks confirmation (FR-005); `EOFError`/`KeyboardInterrupt` print the notice and return 0; any other exception in a handler prints `Unexpected error (<ExceptionType>). Your data is unchanged.` (type name only, no message) and the loop continues. stdout/stdin reconfigured to UTF-8 when supported.
  - **Tests**: scripted sessions: start → exit `y`; exit `n` keeps running; invalid option; EOF; handler raising `RuntimeError("secret/path")` keeps the loop alive and the message text is not printed.
  - **Done when**: `uv run sales-data-analyzer` and `uv run python -m sales_data_analyzer` show the menu and exit cleanly; commit `feat: add terminal menu shell and entry points`.

**Checkpoint**: menu starts and exits on all OSes; user stories can begin.

---

## Phase 3: User Story 1 - Start a session and manage companies (P1) 🎯 MVP

**Goal**: create, list and select companies with in-memory notice.

**Independent Test**: create two companies, select the second, header shows it, exit with confirmation.

- [ ] T009 [US1] Implement SalesSession company management in src/sales_data_analyzer/application/session.py
  - **Files**: `src/sales_data_analyzer/application/session.py`, `src/sales_data_analyzer/application/workspace.py` (constructor + `company` only), `tests/test_application_session.py`
  - **Acceptance**: `create_company(name, sector)` validates through `Company`, rejects duplicate names "unique case-insensitively after trim" with `DuplicateCompanyError`, selects the new workspace; `select_company(index)` 1-based, out of range → `CompanyNotFoundError`; `require_current()` → `NoCompanySelectedError`; selection resets to all data on company change; refused calls leave state unchanged.
  - **Tests**: FR-002, FR-003, FR-004 cases incl. `" coffee shop "` duplicate, index 0 and len+1, state equality after refusal.
  - **Done when**: tests pass; commit `feat: add in-memory session with company selection`.

- [ ] T010 [US1] Wire options 1–2 and the company guard in src/sales_data_analyzer/cli/menu.py
  - **Files**: `src/sales_data_analyzer/cli/menu.py`, `tests/test_cli_menu.py`
  - **Acceptance**: option 1 prompts name and sector, prints `Company created and selected: <name>`; option 2 lists `n. name (sector)` and selects by number; empty list → `No companies yet.`; header updates; options 3–12 guarded (FR-004).
  - **Tests**: User Story 1 acceptance scenarios 1–6 as scripted sessions.
  - **Done when**: US1 independent test passes in a scripted session; commit `feat: create and select companies from the menu`.

**Checkpoint**: MVP — a usable session with companies.

---

## Phase 4: User Story 2 - Import sales from CSV (P1)

**Goal**: atomic import into the selected company with the repeated-import and catalog policies.

**Independent Test**: import `valid_sales.csv` (2 sales, 3 items, 2 new products); import again → refused, data unchanged.

- [ ] T011 [US2] Implement the company catalog core in src/sales_data_analyzer/application/workspace.py
  - **Files**: `src/sales_data_analyzer/application/workspace.py`, `tests/test_application_workspace.py`
  - **Acceptance**: `products` tuple ordered by ID; `register_product(product_id, name, category)` builds `Product(company=workspace.company)`, IDs trimmed, duplicates → `DuplicateProductError`; `find_product` trims and returns `None` when absent.
  - **Tests**: FR-006, FR-007; leading zeros preserved (`"007"` ≠ `"7"`); same ID in two companies allowed.
  - **Done when**: tests pass; commit `feat: add per-company product catalog`.

- [ ] T012 [US2] Implement `import_sales` with the merge policy in src/sales_data_analyzer/application/workspace.py
  - **Files**: `src/sales_data_analyzer/application/workspace.py`, `tests/test_application_workspace.py`, `tests/fixtures/catalog_conflict.csv`, `tests/fixtures/aware_sales.csv`
  - **Acceptance**: uses `CSVImporter` (injectable `DataImporter`); check order: duplicate sale IDs (all conflicting IDs collected) → catalog conflicts (same ID, different trimmed name or category, case-sensitive) → timestamp awareness vs existing sales; reuse identical catalog products by rebuilding each sale via `Sale.add_item` with the catalog object and the item's own quantity/price/cost; new products added to the catalog; candidate dataset + candidate catalog swapped only on success; returns `ImportSummary(sales_added, items_added, new_products, reused_products)`. `CSVImporter` and domain classes unchanged.
  - **Tests**: FR-011–FR-018: valid import counts; invalid file → `ImportValidationError`, state unchanged; re-import → `DuplicateSaleError` with IDs `("001","002")`, state unchanged; conflict → `CatalogConflictError(("007",))`; identical product reused (`item.product is catalog product`); aware file after naive data refused; historical prices equal file values; `sale.company is workspace.company`.
  - **Done when**: tests pass; commit `feat: import CSV into a company with duplicate and conflict policies`.

- [ ] T013 [US2] Wire option 7 (Import CSV) in src/sales_data_analyzer/cli/menu.py
  - **Files**: `src/sales_data_analyzer/cli/menu.py`, `src/sales_data_analyzer/cli/formatting.py`, `tests/test_cli_menu.py`, `tests/test_cli_formatting.py`
  - **Acceptance**: path via `parse_path`; success line `Imported N sales, M items. Products: X new, Y reused.`; `ImportValidationError` → `Import refused at line L, field F: reason.`; duplicate/conflict errors list up to five IDs taken from the error attributes, plus `and N more`; missing/unreadable file → `Import refused: cannot read file.` (line omitted when the importer reports line 0).
  - **Tests**: User Story 2 scenarios 1–6 scripted; quoted path with spaces.
  - **Done when**: quickstart scenario A steps 1, 2 and 4 pass; commit `feat: import CSV from the terminal menu`.

**Checkpoint**: data can be loaded; analyses can follow.

---

## Phase 5: User Story 3 - Run analyses on all data or a period (P1)

**Goal**: period selection and readable financial/product results.

**Independent Test**: after importing the fixture, revenue 45.40 / cost 18.20 / profit 27.20; period 2026-01-02..2026-01-02 → revenue 5.00.

- [ ] T014 [US3] Implement Selection and period filtering in src/sales_data_analyzer/application/session.py
  - **Files**: `src/sales_data_analyzer/application/session.py`, `tests/test_application_session.py`
  - **Acceptance**: `Selection(start: date | None, end: date | None)` "both set or both None; start <= end"; `set_period` start > end → `InvalidPeriodError` keeping previous selection; `selected_sales()` uses `filter_period(start 00:00, end + 1 day 00:00)`, with `tzinfo=timezone.utc` when data is aware; `data_is_aware()`.
  - **Tests**: inclusive end day; empty result; naive and aware datasets; refusal keeps previous selection.
  - **Done when**: tests pass; commit `feat: select all data or an inclusive date period`.

- [ ] T015 [US3] Add analysis use cases to SalesSession in src/sales_data_analyzer/application/session.py
  - **Files**: `src/sales_data_analyzer/application/session.py`, `tests/test_application_session.py`
  - **Acceptance**: `run_financial_analysis()` / `run_product_analysis()` call existing `FinancialAnalysis`/`ProductAnalysis` on `selected_sales()`; require a company.
  - **Tests**: values equal direct analysis calls; empty selection gives zero totals and `None` ratios.
  - **Done when**: tests pass; commit `feat: run financial and product analyses on the selection`.

- [ ] T016 [US3] Format financial and product results in src/sales_data_analyzer/cli/formatting.py
  - **Files**: `src/sales_data_analyzer/cli/formatting.py`, `tests/test_cli_formatting.py`
  - **Acceptance**: layouts from contracts/terminal-menu.md; product table joins catalog names by ID (unknown name → `?`); top five by quantity and revenue (existing ranking order); header with company, selection description and sale count.
  - **Tests**: golden strings for the fixture; empty dataset (`n/a` ratios, `No products sold.`).
  - **Done when**: tests pass; commit `feat: format analysis results for the terminal`.

- [ ] T017 [US3] Wire options 8–11 in src/sales_data_analyzer/cli/menu.py
  - **Files**: `src/sales_data_analyzer/cli/menu.py`, `tests/test_cli_menu.py`
  - **Acceptance**: option 8 asks start/end dates (re-ask invalid format, `Not done` for end < start); option 9 clears; header shows `Selection: 2026-01-02 to 2026-01-02 (1 sale)`; for aware data the period prompt says dates are UTC; options 10/11 print formatted results.
  - **Tests**: User Story 3 scenarios 1–6 scripted.
  - **Done when**: quickstart scenario A steps 3 and 5 pass; commit `feat: period selection and analyses in the terminal menu`.

**Checkpoint**: the three P1 stories form a complete, demonstrable level 2 core.

---

## Phase 6: User Story 4 - Register products and record sales manually (P2)

**Goal**: catalog and manual sales from the menu.

**Independent Test**: register two products, list, find one, record a two-item sale (total 26.00, cost 10.00), see it in the financial analysis.

- [ ] T018 [US4] Implement `record_sale` and `ItemInput` in src/sales_data_analyzer/application/workspace.py
  - **Files**: `src/sales_data_analyzer/application/workspace.py`, `tests/test_application_workspace.py`
  - **Acceptance**: `ItemInput(product_id, quantity, unit_price, unit_cost)` frozen; `has_sale(sale_id) -> bool` (trimmed) for the menu's early check; aware date-times normalized to UTC like the importer; checks in order: duplicate sale ID → `DuplicateSaleError`, empty items → `EmptySaleError`, unknown product → `UnknownProductError`, awareness mismatch → `TimestampAwarenessError`; item value errors from `SaleItem` propagate; candidate dataset swap.
  - **Tests**: FR-008–FR-010; totals 26.00/10.00 exactly; each refusal leaves state unchanged; a later catalog product with the same values does not affect stored items.
  - **Done when**: tests pass; commit `feat: record manual sales with catalog products`.

- [ ] T019 [US4] Wire options 3–5 (products) in src/sales_data_analyzer/cli/menu.py
  - **Files**: `src/sales_data_analyzer/cli/menu.py`, `src/sales_data_analyzer/cli/formatting.py`, `tests/test_cli_menu.py`
  - **Acceptance**: register prompts ID/name/category; list prints `ID  Name  Category` ordered by ID or `Catalog is empty.`; find prints details or `Product <id> not found.`
  - **Tests**: User Story 4 scenarios 1–3.
  - **Done when**: tests pass; commit `feat: manage the product catalog from the menu`.

- [ ] T020 [US4] Wire option 6 (record sale) in src/sales_data_analyzer/cli/menu.py
  - **Files**: `src/sales_data_analyzer/cli/menu.py`, `tests/test_cli_menu.py`
  - **Acceptance**: empty catalog → message (scenario 8); asks sale ID first and refuses an existing ID before items (scenario 5); item loop per contracts (blank product ID finishes); invalid item values re-asked (scenario 6); no items → nothing stored (scenario 7); success prints `Sale S-1 recorded: 2 items, total 26.00.`
  - **Tests**: User Story 4 scenarios 4–8 scripted.
  - **Done when**: US4 independent test passes; commit `feat: record sales from the terminal menu`.

**Checkpoint**: all data entry paths available.

---

## Phase 7: User Story 5 - Forecast revenue with stated limitations (P3)

**Goal**: expose the existing forecaster with clear explanations.

**Independent Test**: 14-day fixture → errors, 7 future days, limitations; 2-day fixture → insufficient history message.

- [ ] T021 [US5] Add `run_forecast` to SalesSession in src/sales_data_analyzer/application/session.py
  - **Files**: `src/sales_data_analyzer/application/session.py`, `tests/test_application_session.py`, `tests/fixtures/forecast_14_days.csv`
  - **Acceptance**: passes horizon/test_days/missing_days to `RevenueForecaster.forecast`; aware data requires `utc_offset` (→ `timezone(utc_offset)`), naive data ignores it; empty selection raises `NoSalesInSelectionError` (new `ApplicationError` subclass) before calling the forecaster; for insufficient history the session attaches `available_days = len(daily_revenue(data, missing_days="zero", timezone=...))` and `required_days = 5 + test_days` to an `InsufficientHistoryError` (new subclass) checked before the missing-days check; other forecaster `ValueError`s propagate unchanged; fixture: 14 consecutive days, revenue 10..140 like the existing example.
  - **Tests**: fixture result matches `examples/analysis_and_forecast.py` predictions (150, 160, 170 for horizon 3, test_days 3); empty selection, short history (with and without gaps, exact counts) and missing days; forecaster message strings pinned in tests so upstream wording changes are caught.
  - **Done when**: tests pass; commit `feat: run the revenue forecast on the selection`.

- [ ] T022 [US5] Format forecast results and explain forecast errors in src/sales_data_analyzer/cli/formatting.py
  - **Files**: `src/sales_data_analyzer/cli/formatting.py`, `tests/test_cli_formatting.py`
  - **Acceptance**: layout and limitations text from contracts/terminal-menu.md (FR-024, FR-025); `explain_forecast_error(error) -> str` maps `InsufficientHistoryError` (using its counts) and the forecaster messages to the table in the contract (FR-026), falling back to the original message.
  - **Tests**: golden output; one test per mapped condition; "better" line for model, baseline and tie.
  - **Done when**: tests pass; commit `feat: explain forecast results and limitations`.

- [ ] T023 [US5] Wire option 12 (forecast) in src/sales_data_analyzer/cli/menu.py
  - **Files**: `src/sales_data_analyzer/cli/menu.py`, `tests/test_cli_menu.py`
  - **Acceptance**: prompts horizon (1–365) and test days (blank = defaults; test days < 2 or horizon outside 1–365 re-asked); offset prompt only for aware data (FR-028); on missing-days error asks the confirmation and retries with `missing_days="zero"` only on `y` (FR-027); empty selection → `No sales in the current selection.`
  - **Tests**: User Story 5 scenarios 1–6 scripted.
  - **Done when**: quickstart scenario C passes; commit `feat: revenue forecast from the terminal menu`.

**Checkpoint**: all level 2 operations available.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T024 End-to-end subprocess test in tests/test_cli_end_to_end.py
  - **Files**: `tests/test_cli_end_to_end.py`
  - **Acceptance**: runs `[sys.executable, "-m", "sales_data_analyzer"]` with scripted stdin covering quickstart scenario A plus invalid inputs (SC-004), `env` with `PYTHONPATH` to `src`, `encoding="utf-8"`, timeout; asserts exit code 0, values 45.40/18.20/27.20, refused re-import, no `Traceback` in output.
  - **Tests**: itself; green in CI on all three OSes (SC-006).
  - **Done when**: CI green; commit `test: add end-to-end terminal session`.

- [ ] T025 [P] Update README for level 2 in README.md
  - **Files**: `README.md`, `docs/product-vision.md` (current state table)
  - **Acceptance**: "Running the terminal menu" section (macOS and Windows commands), import policies summary, in-memory notice, updated test command and count, roadmap tick for level 2, tech stack mentions Ruff and CI.
  - **Tests**: commands in README executed verbatim by `/project-verification`.
  - **Done when**: commit `docs: document the level 2 terminal menu`.

- [ ] T026 [P] Model the application and terminal layers in docs/diagrams/level-two.drawio
  - **Files**: `docs/diagrams/level-two.drawio`, `docs/diagrams/level-two.svg`
  - **Acceptance**: classes `SalesSession`, `CompanyWorkspace`, `Selection`, `ItemInput`, `ImportSummary`, `TerminalMenu`, error hierarchy; associations to existing domain/analysis/forecast classes; dependency arrows only downward; matches public methods in code.
  - **Tests**: `/pre-pr-review` UML step finds no mismatch.
  - **Done when**: commit `docs: add level 2 UML for application and terminal layers`.

- [ ] T027 Final verification and pull request preparation
  - **Files**: `specs/001-terminal-menu/tasks.md` (all `[X]`), PR description draft
  - **Acceptance**: `/project-verification`, `/domain-review`, `/pre-pr-review` report no blocking item; quickstart scenarios A–C run manually on macOS (and Windows when available); `/speckit-analyze` and `/speckit-converge` report no gaps.
  - **Tests**: full suite + CI green.
  - **Done when**: maintainer approves opening the `dev → main` PR; merge only with the maintainer's authorization.

---

## Dependencies & Execution Order

```text
T001 → T002 → T004
T001 → T003 → T004
T005 → T009 → T010 → (US1 done)
T005, T006, T007 (T006/T007 parallel) → T008 → T010; T009 needs T005
T009 → T011 → T012 → T013            (US2; T013 also needs T008)
T009 → T014 → T015 → T017; T007 → T016 → T017; T013 → T017   (US3)
T011 → T018 → T020; T011, T008 → T019 → T020   (US4; all edit cli/menu.py sequentially)
T012, T014 → T021 → T023; T007 → T022 → T023; T013 → T023   (US5)
T013, T017, T020, T023 → T024 → T027
T025, T026 any time after T023 → T027
```

User stories: US1 is the base. US2 and US4 both depend on the catalog core
(T011). US3 depends on data (US2 or US4); its tests use the import. US5 depends
on selection (T014).

## Parallel Example: Phase 2

```text
T006 cli/parsing.py      ┐
T007 cli/formatting.py   ┘ → T008 menu shell
```

Only one task edits `cli/menu.py` at a time; parallel work never touches the
same file.

## Requirement traceability

| Requirement | Tasks |
| --- | --- |
| FR-001, FR-005, FR-029 | T008, T024 |
| FR-002–FR-004 | T009, T010 |
| FR-006, FR-007 | T011, T019 |
| FR-008–FR-010 | T018, T020 |
| FR-011–FR-018 | T012, T013 |
| FR-019 | T014, T017 |
| FR-020–FR-022 | T007, T015, T016, T017 |
| FR-023–FR-028 | T021, T022, T023 |
| FR-030 | T001, T002, T008, T024 |
| SC-001–SC-006 | T024, T027 (manual quickstart) |

## Implementation Strategy

1. Phase 1 (tooling) as small `chore`/`ci`/`test` commits; CI must be green
   before feature code.
2. MVP = Phase 2 + US1. Demonstrable: start, create, select, exit.
3. Add US2 and US3 → the level 2 core (import + analyses); stop and validate
   with quickstart scenario A.
4. US4, then US5, each validated independently.
5. Polish, verification skills, then the `dev → main` PR on approval.

## Notes

- One task ≈ one commit; tests in the same commit as the code they cover.
- Never format existing level 1 files in these commits (decision D4).
- Do not modify `domain/`, `importing/`, `analysis/` or `forecasting/`; if a
  task seems to need it, stop and update the plan first.
