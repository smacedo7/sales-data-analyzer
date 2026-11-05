"""Tabs of the main window, in display order."""

from .catalog import CatalogPage
from .sales import SalesPage

DEFAULT_PAGES = (CatalogPage, SalesPage)
"""Page classes shown by default."""

__all__ = ["DEFAULT_PAGES", "CatalogPage", "SalesPage"]
