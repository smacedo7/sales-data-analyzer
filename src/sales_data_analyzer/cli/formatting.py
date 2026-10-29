"""Turn results into plain terminal text; rounding happens only here."""

from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal

from sales_data_analyzer.analysis import AnalysisResult
from sales_data_analyzer.application.errors import (
    InsufficientHistoryError,
    NoSalesInSelectionError,
)
from sales_data_analyzer.application.session import MIN_TRAINING_DAYS
from sales_data_analyzer.application.workspace import ImportSummary
from sales_data_analyzer.domain.product import Product
from sales_data_analyzer.domain.sale import Sale
from sales_data_analyzer.exploration import (
    WEEKDAY_NAMES,
    CategoryTotal,
    PeriodComparison,
    TemporalSummary,
    WeekdayProfile,
)
from sales_data_analyzer.forecasting import ComparisonResult, ForecastResult

_CENT = Decimal("0.01")
_TENTH = Decimal("0.1")
NOT_AVAILABLE = "n/a"


def format_money(amount: Decimal) -> str:
    """Return an amount rounded half up to cents with thousands separators."""
    return f"{amount.quantize(_CENT, rounding=ROUND_HALF_UP):,.2f}"


def format_optional_money(amount: Decimal | None) -> str:
    """Return format_money(amount), or n/a when the value is undefined."""
    return NOT_AVAILABLE if amount is None else format_money(amount)


def format_percent(ratio: Decimal | None) -> str:
    """Return a ratio as a percentage with one decimal, or n/a when undefined."""
    if ratio is None:
        return NOT_AVAILABLE
    return f"{(ratio * 100).quantize(_TENTH, rounding=ROUND_HALF_UP)}%"


def format_float(value: float) -> str:
    """Return a statistical value with two decimals and thousands separators."""
    return f"{value:,.2f}"


def format_id_list(ids: Sequence[str], limit: int = 5) -> str:
    """Return up to limit IDs separated by commas, plus how many were left out."""
    shown = ", ".join(ids[:limit])
    hidden = len(ids) - limit
    return f"{shown} and {hidden} more" if hidden > 0 else shown


def format_import_summary(summary: ImportSummary) -> str:
    """Describe a successful import in one line."""
    return (
        f"Imported {plural(summary.sales_added, 'sale')}, "
        f"{plural(summary.items_added, 'item')}. "
        f"Products: {summary.new_products} new, {summary.reused_products} reused."
    )


def plural(count: int, word: str) -> str:
    """Return '1 sale' or '2 sales' style counts."""
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def format_scope(company_name: str, selection: str, sale_count: int) -> str:
    """Describe what an analysis covered: company, selection and sale count."""
    return f"{company_name} - {selection} ({plural(sale_count, 'sale')})"


def format_financial(result: AnalysisResult, scope: str) -> list[str]:
    """Return the financial analysis as aligned label/value lines."""
    metrics = result.financial
    if metrics is None:
        raise ValueError("result has no financial metrics")
    rows = (
        ("Revenue", format_money(metrics.revenue)),
        ("Cost", format_money(metrics.cost)),
        ("Gross profit", format_money(metrics.gross_profit)),
        ("Gross margin", format_percent(metrics.gross_margin)),
        ("Average order", format_optional_money(metrics.average_order_value)),
        ("Sales", str(metrics.sale_count)),
    )
    width = max(len(value) for _, value in rows)
    lines = [f"Financial analysis - {scope}"]
    lines += [f"{label + ' ':.<20} {value:>{width}}" for label, value in rows]
    return lines


def format_products(
    result: AnalysisResult, scope: str, names: dict[str, str], top: int = 5
) -> list[str]:
    """Return the product table and the top products by quantity and revenue.

    names maps product IDs to catalog names; unknown IDs show '?'.
    """
    lines = [f"Product analysis - {scope}"]
    if not result.products:
        lines.append("No products sold.")
        return lines
    header = ("ID", "Name", "Qty", "Revenue", "Gross profit")
    rows = [
        (
            row.product_id,
            names.get(row.product_id, "?"),
            str(row.quantity),
            format_money(row.revenue),
            format_money(row.gross_profit),
        )
        for row in result.products
    ]
    widths = [max(len(cells[i]) for cells in (header, *rows)) for i in range(len(header))]

    def render(cells: tuple[str, ...]) -> str:
        left = [f"{cells[i]:<{widths[i]}}" for i in (0, 1)]
        right = [f"{cells[i]:>{widths[i]}}" for i in (2, 3, 4)]
        return "  ".join(left + right).rstrip()

    lines.append(render(header))
    lines += [render(cells) for cells in rows]
    lines.append(f"Top by quantity: {', '.join(result.quantity_ranking[:top])}")
    lines.append(f"Top by revenue:  {', '.join(result.revenue_ranking[:top])}")
    return lines


def format_catalog(products: Sequence[Product]) -> list[str]:
    """Return the catalog as an aligned ID/Name/Category table."""
    if not products:
        return ["Catalog is empty."]
    rows = [("ID", "Name", "Category"), *((p.id, p.name, p.category) for p in products)]
    widths = [max(len(row[i]) for row in rows) for i in range(3)]
    return [
        "  ".join(f"{cell:<{widths[i]}}" for i, cell in enumerate(row)).rstrip() for row in rows
    ]


def format_sales(sales: Sequence[Sale]) -> list[str]:
    """Return sales as an aligned table followed by their count."""
    if not sales:
        return ["No sales in the current selection."]
    rows = [
        (
            sale.id,
            sale.date_time.isoformat(),
            str(len(sale.items)),
            format_money(sale.calculate_total()),
        )
        for sale in sales
    ]
    header = ("Sale ID", "Date and time", "Items", "Total")
    return [*format_table(header, rows, left=2), plural(len(sales), "sale")]


def format_table(
    header: Sequence[str], rows: Sequence[Sequence[str]], *, left: int = 1
) -> list[str]:
    """Return aligned columns: the first `left` columns to the left, the rest to the right."""
    widths = [max(len(cells[i]) for cells in (header, *rows)) for i in range(len(header))]

    def render(cells: Sequence[str]) -> str:
        parts = [
            f"{cell:<{widths[i]}}" if i < left else f"{cell:>{widths[i]}}"
            for i, cell in enumerate(cells)
        ]
        return "  ".join(parts).rstrip()

    return [render(header), *(render(cells) for cells in rows)]


def format_temporal(summary: TemporalSummary, scope: str) -> list[str]:
    """Return revenue, cost, gross profit and sales per period with a total row."""
    lines = [f"Sales by {summary.granularity} - {scope}"]
    rows = [
        (
            row.label,
            format_money(row.revenue),
            format_money(row.cost),
            format_money(row.gross_profit),
            str(row.sale_count),
        )
        for row in summary.rows
    ]
    revenue = sum((row.revenue for row in summary.rows), Decimal(0))
    cost = sum((row.cost for row in summary.rows), Decimal(0))
    count = sum(row.sale_count for row in summary.rows)
    rows.append(
        (
            "Total",
            format_money(revenue),
            format_money(cost),
            format_money(revenue - cost),
            str(count),
        )
    )
    lines += format_table(("Period", "Revenue", "Cost", "Gross profit", "Sales"), rows)
    if summary.missing_days:
        if summary.zero_filled:
            lines.append(f"{plural(summary.missing_days, 'day')} without sales shown as zero.")
        else:
            lines.append(
                f"{plural(summary.missing_days, 'day')} without recorded sales "
                "between the first and last sale (periods without sales are not listed)."
            )
    if summary.days_are_utc:
        lines.append("Days are UTC days.")
    return lines


def format_weekdays(
    profile: Sequence[WeekdayProfile], scope: str, *, zero_filled: bool, days_are_utc: bool
) -> list[str]:
    """Return total and average revenue per weekday, Monday first."""
    rows = [
        (
            WEEKDAY_NAMES[row.weekday],
            str(row.occurrences),
            format_money(row.total_revenue),
            format_optional_money(row.average_revenue),
        )
        for row in profile
    ]
    lines = [f"Revenue by weekday - {scope}"]
    lines += format_table(("Weekday", "Days", "Revenue", "Average"), rows)
    if zero_filled:
        lines.append("Averages include days without sales as zero.")
    else:
        lines.append("Averages count only days with sales.")
    if days_are_utc:
        lines.append("Days are UTC days.")
    return lines


def format_categories(totals: Sequence[CategoryTotal], scope: str) -> list[str]:
    """Return item totals per category, highest revenue first."""
    rows = [
        (
            row.category,
            str(row.quantity),
            format_money(row.revenue),
            format_money(row.cost),
            format_money(row.gross_profit),
        )
        for row in totals
    ]
    lines = [f"Sales by category - {scope}"]
    lines += format_table(("Category", "Qty", "Revenue", "Cost", "Gross profit"), rows)
    return lines


def _signed_money(amount: Decimal) -> str:
    """Return a money change with an explicit sign."""
    text = format_money(amount)
    return text if text.startswith("-") else f"+{text}"


def _signed_percent(ratio: Decimal | None) -> str:
    """Return a change ratio as a signed percentage, or n/a when undefined."""
    text = format_percent(ratio)
    return text if ratio is None or text.startswith("-") else f"+{text}"


def format_period_comparison(comparison: PeriodComparison, first: str, second: str) -> list[str]:
    """Return both periods side by side with the absolute and percentage change."""
    a, b = comparison.first, comparison.second
    margin_change = (
        NOT_AVAILABLE
        if a.gross_margin is None or b.gross_margin is None
        else f"{_signed_percent(b.gross_margin - a.gross_margin)[:-1]} pp"
    )
    rows = [
        (
            "Revenue",
            format_money(a.revenue),
            format_money(b.revenue),
            _signed_money(comparison.revenue_change),
            _signed_percent(comparison.revenue_change_ratio),
        ),
        (
            "Cost",
            format_money(a.cost),
            format_money(b.cost),
            _signed_money(comparison.cost_change),
            _signed_percent(comparison.cost_change_ratio),
        ),
        (
            "Gross profit",
            format_money(a.gross_profit),
            format_money(b.gross_profit),
            _signed_money(comparison.gross_profit_change),
            _signed_percent(comparison.gross_profit_change_ratio),
        ),
        (
            "Gross margin",
            format_percent(a.gross_margin),
            format_percent(b.gross_margin),
            margin_change,
            "",
        ),
        (
            "Sales",
            str(a.sale_count),
            str(b.sale_count),
            f"{comparison.sale_count_change:+d}",
            _signed_percent(comparison.sale_count_change_ratio),
        ),
    ]
    lines = [f"Period comparison: first {first}, second {second}"]
    lines += format_table(("", "First", "Second", "Change", "% change"), rows)
    lines.append("Changes are second minus first; % change is relative to the first period.")
    return lines


FORECAST_LIMITATIONS = (
    "Limitations: straight-line trend on the day number only; ignores",
    "seasonality, holidays and promotions; can be worse than the baseline; can",
    "predict negative values; no accuracy guarantee.",
)
"""Notice printed after every forecast result (FR-025)."""

# Forecaster ValueError messages (level 1 wording, pinned by tests) -> plain text.
_MISSING_DAYS = "history has missing days; explicitly select zero only for complete records"
_FORECAST_MESSAGES = {
    _MISSING_DAYS: "Some days between the first and last sale have no sales.",
    "training revenue must vary to learn a trend": (
        "Training revenue is constant, so no trend can be learned."
    ),
    "at least two test days are required": "Test days must be at least 2.",
    "history or horizon exceeds numeric/calendar range": (
        "The forecast would go past the last supported calendar day; use a shorter horizon."
    ),
    "revenue must be finite at the ML boundary": "Daily revenue is too large to forecast.",
    "predictions must be finite": "The forecast produced values too large to show.",
    "evaluation errors exceed finite floating-point range": (
        "The forecast errors are too large to show."
    ),
}


def format_forecast(result: ForecastResult, scope: str) -> list[str]:
    """Return evaluation, future estimates and the limitations notice.

    The better method is the one with the lower MAE on the test days.
    """
    model, baseline = result.model_errors, result.baseline_errors
    maes = (format_float(model.mae), format_float(baseline.mae))
    rmses = (format_float(model.rmse), format_float(baseline.rmse))
    mae_width = max(len(v) for v in maes)
    rmse_width = max(len(v) for v in rmses)
    if model.mae < baseline.mae:
        better = "model"
    elif model.mae > baseline.mae:
        better = "baseline"
    else:
        better = "tie (same MAE)"
    lines = [
        f"Revenue forecast - {scope}",
        f"Training days: {len(result.training)} | Test days: {len(result.test)}",
        f"Model     MAE {maes[0]:<{mae_width}} RMSE {rmses[0]:>{rmse_width}}",
        f"Baseline  MAE {maes[1]:<{mae_width}} RMSE {rmses[1]:>{rmse_width}}"
        " (repeats last training day)",
        f"Better on test days (lower MAE): {better}",
        f"Next {plural(len(result.future), 'day')}:",
    ]
    values = [format_float(p.revenue) for p in result.future]
    width = max((len(v) for v in values), default=0)
    lines += [
        f"{p.day.isoformat()}  {v:>{width}}" for p, v in zip(result.future, values, strict=True)
    ]
    lines += FORECAST_LIMITATIONS
    return lines


def is_missing_days_error(error: Exception) -> bool:
    """Return True when the forecaster refused history with days without sales."""
    return isinstance(error, ValueError) and str(error) == _MISSING_DAYS


def explain_forecast_error(error: Exception) -> str:
    """Return a plain-language explanation of a forecast refusal (FR-026).

    Unknown errors fall back to their own message.
    """
    if isinstance(error, InsufficientHistoryError):
        test_days = error.required_days - MIN_TRAINING_DAYS
        return (
            f"Not enough history: {error.available_days} day(s) available, "
            f"at least {error.required_days} needed "
            f"({MIN_TRAINING_DAYS} training + {test_days} test). Add or import more days."
        )
    if isinstance(error, NoSalesInSelectionError):
        return "No sales in the current selection."
    message = str(error)
    return _FORECAST_MESSAGES.get(message, message)


COMPARISON_LIMITATIONS = (
    "Limitations: past errors do not guarantee future accuracy; choosing the lowest error on the",
    "same evaluation is optimistic; holidays and promotions are not modeled; no confidence interval.",
)
"""Notice printed after every forecast comparison (constitution VI)."""

_SKIP_REASONS = {"constant_revenue": "revenue is constant, so no trend can be learned"}
_WEEKDAY_SHORT = ("Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _signed_float(value: float) -> str:
    """Return a statistical value with sign and two decimals, never '-0.00'."""
    rounded = round(value, 2) + 0.0
    return f"{rounded:+,.2f}"


def format_comparison(result: ComparisonResult, scope: str) -> list[str]:
    """Return the evaluation table, skipped methods and the honest-wording notes."""
    first_origin = result.origins[0].isoformat()
    lines = [
        f"Forecast comparison - {scope}",
        f"History: {plural(result.history_days, 'day')} ({result.first_day.isoformat()} to "
        f"{result.last_day.isoformat()}); evaluation: {plural(result.blocks, 'block')} of "
        f"{result.block_days} days from {first_origin}",
    ]
    rows = [
        (
            str(number),
            score.title,
            score.kind,
            format_float(score.mae),
            format_float(score.rmse),
            NOT_AVAILABLE if score.relative_mae is None else format_float(score.relative_mae),
        )
        for number, score in enumerate(result.scores, start=1)
    ]
    lines += format_table(("#", "Method", "Kind", "MAE", "RMSE", "vs last value"), rows, left=3)
    for skipped in result.skipped:
        reason = _SKIP_REASONS.get(skipped.reason) or (
            f"needs {skipped.needed_days} days of history"
        )
        lines.append(f"Skipped: {skipped.title} ({reason})")
    if result.lowest_error_key is None:
        lines.append(
            "Evidence too limited to name a lowest-error method "
            f"({result.evaluated_days} evaluated days)."
        )
    else:
        title = next(s.title for s in result.scores if s.method_key == result.lowest_error_key)
        lines.append(f"Lowest error in this evaluation: {title}.")
    if not result.weak_evidence and any(s.kind == "model" for s in result.scores):
        if not result.model_beats_baselines:
            lines.append("No model beat the best baseline in this evaluation.")
        if not result.clear_difference:
            lines.append(
                "No clear difference between the best model and the best baseline (under 5%)."
            )
    if result.zero_filled_days:
        lines.append(
            f"{plural(result.zero_filled_days, 'missing day')} were treated as zero; "
            "weekly methods learn from these zeros."
        )
    if result.floored_evaluation_days:
        lines.append(
            f"{plural(result.floored_evaluation_days, 'evaluation day')} had negative "
            "estimates floored at 0."
        )
    lines.append(
        "MAE = typical miss in revenue units; RMSE weighs large misses more; "
        "ratio below 1 = lower error here."
    )
    return lines


def format_comparison_estimates(result: ComparisonResult) -> list[str]:
    """Return the chosen method's estimates, its coefficients and the limitations."""
    lines = [f"Estimates ({result.chosen_title}), next {plural(len(result.future), 'day')}:"]
    floored = set(result.floored_future_days)
    values = [format_float(p.revenue) for p in result.future]
    width = max((len(v) for v in values), default=0)
    for prediction, value in zip(result.future, values, strict=True):
        note = "  (negative estimate shown as 0)" if prediction.day in floored else ""
        lines.append(f"{prediction.day.isoformat()}  {value:>{width}}{note}")
    fit = result.fit
    if fit is not None:
        trend = f"trend per day {_signed_float(fit.trend_per_day)}"
        if fit.weekday_effects is None:
            lines.append(f"Fitted line: {trend}.")
        else:
            effects = ", ".join(
                f"{name} {_signed_float(effect)}"
                for name, effect in zip(_WEEKDAY_SHORT, fit.weekday_effects, strict=True)
            )
            lines.append(f"Weekday effects vs Monday: {effects}; {trend}.")
    if result.extrapolation_warning:
        lines.append(
            f"Errors were measured {result.block_days} days ahead; "
            "estimates beyond 14 days are extrapolation."
        )
    lines += COMPARISON_LIMITATIONS
    return lines
