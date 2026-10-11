# Contract: terminal menu

## Start

```text
uv run sales-data-analyzer
uv run python -m sales_data_analyzer
```

Exit status 0 on normal exit, EOF or Ctrl+C.

## Screen layout

```text
Sales Data Analyzer - level 2 (terminal)
Data is kept in memory only and is lost when you exit.

Company: Coffee Shop (Retail) | Selection: all data (2 sales)
 1. Create company
 2. Select company
 3. Register product
 4. List products
 5. Find product
 6. Record sale
 7. Import CSV
 8. Set period
 9. Clear period
10. Financial analysis
11. Product analysis
12. Revenue forecast
 0. Exit
Choose an option:
```

Header shows `Company: none` when nothing is selected. Options 3–12 with no
company print `Not done: create or select a company first.`

## Prompts and accepted formats

| Prompt | Format | Invalid input behaviour |
| --- | --- | --- |
| Menu option | integer listed | `Invalid option.` and menu again |
| Name/sector/ID/category | non-empty text, trimmed | re-ask once per entry; empty entry at an optional step cancels the operation |
| Date-time of sale | `YYYY-MM-DDTHH:MM:SS[.ffffff][Z|±HH:MM]` | `Invalid value: ...` re-ask |
| Period dates | `YYYY-MM-DD` (up to 9999-12-30) | re-ask; end before start → `Not done: ...` |
| Quantity | positive integer | re-ask |
| Unit price / cost | plain non-negative decimal (`10.50`, no thousands separator, no exponent) | re-ask |
| CSV path | any path; surrounding quotes removed; on macOS/Linux `\ ` escapes undone | import error message |
| Horizon / test days | horizon 1–365, test days ≥ 2 (blank = default 7 / 2) | re-ask |
| UTC offset | `±HH:MM` (blank = `+00:00`) | re-ask |
| Yes/no | `y`/`n` (blank = no) | re-ask |

Sale item loop: after each item, `Add another item? [y/N]`; product ID blank
finishes the sale.

## Result formats

Financial:

```text
Financial analysis - Coffee Shop - all data (2 sales)
Revenue ............ 45.40
Cost ............... 18.20
Gross profit ....... 27.20
Gross margin ....... 59.9%
Average order ...... 22.70
Sales .............. 2
```

Product:

```text
Product analysis - Coffee Shop - all data (2 sales)
ID    Name             Qty   Revenue   Gross profit
007   Coffee, premium    4     40.40          24.20
008   Tea                1      5.00           3.00
Top by quantity: 007, 008
Top by revenue:  007, 008
```

Import refused (duplicate IDs; IDs come from the error attributes):

```text
Import refused: 2 sale ID(s) already exist in this company: 001, 002.
```

Import success:

```text
Imported 2 sales, 3 items. Products: 2 new, 0 reused.
```

Forecast (abridged):

```text
Revenue forecast - Coffee Shop - all data
Training days: 12 | Test days: 2
Model     MAE 0.00  RMSE 0.00
Baseline  MAE 15.00 RMSE 15.81 (repeats last training day)
Better on test days: model
Next 7 days:
2026-01-15  150.00
...
Limitations: straight-line trend on the day number only; ignores
seasonality, holidays and promotions; can be worse than the baseline; can
predict negative values; no accuracy guarantee.
```

## Forecast error messages (mapping from `ValueError`)

| Condition | Message |
| --- | --- |
| History shorter than 5 + test days (checked first, counting calendar days from first to last sale) | `Not enough history: N day(s) available, at least M needed (5 training + T test). Add or import more days.` |
| Missing days (enough days, gaps inside) | `Some days between the first and last sale have no sales.` then `Treat missing days as zero revenue? Only answer yes if your records are complete. [y/N]` |
| Constant training revenue | `Training revenue is constant, so no trend can be learned.` |
| Aware data without offset | never shown: the menu asks the offset first |
| No sales in selection | `No sales in the current selection.` |

## Unexpected errors

```text
Unexpected error (KeyError). Your data is unchanged.
```

Only the exception type is shown, never its message (it may contain values or
paths).

## Exit

```text
All data from this session will be lost. Exit? [y/N]
```

