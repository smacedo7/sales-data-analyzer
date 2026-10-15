# Consistency analysis (/speckit-analyze) — 2026-10-11

Run read-only by an independent reviewer against spec, plan, tasks, the
constitution and the actual code. 17 findings; all resolved in the artifacts
before maintainer review.

| ID | Sev | Finding | Resolution |
| --- | --- | --- | --- |
| C1 | Critical | Error messages would include file-supplied IDs and raw exception text (constitution IV) | Messages carry counts only; IDs in attributes; unexpected errors show the type only (T005, T008, T013, data-model, contracts) |
| H1 | High | Menu shell (T008) needed session state created later (T009) | Session skeleton moved into T005 |
| H2 | High | `[P]` tasks edited shared files | `[P]` removed from T016, T019, T022 |
| M1 | Medium | Test command change would diverge from the constitution | T001 includes a PATCH amendment (1.0.1) |
| M2 | Medium | Ruff rule `I` would edit `domain/`/`importing/` | `I` deferred to the style PR |
| M3 | Medium | Missing dependency edges | Graph updated |
| M4 | Medium | Forecaster cannot report available days; gap check runs first | Session checks empty selection and history length first, with counts |
| M5 | Medium | Unbounded horizon | Horizon 1–365 |
| M6 | Medium | macOS drag-and-drop escapes spaces with backslashes | `parse_path` undoes `\ ` on POSIX |
| M7 | Medium | UTC periods vs offset-based forecast days | Documented; agree by default (`+00:00`) |
| L1–L7 | Low | 9999-12-31 overflow, line 0 in file errors, early duplicate-sale check, check order, UTC normalization of manual sales, quickstart order, wording | Each fixed in tasks/data-model/contracts/spec/plan |

Coverage: FR-001–FR-030 mapped to tasks (100%); SC-001–SC-006 via T024/T027.
Verified against code: fixture values (45.40 / 18.20 / 27.20 / 59.9% / 22.70,
period revenue 5.00), forecast numbers (baseline MAE 15.00, RMSE 15.81;
150/160/170), and that the import merge design passes the domain's ownership
and atomicity checks.
