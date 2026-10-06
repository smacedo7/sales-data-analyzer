# Level 1 delivery evidence

This is a non-web Python implementation. No menu, database or GUI is needed for
this level. Public repository: https://github.com/smacedo7/sales-data-analyzer.
Visibility was confirmed through GitHub's public API during preparation.

| Requirement | Implementation evidence | Test / demonstration evidence |
| --- | --- | --- |
| Inheritance | `analysis/__init__.py`: FinancialAnalysis/ProductAnalysis extend Analysis; `importing/__init__.py`: CSVImporter extends DataImporter | `test_polymorphism_and_validation`, abstract importer rejection in `test_file_errors_and_invalid_fixture` |
| Polymorphism | Shared `Analysis.run` and `DataImporter.load` contracts | Typed abstract variables and analysis loop in `examples/import_and_analyze.py` |
| Composition | `domain/sale.py`: Sale.add_item constructs owned SaleItem; tuple snapshot | `test_owned_items_snapshot_and_exact_totals`, repeated CSV item test |
| Association | SaleItem.product, SalesDataset.sales, company references | `test_grouping_precision_identity_and_analyses`, dataset ownership tests |
| Dependency | CSVImporter calls SalesValidator and creates domain results; Analysis consumes SalesDataset; forecaster uses lazy LinearRegression | Import-to-analysis integration and `test_dependency_isolation` |
| Functionalities tested | Import/validation, domain ownership/filtering, accounting/rankings and forecasting | 42 unittest tests passed during preparation; invalid subcases are parameterized |
| Complete editable model | `docs/diagrams/level-one.drawio`: Domain, Import, Analysis, Forecast pages | SVG page previews; result/metrics boxes included; planned features excluded |
| Executable example | `examples/import_and_analyze.py`; existing `analysis_and_forecast.py` | CSV: 2 sales, 3 items, revenue 45.40, profit 27.20; forecast example: revenue 1050, profit 630 |
| Repository public | GitHub repository URL above | Public API returned `private: false`, visibility public |
| YouTube video ≤3 minutes | `docs/video-script-pt.md` | Pending student recording/publication |
| Submission links | Repository, UML and video | Pending student submission |

## Reproduce

From the repository root with Python 3.14+ and uv:

```sh
uv sync --locked
PYTHONPATH=src uv run python -m unittest discover -s tests -v
PYTHONPATH=src uv run python examples/import_and_analyze.py
PYTHONPATH=src uv run python examples/analysis_and_forecast.py
```

`PYTHONPATH=src` also permits direct execution using an existing environment's
Python. Import/domain/descriptive analysis work with third-party site imports
disabled; forecasting needs the existing scikit-learn dependency. No new package
was added. No tests or examples require real sales data or downloads at runtime.

## Remaining student actions

Review and merge the implementation PR (and resolve/reconcile the independent
README PR #10 when appropriate). Record and upload the video to YouTube, ensure
it lasts at most 3 minutes and its link is accessible to the evaluator, then send
the required repository/UML/video links. Preparation does not mean submission;
no video has been recorded or published and no delivery has been submitted.
