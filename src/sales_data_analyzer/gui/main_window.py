"""Main window: database, company and period bar plus one tab per task.

The window holds one SalesSession for the whole run and is a thin view of it:
after every successful action it redraws from the session, and every action
runs through `attempt`, the single place where failures become messages.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from sales_data_analyzer.application import SalesSession

from . import reports
from .messages import describe_failure
from .prompter import Prompter, QtPrompter

WINDOW_TITLE = "Sales Data Analyzer"


class Page(QWidget):
    """A tab that redraws itself from the window's session."""

    title = "Page"

    def __init__(self, window: "MainWindow") -> None:
        """Keep the owning window (session, prompter and attempt)."""
        super().__init__()
        self.window_ = window

    @property
    def session(self) -> SalesSession:
        """Return the window's session."""
        return self.window_.session

    def refresh(self) -> None:
        """Redraw from the session; called after every successful change."""


@contextmanager
def busy_cursor() -> Iterator[None]:
    """Show the wait cursor while a service call runs on the GUI thread."""
    QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        yield
    finally:
        QGuiApplication.restoreOverrideCursor()


def to_qdate(day: date) -> QDate:
    """Return the Qt date of a calendar date."""
    return QDate(day.year, day.month, day.day)


def to_date(value: QDate) -> date:
    """Return the calendar date of a Qt date."""
    return date(value.year(), value.month(), value.day())


class MainWindow(QMainWindow):
    """The desktop interface over one session (and its repository, if any)."""

    def __init__(
        self,
        session: SalesSession,
        prompter: Prompter | None = None,
        pages: tuple[type[Page], ...] | None = None,
    ) -> None:
        """Build the window for session; prompter defaults to Qt dialogs."""
        super().__init__()
        if not isinstance(session, SalesSession):
            raise TypeError("session must be a SalesSession")
        self.session = session
        self.prompter: Prompter = prompter if prompter is not None else QtPrompter(self)
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1100, 720)

        self.company_box = QComboBox()
        self.company_box.setMinimumWidth(240)
        self.company_box.activated.connect(self._company_chosen)
        self.new_company_button = QPushButton("New company…")
        self.new_company_button.clicked.connect(self.new_company)
        self.edit_company_button = QPushButton("Edit company…")
        self.edit_company_button.clicked.connect(self.edit_company)

        self.start_edit = QDateEdit()
        self.end_edit = QDateEdit()
        for edit in (self.start_edit, self.end_edit):
            edit.setCalendarPopup(True)
            edit.setDisplayFormat("yyyy-MM-dd")
            edit.setDate(to_qdate(date.today()))
        self.apply_period_button = QPushButton("Apply period")
        self.apply_period_button.clicked.connect(self.apply_period)
        self.all_data_button = QPushButton("All data")
        self.all_data_button.clicked.connect(self.clear_period)
        self.selection_label = QLabel()
        self.selection_label.setObjectName("selectionLabel")

        company_row = QHBoxLayout()
        company_row.addWidget(QLabel("Company"))
        company_row.addWidget(self.company_box)
        company_row.addWidget(self.new_company_button)
        company_row.addWidget(self.edit_company_button)
        company_row.addStretch()
        period_row = QHBoxLayout()
        period_row.addWidget(QLabel("From"))
        period_row.addWidget(self.start_edit)
        period_row.addWidget(QLabel("To"))
        period_row.addWidget(self.end_edit)
        period_row.addWidget(self.apply_period_button)
        period_row.addWidget(self.all_data_button)
        period_row.addSpacing(16)
        period_row.addWidget(self.selection_label, 1)

        self.tabs = QTabWidget()
        if pages is None:
            from .pages import DEFAULT_PAGES

            pages = DEFAULT_PAGES
        self.pages = tuple(page(self) for page in pages)
        for page in self.pages:
            self.tabs.addTab(page, page.title)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addLayout(company_row)
        layout.addLayout(period_row)
        layout.addWidget(self.tabs, 1)
        self.setCentralWidget(central)

        repository = session.repository
        location = repository.location if repository is not None else "memory only (not saved)"
        self.database_label = QLabel(f"Database: {location}")
        self.statusBar().addPermanentWidget(self.database_label)
        self.refresh()

    # -- the error funnel -----------------------------------------------------------

    def attempt[T](self, action: Callable[[], T]) -> T | None:
        """Run action and return its result, or show why it failed and return None.

        Services validate before writing, so a failure leaves the session and the
        database unchanged; the window redraws from the session either way.
        """
        try:
            with busy_cursor():
                return action()
        except Exception as error:  # the window must survive any failure
            self.prompter.warn(describe_failure(error))
            self._safe_refresh()
            return None

    def _safe_refresh(self) -> None:
        """Redraw, reporting (once) a failure of the redraw itself."""
        try:
            self.refresh()
        except Exception as error:
            self.prompter.warn(describe_failure(error))

    # -- drawing ------------------------------------------------------------------

    def refresh(self) -> None:
        """Redraw the company bar, the selection and every page from the session."""
        self.company_box.blockSignals(True)
        self.company_box.clear()
        self.company_box.addItem("No company selected", None)
        current_index = 0
        for number, workspace in enumerate(self.session.workspaces, start=1):
            company = workspace.company
            self.company_box.addItem(f"{company.name} ({company.sector})", number)
            if workspace is self.session.current:
                current_index = number
        self.company_box.setCurrentIndex(current_index)
        self.company_box.blockSignals(False)

        has_company = self.session.current is not None
        for widget in (
            self.edit_company_button,
            self.start_edit,
            self.end_edit,
            self.apply_period_button,
            self.all_data_button,
            self.tabs,
        ):
            widget.setEnabled(has_company)
        selection = self.session.selection
        if selection.start is not None and selection.end is not None:
            self.start_edit.setDate(to_qdate(selection.start))
            self.end_edit.setDate(to_qdate(selection.end))
        self.selection_label.setText(reports.selection_text(self.session))
        for page in self.pages:
            page.refresh()

    # -- companies ------------------------------------------------------------------

    def _company_chosen(self, index: int) -> None:
        """Select the company behind a combo box entry (the placeholder keeps the current)."""
        number = self.company_box.itemData(index)
        if number is None:
            self.refresh()
            return
        if self.attempt(lambda: self.session.select_company(number)) is not None:
            self.refresh()

    def new_company(self) -> None:
        """Ask for a company, create it and select it."""
        values = self.prompter.company_form()
        if values is None:
            return
        workspace = self.attempt(lambda: self.session.create_company(values.name, values.sector))
        if workspace is not None:
            self.refresh()
            self.statusBar().showMessage(f"Company created: {workspace.company.name}", 5000)

    def edit_company(self) -> None:
        """Ask for the selected company's new name and sector and store both."""
        current = self.session.current
        if current is None:
            self.prompter.warn("Not done: create or select a company first.")
            return
        values = self.prompter.company_form(current.company.name, current.company.sector)
        if values is None:
            return
        if self.attempt(lambda: self.session.update_company(values.name, values.sector)):
            self.refresh()

    # -- period ---------------------------------------------------------------------

    def apply_period(self) -> None:
        """Select the days from the From date to the To date, both included."""
        start, end = to_date(self.start_edit.date()), to_date(self.end_edit.date())
        if self.attempt(lambda: self.session.set_period(start, end) or True):
            self.refresh()

    def clear_period(self) -> None:
        """Select all data of the current company again."""
        if self.attempt(lambda: self.session.clear_period() or True):
            self.refresh()
