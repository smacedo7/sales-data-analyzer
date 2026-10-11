"""Turn results into plain terminal text; rounding happens only here."""

from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal

from sales_data_analyzer.analysis import AnalysisResult
from sales_data_analyzer.application.workspace import ImportSummary

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
