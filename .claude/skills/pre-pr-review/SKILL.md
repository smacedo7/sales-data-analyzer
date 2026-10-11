---
name: pre-pr-review
description: Final review of the dev branch before opening a pull request to main - diff scope, tests, documentation and UML correspondence. Use when the user asks to prepare or check a PR.
---

# Pre-PR review

Produce a go / no-go report for the branch about to be proposed. This skill
never opens, pushes or merges anything; it ends with a draft PR description
for the user to approve.

## Steps

1. Scope: `git fetch origin main` then `git diff --stat origin/main...HEAD`
   and `git log --oneline origin/main..HEAD`.
   - Every changed file must map to a task in the active
     `specs/NNN-*/tasks.md` (or be tooling/docs explicitly planned).
   - Flag unrelated changes, mass reformatting mixed with features, generated
     files, secrets, `.env`, large data files.
2. Tasks: all tasks of the increment are `[X]`; unchecked ones are listed.
3. Verification: run the `project-verification` skill and include its result.
4. Domain: if domain/import/analysis/forecasting/application code changed,
   run the `domain-review` skill and include blocking findings.
5. Tests: each new public behaviour has at least one test; error paths in the
   spec's acceptance criteria are tested.
6. Documentation: README commands still work; new public classes have
   docstrings; spec/plan updated if behaviour diverged.
7. UML: compare new or changed classes, relationships and public methods
   against `docs/diagrams/level-one.drawio` (and its SVG previews). List
   classes missing from the diagram or diagram elements no longer in code.
8. For a deeper bug hunt, suggest the built-in `/code-review` command
   instead of duplicating it here.

## Output

- Verdict: ready / not ready, with the blocking items first.
- Checklist results (scope, tasks, tests, domain, docs, UML).
- Draft PR title and body (English): Before / After / How, linked spec.

## Rules

- Do not commit, push, open PRs or merge. The maintainer approves each step.
