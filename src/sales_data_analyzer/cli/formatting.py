"""Turn results into plain terminal text; rounding happens only here."""

from decimal import ROUND_HALF_UP, Decimal

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
