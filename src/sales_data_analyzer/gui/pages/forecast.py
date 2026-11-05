"""Forecast tab: the level 2 linear forecast and the level 3 method comparison.

Refusals follow the terminal: missing days are treated as zero only after the
user confirms that the records are complete (default No).
"""

from datetime import timedelta

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from sales_data_analyzer.application import InsufficientHistoryError
from sales_data_analyzer.cli.formatting import explain_forecast_error, is_missing_days_error
from sales_data_analyzer.cli.parsing import (
    DEFAULT_HORIZON,
    DEFAULT_TEST_DAYS,
    MAX_HORIZON,
    MIN_TEST_DAYS,
    parse_optional_offset,
)

from .. import reports
from ..main_window import MainWindow, Page
from .analyses import report_view

ZERO_QUESTION = "Treat missing days as zero revenue? Only answer yes if your records are complete."
CANCELLED = "Forecast cancelled."
OFFSET_NOTE = "These sales have time zone offsets; days are grouped by a UTC offset."
PROMPT = "Choose the options and run a forecast."


class _Refused(Exception):
    """A forecast refusal already worded for the user (shown in the result panel)."""


class ForecastPage(Page):
    """Runs forecasts of the active selection and shows them like the terminal."""

    title = "Forecast"

    def __init__(self, window: MainWindow) -> None:
        """Build the options, the two run buttons, the method selector and the panel."""
        super().__init__(window)
        self.horizon_box = QSpinBox()
        self.horizon_box.setRange(1, MAX_HORIZON)
        self.horizon_box.setValue(DEFAULT_HORIZON)
        self.test_days_box = QSpinBox()
        self.test_days_box.setRange(MIN_TEST_DAYS, MAX_HORIZON)
        self.test_days_box.setValue(DEFAULT_TEST_DAYS)
        self.offset_edit = QLineEdit()
        self.offset_edit.setPlaceholderText("+00:00")
        self.offset_label = QLabel("UTC offset (+HH:MM or -HH:MM)")
        self.offset_note = QLabel(OFFSET_NOTE)
        self.linear_button = QPushButton("Linear forecast")
        self.linear_button.clicked.connect(self.run_linear)
        self.compare_button = QPushButton("Compare methods")
        self.compare_button.clicked.connect(lambda: self.run_comparison())
        self.method_box = QComboBox()
        self.use_method_button = QPushButton("Use method")
        self.use_method_button.clicked.connect(self.use_method)
        self._comparison: reports.ComparisonReport | None = None
        self._zero = False
        self._aware = False

        form = QFormLayout()
        form.addRow("Days to forecast", self.horizon_box)
        form.addRow("Test days (linear forecast)", self.test_days_box)
        form.addRow(self.offset_label, self.offset_edit)
        form.addRow(self.offset_note)
        buttons = QHBoxLayout()
        for widget in (self.linear_button, self.compare_button, QLabel("Estimates from")):
            buttons.addWidget(widget)
        buttons.addWidget(self.method_box, 1)
        buttons.addWidget(self.use_method_button)
        self.output = report_view()
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(buttons)
        layout.addWidget(self.output, 1)

    def refresh(self) -> None:
        """Forget the previous result; show the offset option only for offset data."""
        aware = (
            self.session.current is not None
            and bool(self.session.selected_sales().sales)
            and self.session.data_is_aware()
        )
        self._aware = aware
        for widget in (self.offset_label, self.offset_edit, self.offset_note):
            widget.setVisible(aware)
        self._set_comparison(None)
        self.output.setPlainText(PROMPT)

    def _set_comparison(self, report: reports.ComparisonReport | None) -> None:
        """Keep the latest comparison and list its methods for the estimates."""
        self._comparison = report
        self.method_box.clear()
        if report is not None:
            for score in report.result.scores:
                self.method_box.addItem(score.title, score.method_key)
            self.method_box.setCurrentIndex(self.method_box.findData(report.result.chosen_key))
        self.method_box.setEnabled(report is not None)
        self.use_method_button.setEnabled(report is not None)

    def _offset(self) -> timedelta | None:
        """Return the typed UTC offset for offset data, None for naive data."""
        if not self._aware:
            return None
        return parse_optional_offset(self.offset_edit.text())

    def _with_missing_days(self, run, explain):  # -> result
        """Run with the reject policy; on a missing-day refusal ask, then run with zero."""
        try:
            self._zero = False
            return run(False)
        except ValueError as error:
            if not is_missing_days_error(error):
                raise
            if not self.window_.prompter.confirm(f"{explain(error)}\n\n{ZERO_QUESTION}"):
                raise _Refused(CANCELLED) from None
        self._zero = True
        return run(True)

    def _show(self, action) -> None:
        """Run action and show its lines; worded refusals go to the result panel."""

        def guarded():  # -> list[str]
            try:
                return action()
            except _Refused as refusal:
                return [str(refusal)]

        lines = self.window_.attempt(guarded)
        if lines is not None:
            self.output.setPlainText("\n".join(lines))

    def run_linear(self) -> None:
        """Run the level 2 linear forecast with the chosen horizon and test days."""
        horizon, test_days = self.horizon_box.value(), self.test_days_box.value()

        def action() -> list[str]:
            offset = self._offset()
            try:
                return self._with_missing_days(
                    lambda zero: reports.forecast_lines(
                        self.session,
                        horizon=horizon,
                        test_days=test_days,
                        zero_missing_days=zero,
                        utc_offset=offset,
                    ),
                    explain_forecast_error,
                )
            except _Refused:
                raise
            except ValueError as error:  # every forecaster refusal, worded like the terminal
                raise _Refused(explain_forecast_error(error)) from None

        self._show(action)

    def run_comparison(self, method: str | None = None) -> None:
        """Compare the forecast methods and show the estimates of the chosen one."""
        horizon = self.horizon_box.value()

        def action() -> list[str]:
            offset = self._offset()
            try:
                report = self._with_missing_days(
                    lambda zero: reports.comparison_report(
                        self.session,
                        horizon=horizon,
                        zero_missing_days=zero,
                        utc_offset=offset,
                        method=method,
                    ),
                    explain_forecast_error,
                )
            except InsufficientHistoryError as error:
                raise _Refused(f"Not done: {error}.") from None
            self._set_comparison(report)
            return list(report.lines)

        self._set_comparison(None)
        self._show(action)

    def use_method(self) -> None:
        """Show the estimates of the method chosen in the selector."""
        report = self._comparison
        key = self.method_box.currentData()
        if report is None or key is None:
            self.window_.prompter.warn("Not done: compare the methods first.")
            return
        horizon, zero = self.horizon_box.value(), self._zero

        def action() -> list[str]:
            new = reports.comparison_report(
                self.session,
                horizon=horizon,
                zero_missing_days=zero,
                utc_offset=self._offset(),
                method=key,
            )
            self._set_comparison(new)
            return list(new.lines)

        self._show(action)
