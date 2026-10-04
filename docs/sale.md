# Sale contract

`Sale(id: str, company: Company, date_time: datetime)` starts empty so items
can be assembled incrementally. IDs are trimmed non-empty strings, as in the
UML. ID, company and timestamp are read-only. Naive and timezone-aware
Python datetimes are accepted; dataset comparisons require consistent awareness.

`add_item(product, quantity, unit_price, unit_cost)` returns `None`, creates
an exclusive SaleItem and appends only after validation succeeds. The product
must reference the same Company object. SaleItem validates positive integer
quantities (excluding bool) and finite non-negative Decimal amounts.
Repeated products are allowed in the domain; duplicate CSV rows remain a future
import validation concern. `unit_price` and `unit_cost` clarify the UML's
`price` and `cost` parameter names.

`items` returns an immutable tuple snapshot. `calculate_total()` sums item
subtotals; `calculate_cost()` sums item costs. Empty sums are Decimal zero.
Items can be appended later, including after dataset insertion; existing items
cannot be removed or replaced through the public API. The company association
is explicit to enforce ownership before any items exist.

Run tests with `PYTHONPATH=src uv run python -m unittest discover -s tests -v`.
