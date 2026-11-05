"""Tabs of the main window, in display order."""

from .analyses import AnalysesPage
from .catalog import CatalogPage
from .charts import ChartsPage
from .forecast import ForecastPage
from .sales import SalesPage

DEFAULT_PAGES = (CatalogPage, SalesPage, AnalysesPage, ForecastPage, ChartsPage)
"""Page classes shown by default."""

__all__ = [
    "DEFAULT_PAGES",
    "AnalysesPage",
    "CatalogPage",
    "ChartsPage",
    "ForecastPage",
    "SalesPage",
]
