---
name: domain-review
description: Review changes touching the sales domain (money, validation, identity, composition, association, historical data). Use when domain/, importing/, analysis/, forecasting/ or a new application service changes.
---

# Domain review

Review the current diff (`git diff dev...HEAD` plus uncommitted changes, or
the paths the user names) against the domain rules. Read the changed code;
do not review from memory. Report findings with `file:line`, severity
(blocking / should fix / note) and a concrete fix.

## Checklist

**Money**
- Amounts are `Decimal` from input to output; no `float()` on money outside
  the ML boundary in `forecasting/`.
- No hidden rounding; display formatting (e.g. 2 places) happens only in the
  presentation layer and never feeds back into calculations.
- Non-finite and negative amounts are rejected where the domain rejects them.

**Validation**
- New inputs reuse existing validators (`validate_non_empty_string`,
  `SalesValidator`, `SaleItem` checks) instead of duplicating rules.
- Wrong types raise `TypeError`; invalid values raise `ValueError` (or a
  documented subclass such as `ImportValidationError`).
- Validation completes before any state change (atomicity).

**Identity**
- Product IDs and sale IDs stay strings (leading zeros preserved, trimmed).
- Product identity is the ID within one company; sale IDs are unique within
  a dataset. Company is compared by object identity.
- Duplicates/conflicts follow the policy in the active spec.

**Composition and association**
- `SaleItem`s are created only through `Sale.add_item`.
- `SalesDataset` shares sales; it never copies or mutates them.
- Cross-company references are rejected.

**Historical data**
- Catalog edits (product name/category) never alter recorded sale items.
- Prices/costs stored on items are never recomputed from the catalog.

**Layering**
- `domain/` imports only the standard library and sibling domain modules.
- No `input()`/`print()` outside the terminal adapter.

## Rules

- Read-only review: propose fixes, do not apply them unless asked.
- Do not commit, push or merge.
