# Sales Data Analyzer Constitution

## Core Principles

### I. Exact and Historical Accounting

- Monetary amounts MUST be `decimal.Decimal` from input to result. Conversion to
  `float` is allowed only at the statistical boundary inside `forecasting/`.
- Rounding for display MUST happen only in the presentation layer and MUST NOT
  feed back into calculations.
- Each sale item MUST keep the unit price and unit cost recorded at sale time.
  Catalog edits MUST NOT rewrite past sales.
- Imports MUST be atomic: a failed import leaves no partial state.

Rationale: sales metrics are only trustworthy if amounts are exact and history
is immutable; this is also the core OOP lesson of the level 1 delivery.

### II. Independent Domain, Thin Adapters

- `domain/` MUST depend only on the Python standard library. It MUST NOT import
  user interface, persistence, dataframe or Machine Learning libraries.
- Use cases that coordinate several domain objects belong to an application
  layer; parsing, terminal, files, database and GUI code belong to adapters.
- `input()` and `print()` MUST appear only in the terminal adapter.
- Stable classes MUST NOT be rewritten only to change folder structure; new
  layers wrap existing code.
- Third-party dependencies MUST be justified by a concrete feature in the
  current increment.

Rationale: the same domain must serve a terminal menu (level 2), SQLite
(level 3) and a PySide6 GUI (level 4) without changes to its rules.

### III. Tested Increments (NON-NEGOTIABLE)

- Every behavior change MUST ship with `unittest` tests proportional to the
  change: success path, validation errors and relevant edge cases.
- The full suite and every script in `examples/` MUST pass before a pull
  request is opened.
- Tests MUST use synthetic data only and MUST NOT need network access.
- A bug fix MUST include a test that fails without the fix.

Rationale: small verified increments are how a student project stays
demonstrable at every delivery.

### IV. Typed, Documented and Modeled

- New public functions, methods and classes MUST have type hints and an
  English docstring that states purpose and raised errors.
- Validation failures MUST raise `TypeError` for wrong types and `ValueError`
  (or a documented subclass) for invalid values, with messages that do not leak
  raw input values or file paths.
- The UML in `docs/diagrams/` and the README MUST be updated in the same pull
  request that changes public classes or relationships.
- Code, docstrings, technical docs, commits and pull requests are written in
  English.

Rationale: the course evaluates the correspondence between UML and code, and
the portfolio is read by English-speaking reviewers.

### V. Incremental Scope and Simplicity

- Work follows the roadmap levels in `docs/product-vision.md`; a level MUST NOT
  start before the previous one is merged into `main`.
- Each feature MUST be specified (`spec.md`), planned (`plan.md`) and broken
  into tasks (`tasks.md`) before implementation.
- Technologies MUST NOT be added only to lengthen the stack list (for example
  Spark, NLP or cloud services).
- Out of scope for the whole product: payments, invoice/tax document issuing,
  inventory control, payroll and full ERP features.
- Forecasts MUST be evaluated against a baseline and state their limitations.

Rationale: a focused product that works end to end is a stronger delivery and
portfolio piece than a broad, unfinished one.

## Technology and Quality Constraints

- Runtime: Python >= 3.14 managed by `uv`; `uv.lock` is committed and installs
  use `uv sync --locked`.
- Tests: standard library `unittest` (run with
  `PYTHONPATH=src uv run python -m unittest discover -s tests`).
- Current dependency: scikit-learn (forecasting only, imported lazily).
- Planned dependencies, each introduced only by the level that needs it:
  Matplotlib (charts), a PDF library (reports), SQLite via the standard library
  `sqlite3` (level 3) and PySide6 (level 4).
- Lint/format: Ruff, introduced in a dedicated tooling change; formatting of
  existing files MUST NOT be mixed with feature commits.
- The project MUST run on macOS and Windows: use `pathlib`, explicit UTF-8
  encodings and no shell-specific commands inside Python code.
- No credentials, personal data or real customer sales data in the repository.

## Development Workflow

- `main` holds only reviewed, delivered increments. `dev` is the integration
  branch, created from `main`; increments are developed on `dev` (optionally on
  short branches from `dev`) and proposed through a `dev → main` pull request.
- Spec Kit runs without its git extension: its skills MUST NOT create or switch
  branches. Feature artifacts live in `specs/NNN-short-name/`.
- Before a pull request: `/project-verification`, `/domain-review` (when
  domain-adjacent code changed) and `/pre-pr-review`.
- Continuous integration MUST run the test suite on every pull request once the
  CI task of level 2 is merged.
- Force pushes, `git reset --hard`, automatic stashes and merges without the
  maintainer's explicit approval are forbidden. Merging into `main` requires
  the maintainer's authorization.
- Commits follow Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`,
  `chore:`, `ci:`).

## Governance

This constitution supersedes conflicting guidance in other project documents.
`CLAUDE.md` holds day-to-day operational guidance and MUST stay consistent with
it.

- Amendments are proposed in a pull request that edits this file through
  `/speckit-constitution`, explains the reason and updates affected templates,
  `CLAUDE.md` and active specs.
- Versioning follows semantic versioning: MAJOR for removed or redefined
  principles, MINOR for new principles or materially expanded guidance, PATCH
  for clarifications.
- Every plan MUST include a Constitution Check; `/pre-pr-review` verifies
  compliance before a pull request. Justified exceptions are recorded in the
  plan's Complexity Tracking table.

**Version**: 1.0.0 | **Ratified**: 2026-10-11 | **Last Amended**: 2026-10-11
