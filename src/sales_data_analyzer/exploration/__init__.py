"""Exact grouped summaries of sales for exploration, computed with pandas.

Pandas groups the rows, but amounts stay `Decimal` in object columns, so every
total is exact and equals FinancialAnalysis for the same sales. Results are frozen
dataclasses; no pandas object leaves this package. Pandas is imported only when a
summary is requested, keeping start-up fast.

Days follow the level 2 period rule: the sale's own calendar day for timestamps
without offset, and the day in ``timezone`` (UTC in the application) otherwise.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta, tzinfo
from decimal import Decimal
from typing import Literal

from sales_data_analyzer.analysis import FinancialAnalysis, FinancialMetrics
from sales_data_analyzer.domain.sale import Sale
from sales_data_analyzer.domain.sales_dataset import SalesDataset

Granularity = Literal["day", "week", "month"]
MissingDays = Literal["reject", "zero"]
WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


@dataclass(frozen=True)
class PeriodTotal:
    """Totals of one day, ISO week or calendar month (start and end included)."""

    label: str
    start: date
    end: date
    revenue: Decimal
    cost: Decimal
    gross_profit: Decimal
    sale_count: int


@dataclass(frozen=True)
class TemporalSummary:
    """Rows in calendar order plus how many days inside the span had no sales.

    With the reject policy, rows list only periods with sales; with zero, every
    period from the first to the last sale appears (empty ones as zero). Totals
    are the same under both policies.
    """

    granularity: Granularity
    rows: tuple[PeriodTotal, ...]
    missing_days: int
    zero_filled: bool
    days_are_utc: bool


@dataclass(frozen=True)
class WeekdayProfile:
    """Revenue of one weekday (0 = Monday) and its average over the counted days."""

    weekday: int
    occurrences: int
    total_revenue: Decimal
    average_revenue: Decimal | None


@dataclass(frozen=True)
class CategoryTotal:
    """Item totals of one product category."""

    category: str
    revenue: Decimal
    cost: Decimal
    gross_profit: Decimal
    quantity: int


@dataclass(frozen=True)
class PeriodComparison:
    """Financial metrics of two periods and the change from the first to the second.

    Ratios are relative to the first period and None when its value is zero.
    """

    first: FinancialMetrics
    second: FinancialMetrics
    revenue_change: Decimal
    revenue_change_ratio: Decimal | None
    cost_change: Decimal
    cost_change_ratio: Decimal | None
    gross_profit_change: Decimal
    gross_profit_change_ratio: Decimal | None
    sale_count_change: int
    sale_count_change_ratio: Decimal | None


def _check_dataset(data: SalesDataset) -> None:
    """Raise TypeError unless data is a SalesDataset."""
    if not isinstance(data, SalesDataset):
        raise TypeError("data must be a SalesDataset")


def _check_options(missing_days: str, timezone: tzinfo | None) -> None:
    """Validate the missing-day policy and the timezone argument."""
    if missing_days not in ("reject", "zero"):
        raise ValueError("missing_days must be 'reject' or 'zero'")
    if timezone is not None and not isinstance(timezone, tzinfo):
        raise TypeError("timezone must be a tzinfo")


def _sale_day(sale: Sale, timezone: tzinfo | None) -> date:
    """Return the calendar day of a sale under the level 2 day rule."""
    moment = sale.date_time
    if moment.utcoffset() is None:
        return moment.date()
    if timezone is None:
        raise ValueError("timestamps with offsets require a timezone")
    return moment.astimezone(timezone).date()


def _sales_frame(data: SalesDataset, timezone: tzinfo | None):  # -> pandas.DataFrame
    """Return one row per sale with its day, exact revenue and cost (object columns)."""
    import pandas as pd

    return pd.DataFrame(
        {
            "day": [_sale_day(sale, timezone) for sale in data.sales],
            "revenue": pd.Series([s.calculate_total() for s in data.sales], dtype=object),
            "cost": pd.Series([s.calculate_cost() for s in data.sales], dtype=object),
            "sales": [1] * len(data.sales),
        }
    )


def _daily_totals(data: SalesDataset, timezone: tzinfo | None) -> dict[date, tuple]:
    """Return {day: (revenue, cost, sale count)} for days with sales, in day order."""
    if not data.sales:
        return {}
    frame = _sales_frame(data, timezone)
    grouped = frame.groupby("day", sort=True).agg(
        revenue=("revenue", _exact_sum), cost=("cost", _exact_sum), sales=("sales", "sum")
    )
    return {row.Index: (row.revenue, row.cost, int(row.sales)) for row in grouped.itertuples()}


def _exact_sum(values) -> Decimal:  # values: pandas.Series of Decimal
    """Add Decimal values without floating point, starting from Decimal 0."""
    return sum(values, Decimal(0))


def _day_span(first: date, last: date) -> list[date]:
    """Return every calendar day from first to last, both included."""
    return [first + timedelta(days=offset) for offset in range((last - first).days + 1)]


def _period_of(day: date, granularity: Granularity) -> tuple[str, date, date]:
    """Return the label, first day and last day of the period containing day."""
    if granularity == "day":
        return day.isoformat(), day, day
    if granularity == "week":
        year, week, weekday = day.isocalendar()
        start = day - timedelta(days=weekday - 1)
        return f"{year}-W{week:02d}", start, min(start + timedelta(days=6), date.max)
    start = day.replace(day=1)
    following = date(day.year + 1, 1, 1) if day.month == 12 else date(day.year, day.month + 1, 1)
    return f"{day.year}-{day.month:02d}", start, following - timedelta(days=1)


def _is_utc_days(data: SalesDataset) -> bool:
    """Return True when the sales carry offsets (their days are timezone days)."""
    return bool(data.sales) and data.sales[0].date_time.utcoffset() is not None


def temporal_summary(
    data: SalesDataset,
    granularity: Granularity,
    *,
    missing_days: MissingDays = "reject",
    timezone: tzinfo | None = None,
) -> TemporalSummary:
    """Group revenue, cost, gross profit and sale count by day, ISO week or month.

    Raise TypeError for a wrong dataset or timezone type and ValueError for an
    unknown granularity or policy, or offset timestamps without a timezone.
    """
    _check_dataset(data)
    _check_options(missing_days, timezone)
    if granularity not in ("day", "week", "month"):
        raise ValueError("granularity must be 'day', 'week' or 'month'")
    daily = _daily_totals(data, timezone)
    if not daily:
        return TemporalSummary(granularity, (), 0, missing_days == "zero", _is_utc_days(data))
    days = _day_span(min(daily), max(daily))
    missing = len(days) - len(daily)
    zero = (Decimal(0), Decimal(0), 0)
    listed = days if missing_days == "zero" else list(daily)
    periods: dict[str, list] = {}
    for day in listed:
        label, start, end = _period_of(day, granularity)
        revenue, cost, count = daily.get(day, zero)
        total = periods.setdefault(label, [start, end, Decimal(0), Decimal(0), 0])
        total[2] += revenue
        total[3] += cost
        total[4] += count
    rows = tuple(
        PeriodTotal(label, start, end, revenue, cost, revenue - cost, count)
        for label, (start, end, revenue, cost, count) in periods.items()
    )
    return TemporalSummary(granularity, rows, missing, missing_days == "zero", _is_utc_days(data))


def weekday_profile(
    data: SalesDataset,
    *,
    missing_days: MissingDays = "reject",
    timezone: tzinfo | None = None,
) -> tuple[WeekdayProfile, ...]:
    """Return seven rows, Monday first, with revenue totals and averages per weekday.

    With the zero policy the average divides by every occurrence of the weekday
    between the first and last sale; with reject only days with sales count. An
    average is None when the weekday never occurs in the counted days.
    """
    _check_dataset(data)
    _check_options(missing_days, timezone)
    daily = _daily_totals(data, timezone)
    counted = _day_span(min(daily), max(daily)) if daily and missing_days == "zero" else list(daily)
    occurrences = [0] * 7
    totals = [Decimal(0)] * 7
    for day in counted:
        occurrences[day.weekday()] += 1
        totals[day.weekday()] += daily.get(day, (Decimal(0),))[0]
    return tuple(
        WeekdayProfile(
            weekday, occurrences[weekday], totals[weekday],
            totals[weekday] / occurrences[weekday] if occurrences[weekday] else None,
        )
        for weekday in range(7)
    )  # fmt: skip


def category_totals(
    data: SalesDataset, categories: Mapping[str, str] | None = None
) -> tuple[CategoryTotal, ...]:
    """Return item totals per category, highest revenue first (ties by name).

    categories maps product IDs to the current catalog category; items whose
    product is not in the mapping use the category of the product they reference.
    """
    _check_dataset(data)
    import pandas as pd

    categories = categories or {}
    items = [item for sale in data.sales for item in sale.items]
    if not items:
        return ()
    frame = pd.DataFrame(
        {
            "category": [categories.get(i.product.id, i.product.category) for i in items],
            "revenue": pd.Series([i.calculate_subtotal() for i in items], dtype=object),
            "cost": pd.Series([i.calculate_cost() for i in items], dtype=object),
            "quantity": pd.Series([i.quantity for i in items], dtype=object),
        }
    )
    grouped = frame.groupby("category", sort=True).agg(
        revenue=("revenue", _exact_sum),
        cost=("cost", _exact_sum),
        quantity=("quantity", lambda values: sum(values, 0)),
    )
    rows = [
        CategoryTotal(category, row.revenue, row.cost, row.revenue - row.cost, int(row.quantity))
        for category, row in zip(grouped.index, grouped.itertuples(), strict=True)
    ]
    return tuple(sorted(rows, key=lambda row: (-row.revenue, row.category)))


def _change(first: Decimal, second: Decimal) -> tuple[Decimal, Decimal | None]:
    """Return the change and the change relative to first (None when first is 0)."""
    change = second - first
    return change, (change / first if first else None)


def compare_periods(first: SalesDataset, second: SalesDataset) -> PeriodComparison:
    """Compare two selections with FinancialAnalysis; either may be empty."""
    _check_dataset(first)
    _check_dataset(second)
    analysis = FinancialAnalysis()
    a, b = analysis.run(first).financial, analysis.run(second).financial
    if a is None or b is None:  # FinancialAnalysis always sets it; keeps type checkers honest
        raise ValueError("financial analysis returned no metrics")
    count_change, count_ratio = _change(Decimal(a.sale_count), Decimal(b.sale_count))
    return PeriodComparison(
        a, b,
        *_change(a.revenue, b.revenue),
        *_change(a.cost, b.cost),
        *_change(a.gross_profit, b.gross_profit),
        int(count_change), count_ratio,
    )  # fmt: skip


__all__ = [
    "WEEKDAY_NAMES",
    "CategoryTotal",
    "PeriodComparison",
    "PeriodTotal",
    "TemporalSummary",
    "WeekdayProfile",
    "category_totals",
    "compare_periods",
    "temporal_summary",
    "weekday_profile",
]
