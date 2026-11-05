"""Synthetic in-memory sessions for application and interface tests."""

from datetime import date, datetime, timedelta, tzinfo
from decimal import Decimal

from sales_data_analyzer.application import ItemInput, SalesSession

START = date(2026, 1, 5)
"""A Monday, so weekday positions are easy to read in tests."""


def daily_session(
    days: int,
    *,
    start: date = START,
    skip: tuple[int, ...] = (),
    session: SalesSession | None = None,
    zone: tzinfo | None = None,
) -> SalesSession:
    """Return a session with company 'Acme', products P1/P2 and one sale per day.

    Day i (0-based, except those in skip) sells 1 x P1 at 10 + i and, on even
    days, 2 x P2 at 3.25; costs are 4 and 1.10. Revenue is exact Decimal. With
    zone, every timestamp (noon) carries that time zone.
    """
    session = session or SalesSession()
    workspace = session.create_company("Acme", "Retail")
    workspace.register_product("P1", "Pen", "Office")
    workspace.register_product("P2", "Ink", "Supplies")
    for index in range(days):
        if index in skip:
            continue
        items = [ItemInput("P1", 1, Decimal(10 + index), Decimal("4"))]
        if index % 2 == 0:
            items.append(ItemInput("P2", 2, Decimal("3.25"), Decimal("1.10")))
        moment = datetime.combine(start + timedelta(days=index), datetime.min.time(), zone)
        workspace.record_sale(f"S{index:03d}", moment.replace(hour=12), items)
    return session
