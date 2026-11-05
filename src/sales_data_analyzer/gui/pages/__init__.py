"""Pages of the main window, in navigation order."""

from .analyses import AnalysesPage
from .catalog import CatalogPage
from .charts import ChartsPage
from .forecast import ForecastPage
from .home import HomePage
from .overview import OverviewPage
from .sales import SalesPage

DEFAULT_PAGES = (
    HomePage, OverviewPage, CatalogPage, SalesPage, AnalysesPage, ForecastPage, ChartsPage,
)  # fmt: skip
"""Page classes shown by default."""

__all__ = [
    "DEFAULT_PAGES",
    "AnalysesPage",
    "CatalogPage",
    "ChartsPage",
    "ForecastPage",
    "HomePage",
    "OverviewPage",
    "SalesPage",
]
