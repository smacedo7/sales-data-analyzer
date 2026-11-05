"""Typed chart values shared by every user interface (no drawing library here)."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

UNKNOWN_PRODUCT_NAME = "?"
"""Name shown for a ranked product ID that is no longer in the catalog."""


@dataclass(frozen=True)
class ProductRevenue:
    """Exact revenue of one product ID in the selection, with its catalog name."""

    product_id: str
    name: str
    revenue: Decimal

    @property
    def label(self) -> str:
        """Return the 'ID name' text used on chart axes."""
        return f"{self.product_id} {self.name}"


@dataclass(frozen=True)
class ChartData:
    """Exact values of the daily, monthly and top-product charts of one selection.

    `forecast` holds the comparison's chosen-method estimates (floats, the
    statistical boundary) and is empty when the comparison refused the history;
    `forecast_refusal` then holds that refusal so each adapter can word it.
    """

    title: str
    daily: tuple[tuple[date, Decimal], ...]
    monthly: tuple[tuple[str, Decimal], ...]
    top_products: tuple[ProductRevenue, ...]
    forecast: tuple[tuple[date, float], ...] = ()
    forecast_title: str | None = None
    forecast_refusal: ValueError | None = None
    weekday: tuple[tuple[int, Decimal | None], ...] = ()
    """(weekday, average revenue over days with sales), Monday = 0; None without sales."""
    forecast_key: str | None = None
    """Method key behind `forecast` (lets interfaces translate the method name)."""
