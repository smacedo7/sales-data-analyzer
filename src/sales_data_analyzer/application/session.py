"""In-memory session state shared by every user interface."""

from sales_data_analyzer.domain.company import Company

from .errors import CompanyNotFoundError, DuplicateCompanyError, NoCompanySelectedError
from .workspace import CompanyWorkspace


class SalesSession:
    """Companies and selection for one program run; nothing is persisted."""

    def __init__(self) -> None:
        """Start an empty session with no selected company."""
        self._workspaces: list[CompanyWorkspace] = []
        self._current: CompanyWorkspace | None = None

    @property
    def workspaces(self) -> tuple[CompanyWorkspace, ...]:
        """Return the company workspaces in creation order."""
        return tuple(self._workspaces)

    @property
    def current(self) -> CompanyWorkspace | None:
        """Return the selected workspace, or None before any selection."""
        return self._current

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
        """
        company = Company(name, sector)
        key = company.name.casefold()
        if any(w.company.name.casefold() == key for w in self._workspaces):
            raise DuplicateCompanyError()
        workspace = CompanyWorkspace(company)
        self._workspaces.append(workspace)
        self._select(workspace)
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
        """Make workspace current."""
        self._current = workspace
