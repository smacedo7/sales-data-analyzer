"""Tabs of the main window, in display order."""

from .analyses import AnalysesPage
from .catalog import CatalogPage
from .sales import SalesPage

DEFAULT_PAGES = (CatalogPage, SalesPage, AnalysesPage)
"""Page classes shown by default."""

__all__ = ["DEFAULT_PAGES", "AnalysesPage", "CatalogPage", "SalesPage"]
