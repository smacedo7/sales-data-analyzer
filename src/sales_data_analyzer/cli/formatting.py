"""Turn results into plain terminal text; rounding happens only here."""

from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal

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
