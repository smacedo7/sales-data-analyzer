"""Session state shared by every user interface, optionally backed by a repository."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal

from sales_data_analyzer.analysis import AnalysisResult, FinancialAnalysis, ProductAnalysis
from sales_data_analyzer.domain.company import Company
from sales_data_analyzer.domain.sales_dataset import SalesDataset
from sales_data_analyzer.domain.validation import validate_non_empty_string
from sales_data_analyzer.exploration import (
    CategoryTotal,
    PeriodComparison,
    TemporalSummary,
    WeekdayProfile,
    category_totals,
    compare_periods,
    temporal_summary,
    weekday_profile,
)
from sales_data_analyzer.forecasting import (
    MIN_HISTORY_DAYS,
    ComparisonResult,
    ForecastResult,
    RevenueForecaster,
    compare_methods,
    daily_revenue,
)

from .errors import (
    CompanyNotFoundError,
    DuplicateCompanyError,
    InsufficientHistoryError,
    InvalidPeriodError,
    NoCompanySelectedError,
    NoSalesInSelectionError,
)
from .repository import SalesRepository
from .workspace import CompanyWorkspace

MIN_TRAINING_DAYS = 5
"""Training days the existing RevenueForecaster requires before the test days."""


@dataclass(frozen=True)
class Selection:
    """All sales (no dates) or the whole days from start to end, both included."""

    start: date | None = None
    end: date | None = None

    def __post_init__(self) -> None:
        """Require both dates or neither, in order, before the last calendar day."""
        if (self.start is None) != (self.end is None):
            raise InvalidPeriodError("a period needs both a start and an end date")
        if self.start is None or self.end is None:
            return
        if not isinstance(self.start, date) or not isinstance(self.end, date):
            raise TypeError("start and end must be dates")
        if isinstance(self.start, datetime) or isinstance(self.end, datetime):
            raise TypeError("start and end must be dates without time")
        if self.start > self.end:
            raise InvalidPeriodError("the end date is before the start date")
        if self.end >= date.max:
            raise InvalidPeriodError("the end date must be on or before 9999-12-30")

    @property
    def is_all(self) -> bool:
        """Return True when every sale is selected."""
        return self.start is None

    def describe(self) -> str:
        """Return a short human description such as 'all data'."""
        if self.start is None or self.end is None:
            return "all data"
        return f"{self.start.isoformat()} to {self.end.isoformat()}"


class SalesSession:
    """Companies and selection for one program run.

    Without a repository nothing is persisted (level 2). With one, companies and
    their data are stored as they change; the selection is never stored.
    """

    def __init__(self, repository: SalesRepository | None = None) -> None:
        """Start an empty session with no selected company."""
        if repository is not None and not isinstance(repository, SalesRepository):
            raise TypeError("repository must be a SalesRepository")
        self._repository = repository
        self._workspaces: list[CompanyWorkspace] = []
        self._current: CompanyWorkspace | None = None
        self._selection = Selection()

    @classmethod
    def open(cls, repository: SalesRepository) -> "SalesSession":
        """Return a session holding every company stored in repository, none selected.

        Errors raised by the repository's load (for example invalid stored rows)
        propagate unchanged.
        """
        session = cls(repository)
        session._workspaces = [
            CompanyWorkspace.from_stored(stored, repository) for stored in repository.load()
        ]
        return session

    @property
    def repository(self) -> SalesRepository | None:
        """Return the repository storing this session's data, or None in memory mode."""
        return self._repository

    @property
    def workspaces(self) -> tuple[CompanyWorkspace, ...]:
        """Return the company workspaces in creation order."""
        return tuple(self._workspaces)

    @property
    def current(self) -> CompanyWorkspace | None:
        """Return the selected workspace, or None before any selection."""
        return self._current

    @property
    def selection(self) -> Selection:
        """Return the active selection (reset to all data when the company changes)."""
        return self._selection

    def require_current(self) -> CompanyWorkspace:
        """Return the selected workspace or raise NoCompanySelectedError."""
        if self._current is None:
            raise NoCompanySelectedError()
        return self._current

    def create_company(self, name: str, sector: str) -> CompanyWorkspace:
        """Create, register and select a company.

        Names are unique ignoring case and surrounding spaces. Raise
        DuplicateCompanyError for a used name and the Company validation errors
        (TypeError/ValueError) for invalid values; the session is unchanged then.
        With a repository the company is stored first (PersistenceError on failure).
        """
        company = Company(name, sector)
        key = company.name.casefold()
        if any(w.company.name.casefold() == key for w in self._workspaces):
            raise DuplicateCompanyError()
        workspace = CompanyWorkspace(company, self._repository)
        if self._repository is not None:
            self._repository.add_company(company)
        self._workspaces.append(workspace)
        self._select(workspace)
        return workspace

    def update_company(self, name: str | None, sector: str | None) -> CompanyWorkspace:
        """Rename and/or change the sector of the selected company; None keeps a value.

        Both values are validated before anything is written (TypeError/ValueError).
        Raise DuplicateCompanyError when another company already uses the name
        (ignoring case and surrounding spaces). With a repository the change is
        stored first; on PersistenceError the company keeps its old values.
        """
        workspace = self.require_current()
        company = workspace.company
        new_name = validate_non_empty_string(company.name if name is None else name, "name")
        new_sector = validate_non_empty_string(
            company.sector if sector is None else sector, "sector"
        )
        key = new_name.casefold()
        if any(w is not workspace and w.company.name.casefold() == key for w in self._workspaces):
            raise DuplicateCompanyError()
        if self._repository is not None:
            self._repository.update_company(company, new_name, new_sector)
        company.name = new_name
        company.sector = new_sector
        return workspace

    def select_company(self, index: int) -> CompanyWorkspace:
        """Select the company at a 1-based position in creation order."""
        if isinstance(index, bool) or not isinstance(index, int):
            raise TypeError("index must be an integer")
        if not 1 <= index <= len(self._workspaces):
            raise CompanyNotFoundError(len(self._workspaces))
        workspace = self._workspaces[index - 1]
        self._select(workspace)
        return workspace

    def _select(self, workspace: CompanyWorkspace) -> None:
        """Make workspace current and select all of its data."""
        self._current = workspace
        self._selection = Selection()

    # -- selection ----------------------------------------------------------------

    def set_period(self, start: date, end: date) -> None:
        """Select the whole days from start to end, both included.

        Raise InvalidPeriodError when end is before start or is the last
        representable day, keeping the previous selection.
        """
        self.require_current()
        self._selection = Selection(start, end)

    def clear_period(self) -> None:
        """Select all data of the current company again."""
        self.require_current()
        self._selection = Selection()

    def data_is_aware(self) -> bool:
        """Return True when the current company's sales carry UTC offsets."""
        sales = self.require_current().sales.sales
        return bool(sales) and sales[0].date_time.utcoffset() is not None

    def selected_sales(self) -> SalesDataset:
        """Return the current company's sales inside the active selection.

        Period days are local calendar days for naive data and UTC days for
        data with offsets (imports normalize offsets to UTC).
        """
        return self._sales_in(self._selection)

    def _sales_in(self, selection: Selection) -> SalesDataset:
        """Return the current company's sales inside selection (see selected_sales)."""
        workspace = self.require_current()
        if not isinstance(selection, Selection):
            raise TypeError("selection must be a Selection")
        if selection.start is None or selection.end is None:
            return workspace.sales
        zone = timezone.utc if self.data_is_aware() else None
        start = datetime.combine(selection.start, time(), zone)
        end = datetime.combine(selection.end + timedelta(days=1), time(), zone)
        return workspace.sales.filter_period(start, end)

    # -- analyses -------------------------------------------------------------------

    def run_financial_analysis(self) -> AnalysisResult:
        """Run the existing FinancialAnalysis on the selected sales."""
        return FinancialAnalysis().run(self.selected_sales())

    def run_product_analysis(self) -> AnalysisResult:
        """Run the existing ProductAnalysis on the selected sales."""
        return ProductAnalysis().run(self.selected_sales())

    # -- exploration ----------------------------------------------------------------

    def _day_zone(self) -> timezone | None:
        """Return UTC for data with offsets (days are UTC days), None for naive data."""
        return timezone.utc if self.data_is_aware() else None

    def sales_over_time(
        self,
        granularity: Literal["day", "week", "month"],
        *,
        missing_days: Literal["reject", "zero"] = "reject",
    ) -> TemporalSummary:
        """Group the selected sales by day, ISO week or month (exact totals).

        Raise NoSalesInSelectionError for an empty selection.
        """
        data = self._require_selected_sales()
        return temporal_summary(
            data, granularity, missing_days=missing_days, timezone=self._day_zone()
        )

    def weekday_profile(
        self, *, missing_days: Literal["reject", "zero"] = "reject"
    ) -> tuple[WeekdayProfile, ...]:
        """Return revenue per weekday of the selected sales, Monday first.

        Raise NoSalesInSelectionError for an empty selection.
        """
        data = self._require_selected_sales()
        return weekday_profile(data, missing_days=missing_days, timezone=self._day_zone())

    def category_totals(self) -> tuple[CategoryTotal, ...]:
        """Return revenue, cost and gross profit per catalog category of the selection.

        Raise NoSalesInSelectionError for an empty selection.
        """
        data = self._require_selected_sales()
        categories = {p.id: p.category for p in self.require_current().products}
        return category_totals(data, categories)

    def compare_periods(self, first: Selection, second: Selection) -> PeriodComparison:
        """Compare two periods of the current company; the active selection is unchanged.

        Either period may be empty (its totals are zero and ratios against it None).
        """
        return compare_periods(self._sales_in(first), self._sales_in(second))

    def _require_selected_sales(self) -> SalesDataset:
        """Return the selected sales or raise NoSalesInSelectionError when there are none."""
        data = self.selected_sales()
        if not data.sales:
            raise NoSalesInSelectionError()
        return data

    # -- forecast -------------------------------------------------------------------

    def run_forecast(
        self,
        *,
        horizon: int = 7,
        test_days: int = 2,
        missing_days: Literal["reject", "zero"] = "reject",
        utc_offset: timedelta | None = None,
    ) -> ForecastResult:
        """Run the existing RevenueForecaster on the selected sales.

        Data with offsets is grouped into days of ``utc_offset`` (default UTC);
        naive data ignores it. Raise NoSalesInSelectionError for an empty
        selection and InsufficientHistoryError when the calendar span from the
        first to the last sale is shorter than five training days plus
        ``test_days``. Other forecaster TypeError/ValueError (missing days,
        constant revenue, invalid counts) propagate unchanged.
        """
        data = self.selected_sales()
        if not data.sales:
            raise NoSalesInSelectionError()
        zone = None
        if self.data_is_aware():
            zone = timezone(utc_offset if utc_offset is not None else timedelta(0))
        if not isinstance(test_days, bool) and isinstance(test_days, int) and test_days >= 2:
            available = len(daily_revenue(data, missing_days="zero", timezone=zone))
            required = MIN_TRAINING_DAYS + test_days
            if available < required:
                raise InsufficientHistoryError(available, required)
        return RevenueForecaster().forecast(
            data, horizon=horizon, test_days=test_days, missing_days=missing_days, timezone=zone
        )

    def compare_forecasts(
        self,
        *,
        horizon: int = 7,
        missing_days: Literal["reject", "zero"] = "reject",
        utc_offset: timedelta | None = None,
        method: str | None = None,
    ) -> ComparisonResult:
        """Compare the forecast methods on the selected sales and forecast horizon days.

        Days follow `run_forecast` (UTC offset grouping for data with offsets). Raise
        NoSalesInSelectionError for an empty selection and InsufficientHistoryError
        below 12 calendar days. The missing-day refusal and other comparison
        ValueErrors propagate unchanged. The level 2 forecast is not affected.
        """
        data = self.selected_sales()
        if not data.sales:
            raise NoSalesInSelectionError()
        zone = None
        if self.data_is_aware():
            zone = timezone(utc_offset if utc_offset is not None else timedelta(0))
        filled = daily_revenue(data, missing_days="zero", timezone=zone)
        if len(filled) < MIN_HISTORY_DAYS:
            raise InsufficientHistoryError(len(filled), MIN_HISTORY_DAYS)
        history = daily_revenue(data, missing_days=missing_days, timezone=zone)
        sale_days = {
            sale.date_time.astimezone(zone).date() if zone is not None else sale.date_time.date()
            for sale in data.sales
        }
        return compare_methods(
            history, horizon=horizon, method=method, zero_filled_days=len(history) - len(sale_days)
        )
