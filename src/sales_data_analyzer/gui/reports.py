"""Qt-free, translated views of the session's results: cards, tables and notes.

Every function asks the application session for its typed result and only
formats it (texts.money, texts.percent, …). Nothing here adds, divides, ranks or
groups business values: totals rows come from FinancialAnalysis of the same
selection, rankings from ProductAnalysis, forecasts from the forecasting
services. The same objects feed the window and the PDF report (spec FR-012).
"""

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Literal

from sales_data_analyzer.application import (
    InsufficientHistoryError,
    NoSalesInSelectionError,
    SalesSession,
    Selection,
)
from sales_data_analyzer.cli.formatting import is_missing_days_error
from sales_data_analyzer.forecasting import ComparisonResult, ForecastResult

from .texts import (
    decimal_number,
    day,
    id_list,
    integer,
    method_title,
    money,
    percent,
    signed_money,
    t,
    weekday,
)

AnalysisView = Literal["financial", "products", "day", "week", "month", "weekday", "category"]
"""Analyses offered by the window, in menu order."""

ANALYSIS_VIEWS: tuple[AnalysisView, ...] = (
    "financial", "products", "day", "week", "month", "weekday", "category",
)  # fmt: skip


@dataclass(frozen=True)
class Card:
    """One headline indicator: label, formatted value and a color tone name."""

    label: str
    value: str
    tone: str


@dataclass(frozen=True)
class Table:
    """A titled table of formatted cells, with right-aligned numeric columns and notes."""

    title: str
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    numeric: tuple[int, ...] = ()
    notes: tuple[str, ...] = ()
    total_row: bool = False


@dataclass(frozen=True)
class Report:
    """Tables plus notes shown below them (limitations, honest wording)."""

    tables: tuple[Table, ...]
    notes: tuple[str, ...] = field(default=())


# -- selection --------------------------------------------------------------------------


def sales_count_text(count: int) -> str:
    """Return '1 venda' / '3 vendas' in the active language."""
    return t("common.sales", count=count)


def selection_text(session: SalesSession) -> str:
    """Return the header line describing the active period and its sale count."""
    if session.current is None:
        return t("header.no_company")
    count = len(session.selected_sales().sales)
    selection = session.selection
    if selection.start is None or selection.end is None:
        return t("header.selection_all", sales=sales_count_text(count))
    return t(
        "header.selection_period",
        start=day(selection.start),
        end=day(selection.end),
        sales=sales_count_text(count),
    )


def period_text(selection: Selection) -> str:
    """Return 'todo o histórico' or 'dd/mm/aaaa a dd/mm/aaaa'."""
    if selection.start is None or selection.end is None:
        return t("report.all_data")
    return t("report.range", start=day(selection.start), end=day(selection.end))


def has_sales(session: SalesSession) -> bool:
    """Return True when a company is selected and its selection has sales."""
    return session.current is not None and bool(session.selected_sales().sales)


def missing_days(session: SalesSession) -> int:
    """Return how many days between the first and last selected sale have no sales."""
    if not has_sales(session):
        return 0
    return session.sales_over_time("day").missing_days


def _require_sales(session: SalesSession) -> None:
    """Raise NoSalesInSelectionError when the selection is empty."""
    session.require_current()
    if not session.selected_sales().sales:
        raise NoSalesInSelectionError()


# -- overview ---------------------------------------------------------------------------


def financial_cards(session: SalesSession) -> tuple[Card, ...]:
    """Return the six headline indicators of the selection (FinancialAnalysis)."""
    _require_sales(session)
    metrics = session.run_financial_analysis().financial
    return (
        Card(t("overview.revenue"), money(metrics.revenue), "blue"),
        Card(t("overview.cost"), money(metrics.cost), "coral"),
        Card(t("overview.profit"), money(metrics.gross_profit), "green"),
        Card(t("overview.margin"), percent(metrics.gross_margin), "purple"),
        Card(t("overview.average"), money(metrics.average_order_value), "amber"),
        Card(t("overview.count"), integer(metrics.sale_count), "teal"),
    )


def top_products_table(session: SalesSession, limit: int = 5) -> Table:
    """Return the best-selling products by revenue (session.top_products)."""
    _require_sales(session)
    rows = tuple(
        (str(position), row.product_id, row.name, money(row.revenue))
        for position, row in enumerate(session.top_products(limit), start=1)
    )
    return Table(
        t("overview.top_products"),
        ("#", t("catalog.col.id"), t("catalog.col.name"), t("analyses.col.revenue")),
        rows,
        numeric=(0, 3),
    )


# -- analyses ---------------------------------------------------------------------------


def _total_row(session: SalesSession, first: str) -> tuple[str, ...]:
    """Return a totals row from FinancialAnalysis of the same selection (never a sum here)."""
    metrics = session.run_financial_analysis().financial
    return (
        first,
        money(metrics.revenue),
        money(metrics.cost),
        money(metrics.gross_profit),
        integer(metrics.sale_count),
    )


def analysis_table(
    session: SalesSession, view: AnalysisView, *, zero_missing_days: bool = False
) -> Table:
    """Return one analysis of the selection as a translated table.

    Raise ValueError for an unknown view and NoSalesInSelectionError for an empty
    selection; `zero_missing_days` applies to the temporal and weekday views.
    """
    if view not in ANALYSIS_VIEWS:
        raise ValueError("unknown analysis view")
    _require_sales(session)
    title = t(f"analyses.view.{view}")
    utc = (t("common.utc_days"),) if session.data_is_aware() else ()
    policy = "zero" if zero_missing_days else "reject"
    if view == "financial":
        cards = financial_cards(session)
        return Table(
            title,
            (t("analyses.col.metric"), t("analyses.col.value")),
            tuple((card.label, card.value) for card in cards),
            numeric=(1,),
        )
    if view == "products":
        result = session.run_product_analysis()
        names = {p.id: p.name for p in session.require_current().products}
        rows = tuple(
            (
                row.product_id,
                names.get(row.product_id, "?"),
                integer(row.quantity),
                money(row.revenue),
                money(row.gross_profit),
            )
            for row in result.products
        )
        notes = (
            t("analyses.ranking_quantity", ids=id_list(result.quantity_ranking)),
            t("analyses.ranking_revenue", ids=id_list(result.revenue_ranking)),
        )
        headers = (
            t("catalog.col.id"),
            t("catalog.col.name"),
            t("analyses.col.quantity"),
            t("analyses.col.revenue"),
            t("analyses.col.profit"),
        )
        return Table(title, headers, rows, numeric=(2, 3, 4), notes=notes)
    if view == "category":
        rows = tuple(
            (
                row.category,
                integer(row.quantity),
                money(row.revenue),
                money(row.cost),
                money(row.gross_profit),
            )
            for row in session.category_totals()
        )
        headers = (
            t("analyses.col.category"),
            t("analyses.col.quantity"),
            t("analyses.col.revenue"),
            t("analyses.col.cost"),
            t("analyses.col.profit"),
        )
        return Table(title, headers, rows, numeric=(1, 2, 3, 4))
    if view == "weekday":
        rows = tuple(
            (
                weekday(row.weekday),
                integer(row.occurrences),
                money(row.total_revenue),
                money(row.average_revenue),
            )
            for row in session.weekday_profile(missing_days=policy)
        )
        note = "analyses.weekday_zero" if zero_missing_days else "analyses.weekday_sales_only"
        headers = (
            t("analyses.col.weekday"),
            t("analyses.col.days"),
            t("analyses.col.revenue"),
            t("analyses.col.average"),
        )
        return Table(title, headers, rows, numeric=(1, 2, 3), notes=(t(note), *utc))
    summary = session.sales_over_time(view, missing_days=policy)
    rows = tuple(
        (
            row.label if view != "day" else day(row.start),
            money(row.revenue),
            money(row.cost),
            money(row.gross_profit),
            integer(row.sale_count),
        )
        for row in summary.rows
    )
    notes: list[str] = []
    if summary.missing_days:
        notes.append(t("analyses.missing", count=summary.missing_days))
        notes.append(
            t("analyses.zero_filled" if summary.zero_filled else "analyses.missing_listed")
        )
    headers = (
        t("analyses.col.period"),
        t("analyses.col.revenue"),
        t("analyses.col.cost"),
        t("analyses.col.profit"),
        t("analyses.col.sales"),
    )
    return Table(
        title,
        headers,
        (*rows, _total_row(session, t("common.total"))),
        numeric=(1, 2, 3, 4),
        notes=(*notes, *utc),
        total_row=True,
    )


def period_comparison_table(session: SalesSession, first: Selection, second: Selection) -> Table:
    """Return two periods side by side with the service's changes (selection unchanged)."""
    comparison = session.compare_periods(first, second)
    a, b = comparison.first, comparison.second
    rows = (
        (t("overview.revenue"), money(a.revenue), money(b.revenue),
         signed_money(comparison.revenue_change),
         percent(comparison.revenue_change_ratio, signed=True)),
        (t("overview.cost"), money(a.cost), money(b.cost),
         signed_money(comparison.cost_change), percent(comparison.cost_change_ratio, signed=True)),
        (t("overview.profit"), money(a.gross_profit), money(b.gross_profit),
         signed_money(comparison.gross_profit_change),
         percent(comparison.gross_profit_change_ratio, signed=True)),
        (t("overview.margin"), percent(a.gross_margin), percent(b.gross_margin),
         t("common.not_available"), t("common.not_available")),
        (t("overview.count"), integer(a.sale_count), integer(b.sale_count),
         integer(comparison.sale_count_change, signed=True),
         percent(comparison.sale_count_change_ratio, signed=True)),
    )  # fmt: skip
    headers = (
        "",
        f"{t('analyses.col.first')} ({period_text(first)})",
        f"{t('analyses.col.second')} ({period_text(second)})",
        t("analyses.col.change"),
        t("analyses.col.change_pct"),
    )
    return Table(
        t("analyses.view.compare"), headers, rows, numeric=(1, 2, 3, 4),
        notes=(t("analyses.compare_note"),),
    )  # fmt: skip


# -- forecasts --------------------------------------------------------------------------


def explain_forecast_refusal(error: Exception) -> str:
    """Return a translated explanation of a forecast or comparison refusal."""
    if isinstance(error, InsufficientHistoryError):
        return t(
            "forecast.short_history",
            available=t("common.days", count=error.available_days),
            required=t("common.days", count=error.required_days),
        )
    if isinstance(error, NoSalesInSelectionError):
        return t("error.no_sales")
    if is_missing_days_error(error):
        return t("forecast.missing_days")
    message = str(error)
    if "constant" in message or "must vary" in message:
        return t("forecast.constant")
    if "calendar range" in message:
        return t("forecast.too_far")
    if "finite" in message:
        return t("forecast.too_large")
    return t("error.invalid_value", detail=message)


def _estimates_table(title: str, rows: tuple[tuple[str, ...], ...]) -> Table:
    return Table(title, (t("forecast.col.day"), t("forecast.col.estimate")), rows, numeric=(1,))


def linear_forecast_report(
    session: SalesSession,
    *,
    horizon: int,
    test_days: int,
    zero_missing_days: bool = False,
    utc_offset: timedelta | None = None,
) -> Report:
    """Run the level 2 linear forecast and return its tables (service errors propagate)."""
    _require_sales(session)
    result: ForecastResult = session.run_forecast(
        horizon=horizon,
        test_days=test_days,
        missing_days="zero" if zero_missing_days else "reject",
        utc_offset=utc_offset,
    )
    model, baseline = result.model_errors, result.baseline_errors
    errors = Table(
        t("forecast.linear_title"),
        (t("forecast.col.method"), t("forecast.col.mae"), t("forecast.col.rmse")),
        (
            (t("forecast.model"), decimal_number(model.mae), decimal_number(model.rmse)),
            (t("forecast.baseline"), decimal_number(baseline.mae), decimal_number(baseline.rmse)),
        ),
        numeric=(1, 2),
        notes=(t("forecast.split", training=len(result.training), test=len(result.test)),),
    )
    if model.mae < baseline.mae:
        better = "forecast.better.model"
    elif model.mae > baseline.mae:
        better = "forecast.better.baseline"
    else:
        better = "forecast.better.tie"
    estimates = _estimates_table(
        t("forecast.estimates", title=t("forecast.model"),
          days=t("common.days", count=len(result.future))),
        tuple((day(p.day), decimal_number(p.revenue)) for p in result.future),
    )  # fmt: skip
    return Report((errors, estimates), (t(better), t("forecast.linear_limits")))


@dataclass(frozen=True)
class ComparisonReport:
    """A forecast comparison result with its translated tables and notes."""

    result: ComparisonResult
    report: Report


def comparison_report(
    session: SalesSession,
    *,
    horizon: int,
    zero_missing_days: bool = False,
    utc_offset: timedelta | None = None,
    method: str | None = None,
) -> ComparisonReport:
    """Compare the forecast methods (optionally forcing the estimate method)."""
    _require_sales(session)
    result = session.compare_forecasts(
        horizon=horizon,
        missing_days="zero" if zero_missing_days else "reject",
        utc_offset=utc_offset,
        method=method,
    )
    scores = Table(
        t("forecast.comparison_title"),
        (
            t("forecast.col.method"),
            t("forecast.col.kind"),
            t("forecast.col.mae"),
            t("forecast.col.rmse"),
            t("forecast.col.relative"),
        ),
        tuple(
            (
                method_title(s.method_key, s.title),
                t(f"forecast.kind.{s.kind}"),
                decimal_number(s.mae),
                decimal_number(s.rmse),
                t("common.not_available") if s.relative_mae is None
                else decimal_number(s.relative_mae),
            )
            for s in result.scores
        ),
        numeric=(2, 3, 4),
        notes=(
            t(
                "forecast.history",
                days=t("common.days", count=result.history_days),
                first=day(result.first_day),
                last=day(result.last_day),
                blocks=t("forecast.blocks", count=result.blocks),
                block_days=result.block_days,
                origin=day(result.origins[0]),
            ),
        ),
    )  # fmt: skip
    notes: list[str] = [
        t(f"forecast.skipped.{s.reason}", title=method_title(s.method_key, s.title),
          needed=s.needed_days)
        for s in result.skipped
    ]  # fmt: skip
    if result.lowest_error_key is None:
        notes.append(
            t("forecast.weak_evidence", days=t("common.days", count=result.evaluated_days))
        )
    else:
        lowest = next(s for s in result.scores if s.method_key == result.lowest_error_key)
        notes.append(t("forecast.lowest", title=method_title(lowest.method_key, lowest.title)))
    if not result.weak_evidence and any(s.kind == "model" for s in result.scores):
        if not result.model_beats_baselines:
            notes.append(t("forecast.no_model_beats"))
        if not result.clear_difference:
            notes.append(t("forecast.no_clear_difference"))
    if result.zero_filled_days:
        notes.append(t("forecast.zero_filled", count=result.zero_filled_days))
    if result.floored_evaluation_days:
        notes.append(t("forecast.floored_eval", count=result.floored_evaluation_days))
    notes.append(t("forecast.metric_help"))
    floored = set(result.floored_future_days)
    chosen = method_title(result.chosen_key, result.chosen_title)
    estimates = _estimates_table(
        t("forecast.estimates", title=chosen, days=t("common.days", count=len(result.future))),
        tuple(
            (day(p.day), decimal_number(p.revenue)
             + (f" ({t('forecast.floored_note')})" if p.day in floored else ""))
            for p in result.future
        ),
    )  # fmt: skip
    if result.fit is not None:
        trend = decimal_number(result.fit.trend_per_day, signed=True)
        if result.fit.weekday_effects is None:
            notes.append(t("forecast.trend", value=trend))
        else:
            effects = ", ".join(
                f"{weekday(index + 1)} {decimal_number(effect, signed=True)}"
                for index, effect in enumerate(result.fit.weekday_effects)
            )
            notes.append(t("forecast.weekday_effects", effects=effects, trend=trend))
    if result.extrapolation_warning:
        notes.append(t("forecast.extrapolation", days=result.block_days))
    notes.append(t("forecast.comparison_limits"))
    return ComparisonReport(result, Report((scores, estimates), tuple(notes)))
