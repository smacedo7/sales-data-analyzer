---
name: project-verification
description: Run the real test suite and executable examples of Sales Data Analyzer and report exact results and limitations. Use after any code change, before /pre-pr-review, or when asked "does it still work?".
---

# Project verification

Verify the project by running it, never by assuming. Report what ran, what
passed, what failed and what could not be checked.

## Steps

1. From the repository root, confirm the environment:
   `uv sync --locked` (do not change `uv.lock`; if the lock is stale, report it).
2. Run the full suite and record the test count and result:
   `PYTHONPATH=src uv run python -m unittest discover -s tests -v`
3. Run every script in `examples/` and compare with the documented outputs:
   - `examples/import_and_analyze.py`: 2 sales, 3 items, revenue 45.40,
     cost 18.20, gross profit 27.20.
   - `examples/analysis_and_forecast.py`: revenue 1050, cost 420, gross
     profit 630, margin 0.6, average order value 75, three future predictions.
4. If a terminal entry point exists (level 2+), run it non-interactively by
   piping a scripted session through stdin and check the exit code.
5. If Ruff is configured in `pyproject.toml`, run `uv run ruff check .` and
   `uv run ruff format --check .`.

On Windows PowerShell set `$env:PYTHONPATH = "src"` instead of the prefix.

## Report format

- Environment: Python version (`uv run python --version`), OS.
- Tests: `N run, OK` or the failing test names with the first error line.
- Examples: matched / differed (show the differing values).
- Limitations: anything skipped (no network, missing tool, manual UI step).

## Rules

- Do not edit source or tests to make checks pass; report failures instead.
- Do not commit, push or merge.
