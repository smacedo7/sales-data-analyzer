"""In-memory session state shared by every user interface."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .errors import NoCompanySelectedError

if TYPE_CHECKING:
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
