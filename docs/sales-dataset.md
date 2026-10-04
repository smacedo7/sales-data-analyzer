# SalesDataset contract

`SalesDataset(company)` creates an empty collection for an explicit Company.
`add_sale(sale)` returns None and accepts only non-empty Sale objects referencing
that same Company object. Trimmed sale IDs must be unique within this dataset.
Validation completes before insertion. `company` and `sales` are read-only;
`sales` returns a tuple snapshot in insertion order.

Sales are associated, not copied or owned: a Sale may appear in several datasets.
Appending valid items to a Sale after insertion is allowed, and every dataset
referencing it observes its updated totals. Read-only sale IDs, ownership and
timestamps keep membership and period selection stable. Public methods cannot
empty a previously accepted sale. Each filtered dataset has independent membership.

`filter_period(start, end)` implements the UML name, includes start, excludes end,
and returns a new SalesDataset with the same Company and shared Sale instances.
No matches produce an empty dataset. Bounds must be datetimes with start < end;
equal/reversed bounds raise ValueError even for empty datasets.

A dataset accepts either all naive timestamps or all aware timestamps. Mixing
awareness raises ValueError on insertion or filtering. Aware datetimes may use
different offsets: Python compares their actual instants. Naive datetimes are
compared as local wall times without assuming a timezone. Bounds must match each
other and the dataset's awareness; empty datasets have no awareness constraint
beyond consistent bounds. Wrong types raise TypeError.

The explicit company, constructor and add_sale method fill gaps in the planning
UML. The planned to_dataframe method remains deferred; this change adds no
analysis/import dependencies.

Run `PYTHONPATH=src uv run python -m unittest discover -s tests -v`.
