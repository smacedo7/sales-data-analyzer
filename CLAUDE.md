# Sales Data Analyzer — guidance for Claude Code

Python 3.14 sales analytics project (UnB OOP course + data portfolio).
Governing principles: `.specify/memory/constitution.md`. Product vision and
roadmap: `docs/product-vision.md`. Read the constitution before planning work.

## Language

- Code, docstrings, technical docs, commit messages and PR text: **English**.
- Explanations to the maintainer (samuel) in chat: **Portuguese**, explaining
  the reasoning behind decisions — the maintainer is learning.

## Verified commands (run from the repository root)

```sh
uv sync --locked                                    # install
uv run python -m unittest discover -s tests -v      # tests
uv run python examples/import_and_analyze.py        # CSV demo
uv run python examples/analysis_and_forecast.py     # forecast demo
```

The same commands work in macOS/Linux shells and Windows PowerShell; no
`PYTHONPATH` is needed (uv installs the package in editable mode). The older
`PYTHONPATH=src` prefix in level 1 documents still works.
No linter or CI exists yet (planned in `specs/001-terminal-menu/plan.md`).

## Domain rules (do not break)

- Money is `Decimal` end to end. Never convert amounts to `float` except at
  the ML boundary in `forecasting/`.
- `SaleItem` stores historical `unit_price`/`unit_cost`; catalog changes must
  never rewrite past sales.
- Identity: `Company` by object identity (auto id); `Product` by string ID
  scoped to one company; `Sale` ID unique per `SalesDataset`. IDs stay strings
  (leading zeros matter).
- Composition: `Sale` creates and owns its `SaleItem`s via `add_item`.
  Association: `SalesDataset` shares (does not copy) `Sale` objects.
- `domain/` depends only on the standard library: no UI, persistence, pandas
  or scikit-learn imports. `input()`/`print()` belong only in the terminal layer.
- Imports are atomic: a failed import leaves no partial state.

## Code standards

- Type hints on every new public function/method; useful English docstrings
  on new modules, classes and public methods.
- Tests (`unittest`) proportional to each change: happy path, validation
  errors and edge cases. No real sales data in fixtures.
- Prefer reuse over rewrites; do not restructure stable classes only to move
  folders. Keep diffs focused; no mass reformatting mixed with features.
- Update the UML (`docs/diagrams/`) and README when public structure changes.

## Git workflow

- Integration branch: `dev` (from `main`). Feature work happens on `dev` or on
  short branches from `dev`; final PR is `dev → main`.
- Spec Kit is installed **without** its git extension, so `/speckit-*` skills
  never create or switch branches. Do not create/switch branches unless asked.
- Never force push, `reset --hard`, auto-stash, or merge without explicit
  maintainer approval. Never commit credentials or `.env` files.
- Commit style: Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).

## Workflow tools

- Spec Kit 1.1.3 skills: `/speckit-constitution`, `/speckit-specify`,
  `/speckit-clarify`, `/speckit-plan`, `/speckit-checklist`, `/speckit-tasks`,
  `/speckit-analyze`, `/speckit-implement`, `/speckit-converge`.
  Features live in `specs/NNN-name/`; see `docs/ai-workflow.md`.
- Project skills: `/project-verification`, `/domain-review`, `/pre-pr-review`.
  None of them pushes or merges.
