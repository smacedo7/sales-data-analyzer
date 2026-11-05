"""Synthetic demonstration data for a guided first run of the desktop window.

The data is written to a temporary CSV file and imported through the normal
CompanyWorkspace.import_sales path, so the demo goes through the same
validation and the same single atomic transaction as a real file.
"""

import csv
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
import random
import tempfile

from sales_data_analyzer.application import CompanyWorkspace, ImportSummary, SalesSession

DEMO_COMPANY = "Café Aurora (demo)"
DEMO_SECTOR = "Cafeteria"
DEMO_DAYS = 42
"""Six weeks: enough history for every forecast method to be evaluated."""

_PRODUCTS = (
    # id, name, category, unit price, unit cost
    ("CAF-01", "Espresso", "Bebidas", Decimal("6.50"), Decimal("1.90")),
    ("CAF-02", "Cappuccino", "Bebidas", Decimal("11.00"), Decimal("3.40")),
    ("CAF-03", "Chá gelado", "Bebidas", Decimal("8.90"), Decimal("2.10")),
    ("PAD-01", "Pão de queijo", "Salgados", Decimal("5.50"), Decimal("1.60")),
    ("PAD-02", "Croissant", "Salgados", Decimal("9.80"), Decimal("3.70")),
    ("DOC-01", "Bolo de cenoura", "Doces", Decimal("8.00"), Decimal("2.50")),
)
_HEADER = (
    "sale_id", "date_time", "product_id", "product", "category",
    "quantity", "unit_price", "unit_cost",
)  # fmt: skip


def demo_rows(last_day: date, *, seed: int = 7) -> list[tuple[str, ...]]:
    """Return CSV rows of DEMO_DAYS days ending on last_day (deterministic for a seed).

    Weekends sell more and sales grow slowly, so the charts and the forecast
    comparison have a visible weekly pattern and trend.
    """
    generator = random.Random(seed)
    rows: list[tuple[str, ...]] = []
    number = 0
    first = last_day - timedelta(days=DEMO_DAYS - 1)
    for offset in range(DEMO_DAYS):
        current = first + timedelta(days=offset)
        busy = 2 if current.weekday() >= 5 else 0
        for _ in range(3 + busy + offset // 14 + generator.randint(0, 2)):
            number += 1
            moment = datetime.combine(current, datetime.min.time()).replace(
                hour=generator.randint(7, 19), minute=generator.choice((0, 15, 30, 45))
            )
            for product in generator.sample(_PRODUCTS, generator.randint(1, 3)):
                code, name, category, price, cost = product
                rows.append((
                    f"D{number:05d}", moment.isoformat(timespec="seconds"), code, name,
                    category, str(generator.randint(1, 3)), str(price), str(cost),
                ))  # fmt: skip
    return rows


def find_demo(session: SalesSession) -> int | None:
    """Return the 1-based position of the demo company, or None when it does not exist."""
    for number, workspace in enumerate(session.workspaces, start=1):
        if workspace.company.name.casefold() == DEMO_COMPANY.casefold():
            return number
    return None


def load_demo(
    session: SalesSession, last_day: date | None = None
) -> tuple[CompanyWorkspace, ImportSummary]:
    """Create and select the demo company and import its sales in one transaction.

    `last_day` defaults to yesterday. Raise DuplicateCompanyError when the demo
    company already exists (callers select it instead); storage errors propagate
    and leave the new, empty company in place, exactly like a failed import.
    """
    last_day = last_day or date.today() - timedelta(days=1)
    workspace = session.create_company(DEMO_COMPANY, DEMO_SECTOR)
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "demo_sales.csv"
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(_HEADER)
            writer.writerows(demo_rows(last_day))
        summary = workspace.import_sales(path)
    return workspace, summary
