"""Qt-free report text for the desktop window, built only from session services.

Every function asks the application session for its typed result and renders it
with the terminal's presentation helpers, so the window shows the same numbers,
rounding and honest-forecast wording as the terminal menu (spec FR-012, SC-002).
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Literal

from sales_data_analyzer.application import NoSalesInSelectionError, SalesSession, Selection
from sales_data_analyzer.cli.formatting import (
    format_categories,
    format_comparison,
    format_comparison_estimates,
    format_financial,
    format_forecast,
    format_period_comparison,
    format_products,
    format_scope,
    format_temporal,
    format_weekdays,
    plural,
)
from sales_data_analyzer.forecasting import ComparisonResult

AnalysisView = Literal["financial", "products", "day", "week", "month", "weekday", "category"]
"""Analyses offered by the window, in menu order."""

ANALYSIS_VIEWS: tuple[tuple[AnalysisView, str], ...] = (
    ("financial", "Financial summary"),
    ("products", "Products"),
    ("day", "Sales by day"),
    ("week", "Sales by week"),
    ("month", "Sales by month"),
    ("weekday", "Weekday profile"),
    ("category", "Categories"),
)
"""(key, label) pairs shown in the analysis selector."""

NO_SALES = "No sales in the current selection."


def scope(session: SalesSession) -> str:
    """Return 'company - selection (n sales)', the header of every result."""
    workspace = session.require_current()
    count = len(session.selected_sales().sales)
    return format_scope(workspace.company.name, session.selection.describe(), count)


def selection_text(session: SalesSession) -> str:
    """Return the selection label of the top bar ('No company selected' before one)."""
    if session.current is None:
        return "No company selected"
    return f"Selection: {scope(session)}"


def missing_days(session: SalesSession) -> int:
    """Return how many days between the first and last selected sale have no sales."""
    if not session.selected_sales().sales:
        return 0
    return session.sales_over_time("day").missing_days


def analysis_lines(
    session: SalesSession, view: AnalysisView, *, zero_missing_days: bool = False
) -> list[str]:
    """Return the text of one analysis of the selection.

    `zero_missing_days` applies only to the temporal and weekday views, as in
    the terminal. Raise ValueError for an unknown view.
    """
    keys = [key for key, _ in ANALYSIS_VIEWS]
    if view not in keys:
        raise ValueError("unknown analysis view")
    session.require_current()
    if not session.selected_sales().sales:
        return [NO_SALES]
    header = scope(session)
    policy = "zero" if zero_missing_days else "reject"
    if view == "financial":
        return format_financial(session.run_financial_analysis(), header)
    if view == "products":
        names = {p.id: p.name for p in session.require_current().products}
        return format_products(session.run_product_analysis(), header, names)
    if view == "category":
        return format_categories(session.category_totals(), header)
    if view == "weekday":
        return format_weekdays(
            session.weekday_profile(missing_days=policy),
            header,
            zero_filled=zero_missing_days,
            days_are_utc=session.data_is_aware(),
        )
    return format_temporal(session.sales_over_time(view, missing_days=policy), header)


def period_comparison_lines(
    session: SalesSession, first: Selection, second: Selection
) -> list[str]:
    """Return the comparison of two periods; the active selection is unchanged."""
    comparison = session.compare_periods(first, second)
    return format_period_comparison(comparison, first.describe(), second.describe())


def forecast_lines(
    session: SalesSession,
    *,
    horizon: int,
    test_days: int,
    zero_missing_days: bool = False,
    utc_offset: timedelta | None = None,
) -> list[str]:
    """Return the level 2 linear forecast text (service errors propagate)."""
    session.require_current()
    if not session.selected_sales().sales:
        raise NoSalesInSelectionError()
    result = session.run_forecast(
        horizon=horizon,
        test_days=test_days,
        missing_days="zero" if zero_missing_days else "reject",
        utc_offset=utc_offset,
    )
    return format_forecast(result, _forecast_header(session))


@dataclass(frozen=True)
class ComparisonReport:
    """A forecast comparison and its text: evaluation table plus chosen estimates."""

    result: ComparisonResult
    lines: tuple[str, ...]


def comparison_report(
    session: SalesSession,
    *,
    horizon: int,
    zero_missing_days: bool = False,
    utc_offset: timedelta | None = None,
    method: str | None = None,
) -> ComparisonReport:
    """Compare forecast methods (optionally forcing the estimate method); errors propagate."""
    session.require_current()
    if not session.selected_sales().sales:
        raise NoSalesInSelectionError()
    result = session.compare_forecasts(
        horizon=horizon,
        missing_days="zero" if zero_missing_days else "reject",
        utc_offset=utc_offset,
        method=method,
    )
    header = _forecast_header(session)
    lines = format_comparison(result, header) + [""] + format_comparison_estimates(result)
    return ComparisonReport(result, tuple(lines))


def _forecast_header(session: SalesSession) -> str:
    """Return 'company - selection', the forecast header used by the terminal."""
    return f"{session.require_current().company.name} - {session.selection.describe()}"


def missing_days_notice(count: int) -> str:
    """Return the explanation shown next to the 'treat as zero' option."""
    return f"{plural(count, 'day')} between the first and last sale have no sales."
