"""Analyses tab: financial, product, temporal, weekday, category and period comparison."""

from datetime import date

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from sales_data_analyzer.application import Selection

from .. import reports
from ..main_window import MainWindow, Page, to_date, to_qdate

TIMEZONE_NOTE = "These sales have time zone offsets: dates are interpreted in UTC."
PROMPT = "Choose an analysis and press Show."


def report_view() -> QPlainTextEdit:
    """Return a read-only monospace panel for terminal-formatted results."""
    view = QPlainTextEdit()
    view.setReadOnly(True)
    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    font.setFamilies(["Menlo", "Consolas", "DejaVu Sans Mono", "Courier New", font.family()])
    font.setStyleHint(QFont.StyleHint.TypeWriter)
    font.setFixedPitch(True)
    view.setFont(font)
    view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
    return view


def date_edit(day: date) -> QDateEdit:
    """Return an ISO-formatted date field with a calendar popup."""
    edit = QDateEdit()
    edit.setCalendarPopup(True)
    edit.setDisplayFormat("yyyy-MM-dd")
    edit.setDate(to_qdate(day))
    return edit


class AnalysesPage(Page):
    """Shows one analysis of the active selection, worded like the terminal."""

    title = "Analyses"

    def __init__(self, window: MainWindow) -> None:
        """Build the view selector, the options and the result panel."""
        super().__init__(window)
        self._company_shown = None
        self.view_box = QComboBox()
        for key, label in reports.ANALYSIS_VIEWS:
            self.view_box.addItem(label, key)
        self.zero_box = QCheckBox("Treat days without sales as zero")
        self.missing_label = QLabel()
        self.show_button = QPushButton("Show")
        self.show_button.clicked.connect(self.show_analysis)

        today = date.today()
        self.first_start, self.first_end = date_edit(today), date_edit(today)
        self.second_start, self.second_end = date_edit(today), date_edit(today)
        self.compare_button = QPushButton("Compare periods")
        self.compare_button.clicked.connect(self.compare_periods)
        periods = QGroupBox("Compare two periods (both days included)")
        row = QHBoxLayout(periods)
        for label, edit in (
            ("First", self.first_start),
            ("to", self.first_end),
            ("Second", self.second_start),
            ("to", self.second_end),
        ):
            row.addWidget(QLabel(label))
            row.addWidget(edit)
        row.addWidget(self.compare_button)
        row.addStretch()

        self.output = report_view()
        options = QHBoxLayout()
        options.addWidget(self.view_box)
        options.addWidget(self.show_button)
        options.addWidget(self.zero_box)
        options.addWidget(self.missing_label, 1)
        layout = QVBoxLayout(self)
        layout.addLayout(options)
        layout.addWidget(periods)
        layout.addWidget(self.output, 1)

    def refresh(self) -> None:
        """Clear the previous result and update the missing-day notice.

        When another company is selected, both comparison periods start as the
        period shown in the top bar.
        """
        self.output.setPlainText(PROMPT)
        if self.session.current is not self._company_shown:
            self._company_shown = self.session.current
            bar = self.window_
            for start, end in ((self.first_start, self.first_end),
                               (self.second_start, self.second_end)):  # fmt: skip
                start.setDate(bar.start_edit.date())
                end.setDate(bar.end_edit.date())
        missing = reports.missing_days(self.session) if self.session.current is not None else 0
        self.zero_box.setEnabled(bool(missing))
        if not missing:
            self.zero_box.setChecked(False)
        notes = [reports.missing_days_notice(missing)] if missing else []
        if self.session.current is not None and self.session.selected_sales().sales:
            if self.session.data_is_aware():
                notes.append(TIMEZONE_NOTE)
        self.missing_label.setText(" ".join(notes))

    def choose(self, view: reports.AnalysisView) -> None:
        """Select an analysis in the selector (used by tests and shortcuts)."""
        self.view_box.setCurrentIndex(self.view_box.findData(view))

    def show_analysis(self) -> None:
        """Show the chosen analysis of the active selection."""
        view = self.view_box.currentData()
        zero = self.zero_box.isChecked()
        lines = self.window_.attempt(
            lambda: reports.analysis_lines(self.session, view, zero_missing_days=zero)
        )
        if lines is not None:
            self.output.setPlainText("\n".join(lines))

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

        def compare() -> list[str]:
            first = Selection(to_date(self.first_start.date()), to_date(self.first_end.date()))
            second = Selection(to_date(self.second_start.date()), to_date(self.second_end.date()))
            return reports.period_comparison_lines(self.session, first, second)

        lines = self.window_.attempt(compare)
        if lines is not None:
            self.output.setPlainText("\n".join(lines))
