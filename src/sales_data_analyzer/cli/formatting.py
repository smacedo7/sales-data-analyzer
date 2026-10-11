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
from sales_data_analyzer.forecasting import ForecastResult

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
        f"Imported {summary.sales_added} sales, {summary.items_added} items. "
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
