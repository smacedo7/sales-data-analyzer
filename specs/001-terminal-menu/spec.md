# Feature Specification: Functional Terminal Menu (Level 2)

**Feature Branch**: `dev` (Spec Kit git extension not installed; directory `specs/001-terminal-menu`)

**Created**: 2026-10-11

**Status**: Draft — awaiting maintainer review

**Input**: User description: "Level 2: a functional terminal menu that exposes the
operations that already exist: create and select companies, register and look up
products, record sales and their items, import CSV into the selected company,
select data and filter periods, run financial and product analyses, run the
existing forecast explaining its limitations and insufficient-history errors,
show readable results, keep state in memory during the session and tell the user
that data is not kept after exit. Define the policy for repeated imports,
duplicate IDs and catalog conflicts before implementing."

## Scope

In scope: an interactive text menu, used by one person at a time, that drives
the level 1 capabilities without writing code. All data lives in memory for the
duration of one session.

Out of scope for this increment: saving data between sessions, editing or
deleting companies/products/sales, exporting files, charts, PDF reports, new
analyses or new forecasting models, multi-user use, graphical interface.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Start a session and manage companies (Priority: P1)

The analyst starts the program, is told that data exists only in memory, creates
one or more companies (name and sector) and selects the one to work on. Every
other operation applies to the selected company.

**Why this priority**: every other operation needs a selected company; this is
the smallest usable slice.

**Independent Test**: start the program, create two companies, list them,
select the second, see its name in the menu header, exit and confirm.

**Acceptance Scenarios**:

1. **Given** the program starts, **When** the main menu appears, **Then** a
   notice states that data is kept only in memory and is lost on exit.
2. **Given** no company exists, **When** the analyst creates "Coffee Shop" with
   sector "Retail", **Then** it is listed and automatically selected.
3. **Given** companies exist, **When** the analyst selects one by its list
   number, **Then** the header shows the selected company.
4. **Given** "Coffee Shop" exists, **When** the analyst creates " coffee shop "
   again, **Then** the creation is refused as a duplicate name.
5. **Given** no company is selected, **When** the analyst chooses any operation
   that needs one, **Then** the program explains that a company must be
   created or selected first and returns to the menu.
6. **Given** a session with data, **When** the analyst chooses Exit, **Then** the
   program warns that all data will be lost and exits only after confirmation.

---

### User Story 2 - Import sales from CSV (Priority: P1)

The analyst imports a CSV file (the level 1 format) into the selected company
and sees how many sales, items and new products were added.

**Why this priority**: importing is the fastest way to get realistic data for
analyses; it is the main level 1 capability.

**Independent Test**: select a company, import `tests/fixtures/valid_sales.csv`,
see "2 sales, 3 items, 2 new products"; import the same file again and see it
refused with nothing changed.

**Acceptance Scenarios**:

1. **Given** a selected company, **When** the analyst gives the path of a valid
   file, **Then** all its sales are added and a summary shows sales, items, new
   products and reused products.
2. **Given** a file with an invalid row, **When** it is imported, **Then** the
   message shows the line, field and reason, and the company's data is
   unchanged.
3. **Given** the same file was already imported, **When** it is imported again,
   **Then** the import is refused because its sale IDs already exist, and
   nothing changes.
4. **Given** the catalog has product "007" named "Coffee" in "Beverages",
   **When** a file uses "007" with the same name and category, **Then** the
   existing product is reused.
5. **Given** the catalog has product "007" named "Coffee", **When** a file uses
   "007" named "Tea", **Then** the import is refused as a catalog conflict and
   nothing changes.
6. **Given** a path that does not exist or is not readable, **When** it is
   imported, **Then** a clear message is shown and the menu continues.

---

### User Story 3 - Run analyses on all data or a period (Priority: P1)

The analyst runs the financial analysis and the product analysis on all sales
of the selected company or on a chosen period, and reads the results as
formatted tables.

**Why this priority**: analyses are the value the product delivers.

**Independent Test**: after importing the fixture, run both analyses on all data
and compare with revenue 45.40, cost 18.20, gross profit 27.20; set a period
covering only 2026-01-02 and see revenue 5.00.

**Acceptance Scenarios**:

1. **Given** imported sales, **When** the financial analysis runs on all data,
   **Then** revenue, cost, gross profit, gross margin (percentage), average
   order value and number of sales are shown, money with two decimal places.
2. **Given** imported sales, **When** the product analysis runs, **Then** a
   table shows product ID, name, quantity, revenue and gross profit, followed by
   the top products by quantity and by revenue.
3. **Given** a period from 2026-01-02 to 2026-01-02 (both days included),
   **When** an analysis runs, **Then** only sales on that day are used and the
   header states the period and the number of sales.
4. **Given** a period with no sales, **When** an analysis runs, **Then** zero
   totals are shown and undefined ratios are shown as "n/a", without errors.
5. **Given** the analyst enters an end date before the start date or an invalid
   date, **When** the period is set, **Then** the program explains the expected
   format and keeps the previous selection.
6. **Given** a period is active, **When** the analyst clears it, **Then**
   analyses use all data again.

---

### User Story 4 - Register products and record sales manually (Priority: P2)

The analyst adds products to the selected company's catalog, looks them up, and
records a sale with one or more items, entering quantity and the price and cost
practiced in that sale.

**Why this priority**: lets the analyst complement imported data and
demonstrates composition (sale owns items) and association (item references a
catalog product) live; imports already cover the bulk of data.

**Independent Test**: register two products, list them, look one up by ID,
record a sale with two items, run the financial analysis and see the sale
included.

**Acceptance Scenarios**:

1. **Given** a selected company, **When** the analyst registers ID "001", name
   "Coffee", category "Beverages", **Then** it appears in the catalog list.
2. **Given** "001" exists, **When** another product with ID " 001 " is
   registered, **Then** it is refused as a duplicate ID.
3. **Given** a catalog, **When** the analyst looks up "001", **Then** its name
   and category are shown; an unknown ID shows "not found".
4. **Given** catalog products, **When** the analyst records sale "S-1" at
   2026-01-05T10:00:00 with items (001, 2, 10.50, 4.00) and (002, 1, 5.00,
   2.00), **Then** the sale is stored with a total of 26.00 and cost 10.00.
5. **Given** sale "S-1" exists, **When** another sale "S-1" is recorded,
   **Then** it is refused as a duplicate sale ID before items are asked.
6. **Given** a sale being recorded, **When** the analyst enters an unknown
   product ID, a non-positive quantity or a negative/non-numeric amount,
   **Then** the item is refused with the reason and the analyst can retry or
   finish.
7. **Given** a sale being recorded with no valid item, **When** the analyst
   finishes, **Then** nothing is stored and the program says why.
8. **Given** the catalog is empty, **When** the analyst chooses to record a
   sale, **Then** the program asks to register or import products first.

---

### User Story 5 - Forecast revenue with stated limitations (Priority: P3)

The analyst runs the existing daily revenue forecast on the current selection,
sees the evaluation against a simple baseline, the future estimates and a
plain-language explanation of what the model does not consider.

**Why this priority**: it exposes an existing capability; it depends on enough
history, which manual data rarely has.

**Independent Test**: record or import 14 consecutive days of sales, run the
forecast with defaults and see model errors, baseline errors, future days and
the limitations notice; run it on 3 days of data and see the
insufficient-history explanation.

**Acceptance Scenarios**:

1. **Given** at least 7 consecutive days (5 training + 2 test) with varying revenue, **When** the
   forecast runs with defaults (horizon 7, test days 2), **Then** the program
   shows training/test day counts, model MAE and RMSE, baseline MAE and RMSE,
   which one performed better, and 7 future daily estimates.
2. **Given** any forecast result, **Then** a notice states that the model is a
   straight-line trend, ignores seasonality, holidays and promotions, may be
   worse than the baseline, may predict negative values and gives no accuracy
   guarantee.
3. **Given** fewer days than training (5) plus test days, **When** the forecast
   runs, **Then** the program explains how many days exist, how many are
   needed, and returns to the menu.
4. **Given** days without sales inside the history, **When** the forecast runs,
   **Then** the program explains the gap and offers to treat missing days as
   zero revenue only if the records are complete.
5. **Given** constant revenue in the training days, **When** the forecast runs,
   **Then** the program explains that a trend cannot be learned.
6. **Given** sales imported with time zone offsets, **When** the forecast runs,
   **Then** the analyst is asked for the UTC offset used to group days
   (default +00:00).

---

### Edge Cases

- Empty or whitespace-only text where a value is required: re-ask, never crash.
- Invalid menu option or non-numeric choice: message and menu shown again.
- End of input (Ctrl+D) or interrupt (Ctrl+C): the program ends with the
  data-loss notice and a normal exit status, without a stack trace.
- Very long CSV files: import completes or fails as a whole; no partial data.
- Amounts with more than two decimals (e.g. 10.125) are stored exactly; only
  the display is rounded.
- Sales imported with time zone offsets cannot be mixed with sales without
  offset in the same company; the second kind is refused with an explanation.
- Period dates for data with offsets are interpreted in UTC (stated on screen);
  the forecast groups days by the offset the user enters (default `+00:00`, so
  both agree by default). With another offset, the first and last forecast
  days may hold partial revenue; the period prompt states this.
- Two companies may contain products and sales with the same IDs; IDs are
  scoped to their company.
- Any unexpected internal error is reported in one line and the menu continues;
  data already stored is not lost.

## Requirements *(mandatory)*

### Functional Requirements

**Session and companies**

- **FR-001**: The program MUST show, at start and before exit, that data is kept
  only in memory and is lost when the program ends.
- **FR-002**: Users MUST be able to create a company with a non-empty name and
  sector; names MUST be unique in the session, ignoring case and surrounding
  spaces.
- **FR-003**: Users MUST be able to list companies and select one; a newly
  created company becomes the selected one.
- **FR-004**: Operations other than company creation/selection and exit MUST
  require a selected company.
- **FR-005**: Exit MUST ask for confirmation; end of input or interrupt MUST end
  the program cleanly.

**Catalog**

- **FR-006**: Users MUST be able to register a product (ID, name, category) in
  the selected company's catalog; IDs are trimmed text, keep leading zeros, and
  MUST be unique within the company.
- **FR-007**: Users MUST be able to list the catalog (ordered by ID) and look up
  a product by ID.

**Manual sales**

- **FR-008**: Users MUST be able to record a sale with an ID unique within the
  company, a date-time in the import format (`YYYY-MM-DDTHH:MM:SS`, optional
  offset; offsets are normalized to UTC as in imports) and one or more items.
- **FR-009**: Each item MUST reference a catalog product of the selected
  company and include a positive whole quantity and non-negative unit price and
  unit cost entered as plain decimal numbers; these values are kept exactly as
  entered and never changed by later catalog edits.
- **FR-010**: A sale MUST be stored only when it has at least one valid item;
  cancelling or failing leaves the company's data unchanged.

**Import**

- **FR-011**: Users MUST be able to import a CSV file in the level 1 format into
  the selected company, with the same validation and line/field/reason
  diagnostics as level 1.
- **FR-012**: An import MUST be all-or-nothing with respect to the company's
  existing data: if any rule below fails, nothing is added.
- **FR-013 (repeated import / duplicate sale IDs)**: An import MUST be refused
  if any of its sale IDs already exists in the company. The message MUST give
  the number of conflicting IDs and up to five examples. Sales are never
  overwritten, merged or skipped.
- **FR-014 (catalog reuse)**: A product ID in the file that exists in the
  catalog with the same name and category (after trimming, case-sensitive)
  MUST reuse the existing catalog product.
- **FR-015 (catalog conflict)**: A product ID in the file that exists in the
  catalog with a different name or category MUST cause the import to be
  refused, naming the conflicting product IDs (up to five).
- **FR-016**: Products that appear only in the file MUST be added to the
  catalog when the import succeeds.
- **FR-017**: Imported sales with time zone offsets MUST NOT be mixed with
  existing sales without offset (and vice versa); such an import is refused.
- **FR-018**: A successful import MUST report sales added, items added, new
  products and reused products.

**Selection and analyses**

- **FR-019**: Users MUST be able to set a period by start and end dates
  (`YYYY-MM-DD`, both days included) or clear it; the active selection (all
  data or period) MUST be shown with the number of selected sales.
- **FR-020**: Users MUST be able to run the financial analysis on the active
  selection and see revenue, cost, gross profit, gross margin as a percentage,
  average order value and sale count.
- **FR-021**: Users MUST be able to run the product analysis on the active
  selection and see, per product, ID, catalog name, quantity, revenue and gross
  profit, plus the top five by quantity and by revenue (ties by ascending ID).
- **FR-022**: Money MUST be displayed with two decimal places, rounding half
  up, without changing stored values; undefined ratios MUST be shown as "n/a".

**Forecast**

- **FR-023**: Users MUST be able to run the existing revenue forecast on the
  active selection, choosing horizon (default 7, from 1 to 365
  days) and test days (default 2, minimum 2).
- **FR-024**: Results MUST show training and test day counts, model and
  baseline MAE/RMSE, which performed better, and each future day with its
  estimate.
- **FR-025**: Every forecast result MUST be followed by the limitations notice
  of User Story 5, scenario 2.
- **FR-026**: Insufficient history, missing days, constant revenue and invalid
  parameters MUST be explained in plain language, including, for insufficient
  history, how many days exist and how many are needed.
- **FR-027**: Missing days MUST be treated as zero only after the user confirms
  that the records are complete.
- **FR-028**: For sales with offsets, users MUST provide a UTC offset
  (`±HH:MM`, default `+00:00`) used to group days.

**Robustness**

- **FR-029**: No user input MUST terminate the program with an error trace;
  every error returns to the current menu with a message.
- **FR-030**: The program MUST start with one documented command on macOS and
  Windows.

### Key Entities *(include if feature involves data)*

- **Session**: the in-memory working state of one program run: the companies
  created, the selected company and the active selection. Discarded on exit.
- **Company workspace**: one company with its product catalog (products by ID)
  and all its sales. Sale IDs and product IDs are unique inside it.
- **Selection**: either all sales of the selected company or those inside a
  period of whole days.
- **Import summary**: counts reported after a successful import.
- Existing level 1 entities are reused unchanged: Company, Product, Sale,
  Sale item, Sales dataset, analysis results and forecast result.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A first-time user can create a company, import the sample file and
  read the financial analysis in under 2 minutes using only on-screen prompts.
- **SC-002**: 100% of the level 1 operations listed in Scope are reachable from
  the menu without writing code.
- **SC-003**: Results shown for the sample file match the level 1 documented
  values exactly (revenue 45.40, cost 18.20, gross profit 27.20).
- **SC-004**: In a scripted session that feeds every invalid input listed in
  this spec, the program never stops unexpectedly and the company data after
  each refused operation equals the data before it.
- **SC-005**: Re-importing a file already imported changes nothing in 100% of
  attempts.
- **SC-006**: The same scripted session produces the same results on macOS and
  Windows.

## Assumptions

- One person uses the program at a time, in a terminal with UTF-8 text.
- The CSV format and validation rules are exactly those of level 1
  (`docs/csv-import.md`).
- Dates typed for periods are calendar days; for data with offsets they are
  interpreted in UTC, consistent with how imports normalize offsets.
- Product names and categories are compared exactly after trimming; "Coffee" and
  "coffee" are different values (a conflict for the same ID).
- Editing and deleting are deferred to the persistence level, where they matter.
- Display language of the menu: English, consistent with the repository
  language policy. *(Open decision D1 in plan.md.)*
