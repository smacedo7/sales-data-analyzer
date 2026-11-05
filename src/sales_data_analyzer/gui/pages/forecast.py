"""Forecasts page: the level 2 linear forecast and the level 3 method comparison.

Refusals are explained in place; missing days are treated as zero only after the
user confirms that the records are complete (default No).
"""

from datetime import timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from sales_data_analyzer.cli.formatting import is_missing_days_error
from sales_data_analyzer.cli.parsing import (
    DEFAULT_HORIZON,
    DEFAULT_TEST_DAYS,
    MAX_HORIZON,
    MIN_TEST_DAYS,
    InputError,
    parse_optional_offset,
)

from .. import reports
from ..main_window import MainWindow, Page, scrolling
from ..texts import method_title, t
from ..widgets import button, clear_layout, label, page_header, table_widget


class _Refused(Exception):
    """A forecast refusal already worded for the user (shown in the result area)."""


class ForecastPage(Page):
    """Runs forecasts of the active selection and shows translated tables and notes."""

    key = "forecast"

    def __init__(self, window: MainWindow) -> None:
        """Build the options, the run buttons, the method selector and the result area."""
        super().__init__(window)
        self.horizon_box = QSpinBox()
        self.horizon_box.setRange(1, MAX_HORIZON)
        self.horizon_box.setValue(DEFAULT_HORIZON)
        self.test_days_box = QSpinBox()
        self.test_days_box.setRange(MIN_TEST_DAYS, MAX_HORIZON)
        self.test_days_box.setValue(DEFAULT_TEST_DAYS)
        self.offset_edit = QLineEdit()
        self.offset_edit.setPlaceholderText("+00:00")
        self.offset_label = label(t("forecast.offset"), wrap=False)
        self.offset_note = label(t("forecast.offset_note"), "note")
        self.compare_button = button(t("forecast.compare"), lambda: self.run_comparison(),
                                     primary=True)  # fmt: skip
        self.linear_button = button(t("forecast.linear"), self.run_linear)
        self.method_box = QComboBox()
        self.method_box.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.use_method_button = button(t("forecast.use_method"), self.use_method)
        self._comparison: reports.ComparisonReport | None = None
        self._zero = False
        self._aware = False
        self.shown: reports.Report | None = None
        self.message: str | None = None

        for box in (self.horizon_box, self.test_days_box, self.offset_edit):
            box.setMaximumWidth(140)
        form = QFormLayout()
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)  # macOS would right-align the form
        form.addRow(t("forecast.horizon"), self.horizon_box)
        form.addRow(t("forecast.test_days"), self.test_days_box)
        form.addRow(self.offset_label, self.offset_edit)
        form.addRow(self.offset_note)
        actions = QHBoxLayout()
        actions.addWidget(self.compare_button)
        actions.addWidget(self.linear_button)
        actions.addSpacing(16)
        actions.addWidget(label(t("forecast.estimates_from"), wrap=False))
        actions.addWidget(self.method_box)
        actions.addWidget(self.use_method_button)
        actions.addStretch()
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)
        layout.addLayout(page_header(t("forecast.title"), t("forecast.subtitle")))
        layout.addLayout(form)
        layout.addLayout(actions)
        self.result = QVBoxLayout()
        self.result.setSpacing(10)
        layout.addLayout(self.result)
        layout.addStretch()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scrolling(content))

    # -- drawing --------------------------------------------------------------------

    def refresh(self) -> None:
        """Forget the previous result; show the offset option only for offset data."""
        self._aware = reports.has_sales(self.session) and self.session.data_is_aware()
        for widget in (self.offset_label, self.offset_edit, self.offset_note):
            widget.setVisible(self._aware)
        self._set_comparison(None)
        empty = self.window_.empty_state() if self.session.current is not None else None
        if empty is not None:
            self._replace([empty])
        else:
            self.show_message(t("forecast.prompt"))
        for widget in (self.compare_button, self.linear_button):
            widget.setEnabled(empty is None)

    def _replace(self, widgets: list[QWidget]) -> None:
        """Replace the result area with widgets."""
        clear_layout(self.result)
        for widget in widgets:
            self.result.addWidget(widget)

    def show_message(self, text: str) -> None:
        """Show one sentence in the result area (a prompt or a refusal)."""
        self.shown, self.message = None, text
        self._replace([label(text, "banner")])

    def show_report(self, report: reports.Report) -> None:
        """Show the report's tables followed by its notes."""
        self.shown, self.message = report, None
        widgets = [table_widget(table) for table in report.tables]
        widgets += [label(note, "note") for note in report.notes]
        self._replace(widgets)

    def _set_comparison(self, report: reports.ComparisonReport | None) -> None:
        """Keep the latest comparison and list its methods for the estimates."""
        self._comparison = report
        self.method_box.clear()
        if report is not None:
            for score in report.result.scores:
                self.method_box.addItem(
                    method_title(score.method_key, score.title), score.method_key
                )
            self.method_box.setCurrentIndex(self.method_box.findData(report.result.chosen_key))
        self.method_box.setEnabled(report is not None)
        self.use_method_button.setEnabled(report is not None)

    # -- running --------------------------------------------------------------------

    def _offset(self) -> timedelta | None:
        """Return the typed UTC offset for offset data, None for naive data."""
        if not self._aware:
            return None
        try:
            return parse_optional_offset(self.offset_edit.text())
        except InputError:
            problem = t("form.problem.offset")
            raise _Refused(t("form.error", field=t("forecast.offset"), problem=problem)) from None

    def _with_missing_days(self, run):  # -> result
        """Run with the reject policy; on a missing-day refusal ask, then run with zero."""
        try:
            self._zero = False
            return run(False)
        except ValueError as error:
            if not is_missing_days_error(error):
                raise
            reason = reports.explain_forecast_refusal(error)
            if not self.window_.prompter.confirm(t("forecast.zero_question", reason=reason)):
                raise _Refused(t("forecast.cancelled")) from None
        self._zero = True
        return run(True)

    def _run(self, action) -> None:
        """Run action (returning a Report); worded refusals go to the result area."""

        def guarded():  # -> Report | str
            try:
                return action()
            except _Refused as refusal:
                return str(refusal)
            except ValueError as error:  # service refusals (short history, …)
                return reports.explain_forecast_refusal(error)

        outcome = self.window_.attempt(guarded)
        if isinstance(outcome, str):
            self.show_message(outcome)
        elif outcome is not None:
            self.show_report(outcome)

    def run_linear(self) -> None:
        """Run the level 2 linear forecast with the chosen horizon and test days."""
        horizon, test_days = self.horizon_box.value(), self.test_days_box.value()

        def action() -> reports.Report:
            offset = self._offset()
            self._set_comparison(None)
            return self._with_missing_days(
                lambda zero: reports.linear_forecast_report(
                    self.session, horizon=horizon, test_days=test_days,
                    zero_missing_days=zero, utc_offset=offset,
                )
            )  # fmt: skip

        self._run(action)

    def run_comparison(self, method: str | None = None) -> None:
        """Compare the forecast methods and show the estimates of the chosen one."""
        horizon = self.horizon_box.value()

        def action() -> reports.Report:
            offset = self._offset()
            comparison = self._with_missing_days(
                lambda zero: reports.comparison_report(
                    self.session, horizon=horizon, zero_missing_days=zero,
                    utc_offset=offset, method=method,
                )
            )  # fmt: skip
            self._set_comparison(comparison)
            return comparison.report

        self._set_comparison(None)
        self._run(action)

    def use_method(self) -> None:
        """Show the estimates of the method chosen in the selector."""
        key = self.method_box.currentData()
        if self._comparison is None or key is None:
            self.window_.prompter.warn(t("forecast.compare_first"))
            return
        horizon, zero = self.horizon_box.value(), self._zero

        def action() -> reports.Report:
            comparison = reports.comparison_report(
                self.session, horizon=horizon, zero_missing_days=zero,
                utc_offset=self._offset(), method=key,
            )  # fmt: skip
            self._set_comparison(comparison)
            return comparison.report

        self._run(action)
