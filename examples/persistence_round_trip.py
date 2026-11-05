"""Store sales in a temporary SQLite database, reopen it and compare the totals.

Run from any working directory; nothing is written outside a temporary folder.
"""

from datetime import datetime
from decimal import Decimal
from pathlib import Path
import tempfile

from sales_data_analyzer.application import ItemInput, SalesSession
from sales_data_analyzer.persistence import SQLiteSalesRepository

FIXTURE = Path(__file__).resolve().parents[1] / "tests/fixtures/forecast_14_days.csv"


def revenue(session: SalesSession) -> Decimal:
    """Return the financial-analysis revenue of the selected company."""
    return session.run_financial_analysis().financial.revenue


def main() -> None:
    """Write through one session, then read the same file with a new one."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "demo.sqlite3"

        repository = SQLiteSalesRepository.open(path)
        try:
            session = SalesSession.open(repository)
            workspace = session.create_company("Example shop", "Retail")
            workspace.import_sales(FIXTURE)
            workspace.record_sale(
                "M-1",
                datetime(2026, 1, 15, 9, 30),
                [ItemInput("100", 3, Decimal("10.10"), Decimal("4.05"))],
            )
            written = revenue(session)
            print(f"First run: {len(workspace.sales.sales)} sales, revenue {written}")
        finally:
            repository.close()

        repository = SQLiteSalesRepository.open(path)
        try:
            session = SalesSession.open(repository)
            session.select_company(1)
            loaded = revenue(session)
            print(f"After reopening: {len(session.current.sales.sales)} sales, revenue {loaded}")
            print(f"Exact match: {loaded == written}")
        finally:
            repository.close()


if __name__ == "__main__":
    main()
