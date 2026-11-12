"""Main window: a side navigation, a header with company and period, and one page per task.

The window holds one SalesSession for the whole run and is a thin view of it:
after every successful action it redraws from the session, and every action
runs through `attempt`, the single place where failures become messages.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import date, timedelta

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from sales_data_analyzer.application import SalesSession

from . import reports
from .messages import describe_failure
from .prompter import Prompter, QtPrompter
from .style import STYLE_SHEET
from .texts import t
from .widgets import button, label

NAV_ICONS = {
    "home": "🏠",
    "overview": "📊",
    "catalog": "📦",
    "sales": "🧾",
    "analyses": "🔎",
    "forecast": "📈",
    "charts": "🎨",
    "report": "📄",
}
"""Emoji shown before each navigation entry (rendered by the system font)."""


class Page(QWidget):
    """A navigation destination that redraws itself from the window's session."""

    key = "page"
    needs_company = True

    def __init__(self, window: "MainWindow") -> None:
        """Keep the owning window (session, prompter and attempt)."""
        super().__init__()
        self.setObjectName("page")
        self.window_ = window

    @property
    def session(self) -> SalesSession:
        """Return the window's session."""
        return self.window_.session

    def refresh(self) -> None:
        """Redraw from the session; called after every successful change."""


def scrolling(content: QWidget) -> QScrollArea:
    """Return content inside a frameless vertical scroll area."""
    area = QScrollArea()
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setWidgetResizable(True)
    content.setObjectName("scrollBody")
    area.setWidget(content)
    return area


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
        self.setWindowTitle(t("app.title"))
        self.setStyleSheet(STYLE_SHEET)
        self.resize(1240, 800)
        self.setMinimumSize(900, 600)

        if pages is None:
            from .pages import DEFAULT_PAGES

            pages = DEFAULT_PAGES
        self.pages = tuple(page(self) for page in pages)

        self.sidebar = QListWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(190)
        self.sidebar.currentRowChanged.connect(self._page_chosen)
        self.stack = QStackedWidget()
        for page in self.pages:
            item = QListWidgetItem(f"{NAV_ICONS.get(page.key, '•')}  {t(f'nav.{page.key}')}")
            self.sidebar.addItem(item)
            self.stack.addWidget(page)

        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(0)
        side_layout.addWidget(label(t("app.title"), "brand"))
        side_layout.addWidget(label(t("app.subtitle"), "brandSubtitle"))
        side_layout.addWidget(self.sidebar, 1)
        side.setFixedWidth(190)
        side.setStyleSheet("background: #1f3a4d;")

        self.header = self._build_header()
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        body_layout.addWidget(self.header)
        body_layout.addWidget(self.stack, 1)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(side)
        layout.addWidget(body, 1)
        self.setCentralWidget(central)

        repository = session.repository
        location = (
            t("app.database", path=repository.location) if repository is not None
            else t("app.memory")
        )  # fmt: skip
        self.database_label = QLabel(location)
        self.statusBar().addPermanentWidget(self.database_label)
        self.refresh()
        self.go("home" if session.current is None else "overview")

    def _build_header(self) -> QFrame:
        """Return the header: company name, its buttons and the period controls."""
        header = QFrame()
        header.setObjectName("header")
        self.company_label = label("", "companyName", wrap=False)
        self.change_company_button = button(t("header.change_company"), lambda: self.go("home"))
        self.edit_company_button = button(t("header.edit_company"), self.edit_company)
        self.start_edit = QDateEdit()
        self.end_edit = QDateEdit()
        for edit in (self.start_edit, self.end_edit):
            edit.setCalendarPopup(True)
            edit.setDisplayFormat("dd/MM/yyyy")
            edit.setDate(to_qdate(date.today()))
        self.apply_period_button = button(t("header.apply"), self.apply_period, primary=True)
        self.all_data_button = button(t("header.preset.all"), self.clear_period, name="preset")
        self.last_30_button = button(
            t("header.preset.last_30"), lambda: self.preset("last_30"), name="preset"
        )
        self.month_button = button(
            t("header.preset.this_month"), lambda: self.preset("month"), name="preset"
        )
        self.selection_label = label("", "selectionLabel", wrap=False)

        names = QVBoxLayout()
        names.setSpacing(0)
        names.addWidget(self.company_label)
        names.addWidget(self.selection_label)
        top = QHBoxLayout()
        top.addLayout(names)
        top.addStretch()
        top.addWidget(self.change_company_button)
        top.addWidget(self.edit_company_button)
        period = QHBoxLayout()
        period.addWidget(QLabel(t("header.period")))
        for widget in (
            self.all_data_button,
            self.last_30_button,
            self.month_button,
            QLabel(t("header.from")),
            self.start_edit,
            QLabel(t("header.to")),
            self.end_edit,
            self.apply_period_button,
        ):
            widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            period.addWidget(widget)
        period.addStretch()
        self.period_row = QWidget()
        self.period_row.setLayout(period)
        period.setContentsMargins(0, 0, 0, 0)
        layout = QVBoxLayout(header)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.addLayout(top)
        layout.addWidget(self.period_row)
        return header

    # -- navigation -----------------------------------------------------------------

    def page(self, key: str) -> Page:
        """Return the page with the given navigation key."""
        return next(page for page in self.pages if page.key == key)

    def go(self, key: str) -> None:
        """Show the page with the given key (pages needing a company stay locked)."""
        index = next(i for i, page in enumerate(self.pages) if page.key == key)
        self.sidebar.setCurrentRow(index)

    def _page_chosen(self, index: int) -> None:
        """Show the chosen page, or explain why it is locked."""
        if index < 0:
            return
        page = self.pages[index]
        if page.needs_company and self.session.current is None:
            self.statusBar().showMessage(t("nav.needs_company"), 5000)
            self.sidebar.blockSignals(True)
            self.sidebar.setCurrentRow(self.stack.currentIndex())
            self.sidebar.blockSignals(False)
            return
        self.stack.setCurrentIndex(index)

    @property
    def current_page(self) -> Page:
        """Return the page on screen."""
        return self.pages[self.stack.currentIndex()]

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

    def perform(self, action: Callable[[], object]) -> bool:
        """Run action through `attempt` and return True when it finished without error."""
        done = False

        def run() -> None:
            nonlocal done
            action()
            done = True

        self.attempt(run)
        return done

    def _safe_refresh(self) -> None:
        """Redraw, reporting (once) a failure of the redraw itself."""
        try:
            self.refresh()
        except Exception as error:
            self.prompter.warn(describe_failure(error))

    def notify(self, text: str) -> None:
        """Show a short confirmation in the status bar."""
        self.statusBar().showMessage(text, 8000)

    # -- drawing --------------------------------------------------------------------

    def refresh(self) -> None:
        """Redraw the header, the navigation locks and every page from the session."""
        current = self.session.current
        has_company = current is not None
        self.company_label.setText(
            t("header.company", name=current.company.name, sector=current.company.sector)
            if has_company else t("header.no_company")
        )  # fmt: skip
        self.period_row.setVisible(has_company)
        self.change_company_button.setVisible(has_company)
        self.edit_company_button.setVisible(has_company)
        for widget in (
            self.edit_company_button,
            self.start_edit,
            self.end_edit,
            self.apply_period_button,
            self.all_data_button,
            self.last_30_button,
            self.month_button,
        ):
            widget.setEnabled(has_company)
        for index, page in enumerate(self.pages):
            item = self.sidebar.item(index)
            locked = page.needs_company and not has_company
            item.setFlags(
                Qt.ItemFlag.NoItemFlags if locked
                else Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            )  # fmt: skip
            item.setToolTip(t("nav.needs_company") if locked else "")
        selection = self.session.selection
        if selection.start is not None and selection.end is not None:
            self.start_edit.setDate(to_qdate(selection.start))
            self.end_edit.setDate(to_qdate(selection.end))
        elif (span := self.sales_span()) is not None:
            self.start_edit.setDate(to_qdate(span[0]))
            self.end_edit.setDate(to_qdate(span[1]))
        self.selection_label.setText(reports.selection_text(self.session))
        if not has_company and self.current_page.needs_company:
            self.go("home")
        for page in self.pages:
            page.refresh()

    def sales_span(self) -> tuple[date, date] | None:
        """Return the first and last sale day of the company (UTC days for offset data)."""
        workspace = self.session.current
        if workspace is None or not workspace.sales.sales:
            return None
        days = [sale.date_time.date() for sale in workspace.sales.sales]
        return min(days), max(days)

    def empty_state(self) -> QWidget | None:
        """Return a helpful empty state when the company or the period has no sales."""
        from .widgets import EmptyState

        workspace = self.session.current
        if workspace is None or reports.has_sales(self.session):
            return None
        if not workspace.sales.sales:
            sales = self.page("sales") if any(p.key == "sales" for p in self.pages) else None
            actions = []
            if sales is not None:
                actions = [
                    (t("empty.go_import"), lambda: (self.go("sales"), sales.import_csv())),
                    (t("empty.go_sale"), lambda: (self.go("sales"), sales.record_sale())),
                ]
            return EmptyState(t("empty.no_sales.title"), t("empty.no_sales.body"), actions)
        return EmptyState(
            t("empty.no_selection.title"),
            t("empty.no_selection.body"),
            [(t("empty.show_all"), self.clear_period)],
        )

    # -- companies ------------------------------------------------------------------

    def select_company(self, number: int) -> None:
        """Select the company at a 1-based position and show its overview."""
        if self.attempt(lambda: self.session.select_company(number)) is not None:
            self.refresh()
            self.go("overview")

    def new_company(self) -> None:
        """Ask for a company, create it, select it and show its overview."""
        values = self.prompter.company_form()
        if values is None:
            return
        workspace = self.attempt(lambda: self.session.create_company(values.name, values.sector))
        if workspace is not None:
            self.refresh()
            self.go("overview")

    def edit_company(self) -> None:
        """Ask for the selected company's new name and sector and store both."""
        current = self.session.current
        if current is None:
            self.prompter.warn(t("error.needs_company"))
            return
        values = self.prompter.company_form(current.company.name, current.company.sector)
        if values is None:
            return
        if self.perform(lambda: self.session.update_company(values.name, values.sector)):
            self.refresh()

    # -- period ---------------------------------------------------------------------

    def apply_period(self) -> None:
        """Select the days from the From date to the To date, both included."""
        start, end = to_date(self.start_edit.date()), to_date(self.end_edit.date())
        if self.perform(lambda: self.session.set_period(start, end)):
            self.refresh()

    def clear_period(self) -> None:
        """Select all data of the current company again."""
        if self.perform(self.session.clear_period):
            self.refresh()

    def preset(self, name: str) -> None:
        """Select the last 30 days or the last calendar month that has sales."""
        span = self.sales_span()
        if span is None:
            self.prompter.warn(t("error.no_sales"))
            return
        last = span[1]
        if name == "last_30":
            start = last - timedelta(days=29)
        else:
            start = last.replace(day=1)
            next_month = (start + timedelta(days=32)).replace(day=1)
            last = next_month - timedelta(days=1)
        if self.perform(lambda: self.session.set_period(start, last)):
            self.refresh()
