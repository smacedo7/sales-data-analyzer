"""Analyses page: one translated table per analysis of the active selection."""

from datetime import date

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from sales_data_analyzer.application import Selection

from .. import reports
from ..messages import describe_failure
from ..main_window import MainWindow, Page, scrolling, to_date, to_qdate
from ..texts import t
from ..widgets import button, clear_layout, label, page_header, table_widget

COMPARE = "compare"
"""Selector key of the two-period comparison."""


def date_edit(day: date) -> QDateEdit:
    """Return a dd/mm/yyyy date field with a calendar popup."""
    edit = QDateEdit()
    edit.setCalendarPopup(True)
    edit.setDisplayFormat("dd/MM/yyyy")
    edit.setDate(to_qdate(day))
    return edit


class AnalysesPage(Page):
    """Shows the chosen analysis as soon as it is picked."""

    key = "analyses"

    def __init__(self, window: MainWindow) -> None:
        """Build the selector, the options, the comparison dates and the result area."""
        super().__init__(window)
        self.view_box = QComboBox()
        for view in (*reports.ANALYSIS_VIEWS, COMPARE):
            self.view_box.addItem(t(f"analyses.view.{view}"), view)
        self.view_box.currentIndexChanged.connect(lambda _: self.show_analysis())
        self.zero_box = QCheckBox(t("analyses.zero_days"))
        self.zero_box.toggled.connect(lambda _: self.show_analysis())
        self.missing_label = label("", "note")

        today = date.today()
        self.first_start, self.first_end = date_edit(today), date_edit(today)
        self.second_start, self.second_end = date_edit(today), date_edit(today)
        self.compare_button = button(t("analyses.compare"), self.compare_periods, primary=True)
        self.periods = QFrame()
        row = QHBoxLayout(self.periods)
        row.setContentsMargins(0, 0, 0, 0)
        for text, edit in (
            (t("analyses.first"), self.first_start),
            (t("header.to"), self.first_end),
            (t("analyses.second"), self.second_start),
            (t("header.to"), self.second_end),
        ):
            row.addWidget(label(text, wrap=False))
            row.addWidget(edit)
        row.addWidget(self.compare_button)
        row.addStretch()
        self._company_shown = None

        options = QHBoxLayout()
        options.addWidget(self.view_box)
        options.addWidget(self.zero_box)
        options.addStretch()
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)
        layout.addLayout(page_header(t("analyses.title"), t("analyses.subtitle")))
        layout.addLayout(options)
        layout.addWidget(self.missing_label)
        layout.addWidget(self.periods)
        self.result = QVBoxLayout()
        layout.addLayout(self.result)
        layout.addStretch()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scrolling(content))
        self.shown: reports.Table | None = None

    def refresh(self) -> None:
        """Update the missing-day option and redraw the chosen analysis.

        When another company is selected, both comparison periods start as the
        period shown in the header.
        """
        if self.session.current is not self._company_shown:
            self._company_shown = self.session.current
            bar = self.window_
            for start, end in ((self.first_start, self.first_end),
                               (self.second_start, self.second_end)):  # fmt: skip
                start.setDate(bar.start_edit.date())
                end.setDate(bar.end_edit.date())
        missing = reports.missing_days(self.session) if self.session.current else 0
        self.zero_box.setEnabled(bool(missing))
        if not missing and self.zero_box.isChecked():
            self.zero_box.blockSignals(True)
            self.zero_box.setChecked(False)
            self.zero_box.blockSignals(False)
        self.missing_label.setText(t("analyses.missing", count=missing) if missing else "")
        self.missing_label.setVisible(bool(missing))
        self.show_analysis()

    def choose(self, view: str) -> None:
        """Select an analysis in the selector (shows it at once)."""
        self.view_box.setCurrentIndex(self.view_box.findData(view))

    def _show(self, widget: QWidget) -> None:
        """Replace the result area with widget."""
        clear_layout(self.result)
        self.result.addWidget(widget)

    def show_analysis(self) -> None:
        """Show the chosen analysis, the comparison form, or the empty state."""
        view = self.view_box.currentData()
        self.periods.setVisible(view == COMPARE)
        self.zero_box.setVisible(view in ("day", "week", "month", "weekday"))
        self.shown = None
        clear_layout(self.result)
        if self.session.current is None:
            return
        if view == COMPARE:
            return
        empty = self.window_.empty_state()
        if empty is not None:
            self._show(empty)
            return
        try:  # also runs during refresh, so failures are shown inline, never re-refreshed
            table = reports.analysis_table(
                self.session, view, zero_missing_days=self.zero_box.isChecked()
            )
        except Exception as error:
            self._show(label(describe_failure(error), "banner"))
            return
        self.shown = table
        self._show(table_widget(table))

    def set_periods(self, first: tuple[date, date], second: tuple[date, date]) -> None:
        """Fill the four comparison dates (used by tests)."""
        for edit, day in zip(
            (self.first_start, self.first_end, self.second_start, self.second_end),
            (*first, *second),
            strict=True,
        ):
            edit.setDate(to_qdate(day))

    def compare_periods(self) -> None:
        """Compare the two periods; the active selection is unchanged."""

        def compare() -> reports.Table:
            first = Selection(to_date(self.first_start.date()), to_date(self.first_end.date()))
            second = Selection(to_date(self.second_start.date()), to_date(self.second_end.date()))
            return reports.period_comparison_table(self.session, first, second)

        table = self.window_.attempt(compare)
        if table is not None:
            self.shown = table
            self._show(table_widget(table))
