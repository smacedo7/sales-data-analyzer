# Implementation Plan: Functional Terminal Menu (Level 2)

**Branch**: `dev` | **Date**: 2026-10-11 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-terminal-menu/spec.md`

## Summary

Add a thin **application layer** (session state, company workspaces with a
product catalog, import merge policy) and a **terminal adapter** (menu loop,
prompts, formatting) on top of the unchanged level 1 packages. The menu is
started by the existing console script `sales-data-analyzer` and by
`python -m sales_data_analyzer`. Alongside the feature, add GitHub Actions CI
(tests on Ubuntu, macOS and Windows) and introduce Ruff in separate commits.

## Technical Context

**Language/Version**: Python 3.14 (`requires-python >=3.14`, uv-managed)

**Primary Dependencies**: standard library only for the new code; existing
scikit-learn stays a lazy import of the forecast. Ruff added as a development
dependency group (not a runtime dependency).

**Storage**: in memory only (one `SalesSession` object per run)

**Testing**: `unittest`; terminal tests inject input/output callables; one
end-to-end test runs the module in a subprocess with scripted stdin.

**Target Platform**: macOS and Windows terminals (Linux in CI)

**Project Type**: single-package desktop/terminal application (`src/` layout)

**Performance Goals**: interactive; importing a 10k-row CSV completes in a few
seconds (current importer is linear)

**Constraints**: no new runtime dependency; UTF-8 I/O; `pathlib` paths;
no shell-specific behaviour

**Scale/Scope**: one user, tens of companies, up to ~100k items per session

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
| --- | --- | --- |
| I. Exact and historical accounting | Amounts parsed straight to `Decimal`; display rounding only in `cli/formatting.py`; items keep their own price/cost; import and manual sale are applied to a candidate dataset and swapped only on success | Pass |
| II. Independent domain, thin adapters | No change to `domain/`; new `application/` imports domain, importing, analysis, forecasting; `cli/` is the only place with `input`/`print` | Pass |
| III. Tested increments | Each task lists tests; application tests are pure; menu tests use scripted I/O; CI runs all on 3 OSes | Pass |
| IV. Typed, documented, modeled | New modules typed and documented; UML gets a "Level 2" page; README updated | Pass |
| V. Incremental scope | Only exposes existing operations; edit/delete, persistence, charts excluded; no new runtime dependency | Pass |
| Workflow | Work on `dev`; no branch automation; Ruff introduced in dedicated commits; CI task included | Pass |

Post-design re-check (after data-model and contracts and the independent
analysis): still passes — existing files touched are `__init__.py` (entry
point), `main.py`, one test's subprocess environment, `pyproject.toml`/
`uv.lock` (dev group), README, `docs/product-vision.md`, `CLAUDE.md`, the
project-verification skill, a PATCH amendment of the constitution's test
command, and the UML. Error messages carry counts only (Principle IV).

## Architecture

```text
            ┌──────────────────────────── cli/ (adapter) ───────────────────────────┐
 stdin ───► │ TerminalMenu: menu loop, prompts, parsing of typed text, error display │ ───► stdout
            │ formatting: money/percent/tables/forecast text (pure functions)        │
            └───────────────┬───────────────────────────────────────────────────────┘
                            │ calls (typed arguments, Decimal/datetime/str)
            ┌───────────────▼──────────── application/ ─────────────────────────────┐
            │ SalesSession: companies, selected workspace, active period             │
            │ CompanyWorkspace: catalog, sales, register_product, record_sale,        │
            │                   import_sales (merge policy)                           │
            │ errors: ApplicationError + subclasses                                   │
            └───────┬───────────────┬───────────────────┬──────────────┬─────────────┘
                    │               │                   │              │
                domain/        importing/          analysis/     forecasting/   (unchanged)
```

- Dependencies point downwards only. `application/` never prints or reads
  input, so levels 3 (SQLite) and 4 (PySide6) can reuse it.
- `cli/` converts text to typed values (`Decimal`, `datetime`, `int`) and
  passes them to the application; domain/application exceptions come back and
  are rendered as one-line messages.
- No repository/ORM abstraction yet (YAGNI): persistence in level 3 will add
  one behind `CompanyWorkspace` if needed.

### Error flow

| Origin | Exception | Rendered by menu as |
| --- | --- | --- |
| Typed-text parsing in `cli/` | `InputError` (local to cli) | "Invalid value: <reason>. Expected <format>." then re-prompt |
| Application rule (duplicate, conflict, no company, history) | `ApplicationError` subclasses (messages hold counts only; IDs/counts in attributes) | "Not done: <reason>." with IDs from attributes; menu continues |
| Domain validation | `TypeError` / `ValueError` from domain | "Not done: <message>." |
| CSV validation | `ImportValidationError` | "Import refused at line L, field F: reason." |
| Forecast preconditions | `ValueError` from forecaster | Mapped to plain-language explanation (see contracts) |
| Unexpected | `Exception` | "Unexpected error (<type>). Your data is unchanged." (no message text) |
| EOF / Ctrl+C | `EOFError` / `KeyboardInterrupt` | Data-loss notice, exit code 0 |

Atomicity is guaranteed by building a new candidate `SalesDataset` (existing
sales + new ones) and a candidate catalog, swapping them in only after every
check passes.

## Project Structure

### Documentation (this feature)

```text
specs/001-terminal-menu/
├── spec.md
├── plan.md               # this file
├── research.md           # decisions and alternatives
├── data-model.md         # session/workspace entities and rules
├── quickstart.md         # how to validate the feature end to end
├── contracts/
│   ├── application-api.md
│   └── terminal-menu.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/sales_data_analyzer/
├── __init__.py            # main() now starts the terminal menu
├── __main__.py            # NEW: python -m sales_data_analyzer
├── domain/                # unchanged
├── importing/             # unchanged
├── analysis/              # unchanged
├── forecasting/           # unchanged
├── application/           # NEW
│   ├── __init__.py        # public exports
│   ├── errors.py          # ApplicationError hierarchy
│   ├── workspace.py       # CompanyWorkspace, ItemInput, ImportSummary
│   └── session.py         # SalesSession, Selection
└── cli/                   # NEW
    ├── __init__.py        # run(argv) entry
    ├── parsing.py         # text -> Decimal/int/date/datetime/offset, InputError
    ├── formatting.py      # results -> text
    └── menu.py            # TerminalMenu (injected input/output)

tests/
├── test_application_session.py     # NEW
├── test_application_workspace.py   # NEW
├── test_cli_parsing.py             # NEW
├── test_cli_formatting.py          # NEW
├── test_cli_menu.py                # NEW (scripted sessions)
├── test_cli_end_to_end.py          # NEW (subprocess, stdin)
└── fixtures/                       # + catalog_conflict.csv, forecast_14_days.csv
.github/workflows/tests.yml         # NEW
```

**Structure Decision**: single `src/` package. New code lives in two new
subpackages; existing subpackages are not moved or rewritten. The scratch
`main.py` at the root delegates to the new entry point (decision D3).

## Cross-platform execution

- Start: `uv run sales-data-analyzer` (console script already declared in
  `pyproject.toml`) — identical on macOS and Windows. Alternative:
  `uv run python -m sales_data_analyzer`.
- Tests: `uv run python -m unittest discover -s tests -v`. Task T001 makes the
  one subprocess test set `PYTHONPATH` itself, so the `PYTHONPATH=src` prefix
  (PowerShell needs `$env:PYTHONPATH="src"; ...` instead) is no longer required.
- Paths typed by the user are passed to `pathlib.Path` after stripping
  surrounding quotes (Windows drag-and-drop adds quotes) and, on macOS/Linux,
  undoing backslash-escaped spaces (macOS Terminal drag-and-drop).
- Output is plain ASCII/UTF-8 text without colours or box-drawing characters
  (safe in Windows `cmd`/PowerShell defaults); stdin/stdout are reconfigured to
  UTF-8 when possible.
- Time-zone grouping uses fixed UTC offsets (`datetime.timezone`), which need no
  time-zone database (Windows has none without the `tzdata` package).

## Testing strategy

| Layer | Kind | Technique |
| --- | --- | --- |
| application | unit | Build domain objects directly; assert state before/after each refused operation is identical (atomicity) |
| cli/parsing | unit | Table-driven valid/invalid strings |
| cli/formatting | unit | Fixed results → exact expected text (golden strings) |
| cli/menu | integration | `TerminalMenu(input_fn=iter(lines).__next__, output_fn=list.append)`; assert key lines |
| entry point | end-to-end | `subprocess.run([sys.executable, "-m", "sales_data_analyzer"], input=script, env=PYTHONPATH)`; exit code 0, sample values present |
| existing | regression | Full current suite (42 tests) stays green |

Coverage goal: every FR has at least one test (traceability in tasks.md).

## CI plan

`.github/workflows/tests.yml`: on `pull_request` (to `main` and `dev`) and
`push` to `dev`; matrix `ubuntu-latest`, `macos-latest`, `windows-latest`;
steps: checkout → `astral-sh/setup-uv` (pinned major) with Python 3.14 →
`uv sync --locked` → `uv run python -m unittest discover -s tests -v` →
`uv run ruff check .` (after T004). No secrets needed.

## Ruff introduction

1. T003 (`chore:`): add Ruff to a `dev` dependency group, minimal config
   (`target-version = "py314"`, `line-length = 100`, rules `E4,E7,E9,F,B`),
   run `ruff check`. Import sorting (`I`) is deferred to the style PR because
   it would reorder imports in `domain/` and `importing/`.
2. T004 (`ci:`): add `ruff check .` to CI.
3. New packages (`application/`, `cli/`, new tests) are written
   Ruff-formatted from the start; CI checks `ruff format --check` on those
   paths only.
4. Formatting the existing level 1 files is a separate `style:` pull request
   after level 2 is merged (decision D4), so the level 1 diff evidence stays
   readable and no feature commit mixes formatting.

## Open decisions (defaults applied; see research.md)

| ID | Decision | Default taken |
| --- | --- | --- |
| D1 | Menu text language | English (repository policy); Portuguese possible via a single strings module later |
| D2 | Repeated import / duplicate IDs / catalog conflicts | Refuse whole import (FR-013, FR-015); reuse identical products (FR-014) |
| D3 | Root `main.py` scratch script | Replace with a 3-line delegate to the entry point |
| D4 | When to format existing files with Ruff | Separate `style:` PR after level 2 merge |
| D5 | Duplicate company names | Refused, case-insensitive |

## Complexity Tracking

No constitution violations. Not applicable.
