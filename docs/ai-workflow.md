# AI-assisted workflow (Claude Code + Spec Kit)

## What is installed

- **Spec Kit 1.1.3** (`specify-cli`, pinned tag `v1.1.3`) with the official
  `claude` integration and Python helper scripts (`--script py`).
  - Skills: `.claude/skills/speckit-*/` (constitution, specify, clarify, plan,
    checklist, tasks, analyze, implement, converge, taskstoissues).
  - Shared files: `.specify/` (templates, scripts, constitution, manifests).
  - The optional **git extension is not installed**, so no Spec Kit skill
    creates or switches branches. Work stays on `dev`.
- **Project skills** (`.claude/skills/`): `project-verification`,
  `domain-review`, `pre-pr-review`. None pushes or merges.
- **`.claude/settings.json`**: denies force push, `git reset --hard` and reading
  `.env` files. Personal settings go in `.claude/settings.local.json` (ignored).
- **`CLAUDE.md`**: short operating guide loaded by Claude Code in every session.

No MCP servers, hooks or third-party plugins were added.

## Install the Spec Kit CLI (only needed to upgrade or re-run `specify`)

The skills are committed, so day-to-day use needs only Claude Code. To manage
Spec Kit itself:

```sh
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@v1.1.3
specify version          # expect 1.1.3
specify integration status
```

The command is the same on macOS and Windows (uv installs `specify` on PATH).

### Windows note

The generated skills call helper scripts with `.venv/bin/python` (the macOS/
Linux virtualenv layout detected at install time). On Windows the virtualenv
interpreter is `.venv\Scripts\python.exe`. If you run Claude Code on Windows,
regenerate the integration locally after `uv sync --locked`:

```powershell
specify integration upgrade claude --script py
```

Review the diff before committing; on macOS nothing needs to change.

## Feature cycle

Run these in Claude Code from the repository root, on `dev`:

```text
/speckit-specify <what and why>     -> specs/NNN-name/spec.md
/speckit-clarify                    -> resolves open questions in spec.md
/speckit-plan <technical direction> -> plan.md, research.md, data-model.md, contracts/, quickstart.md
/speckit-tasks                      -> tasks.md
/speckit-analyze                    -> read-only consistency report
/speckit-implement                  -> executes tasks.md (only after approval)
/speckit-converge                   -> appends any remaining work as tasks
/project-verification, /domain-review, /pre-pr-review
```

The active feature is recorded in `.specify/feature.json` (machine-local,
ignored by git). To switch feature, edit that file or re-run
`/speckit-specify`.

## Upgrading Spec Kit

```sh
specify self check                       # read-only: is a newer release out?
uv tool install --force specify-cli --from git+https://github.com/github/spec-kit.git@vX.Y.Z
specify integration upgrade claude --script py
```

Record the new version here and in `CLAUDE.md`.
