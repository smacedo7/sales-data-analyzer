"""Charts tab: the level 3 Matplotlib charts drawn in the window and saved as PNG.

Charts are computed only on request (the comparison behind the estimate line is
the slowest service), from the same figures that the PNG writer saves.
"""

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from .. import reports
from ..main_window import MainWindow, Page
from ..texts import t

PROMPT = ""
CHART_PIXELS_PER_INCH = 90
"""On-screen height per inch of figure, so charts scroll instead of shrinking."""


class ChartsPage(Page):
    """Daily (with estimate), monthly and top-product charts of the active selection."""

    key = "charts"

    def __init__(self, window: MainWindow) -> None:
        """Build the buttons, the note and the scrolling chart area."""
        super().__init__(window)
        self.refresh_button = QPushButton(t("charts.title"))
        self.refresh_button.clicked.connect(self.draw)
        self.save_button = QPushButton(t("charts.save"))
        self.save_button.clicked.connect(self.save)
        self.note_label = QLabel(PROMPT)
        self.note_label.setWordWrap(True)
        self.canvases: list[QWidget] = []
        self._charts = QWidget()
        self._charts_layout = QVBoxLayout(self._charts)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._charts)
        buttons = QHBoxLayout()
        buttons.addWidget(self.refresh_button)
        buttons.addWidget(self.save_button)
        buttons.addStretch()
        layout = QVBoxLayout(self)
        layout.addLayout(buttons)
        layout.addWidget(self.note_label)
        layout.addWidget(scroll, 1)

    def refresh(self) -> None:
        """Remove charts of an older selection or company."""
        self._clear()
        self.note_label.setText(PROMPT)

    def _clear(self) -> None:
        """Delete the embedded canvases."""
        for canvas in self.canvases:
            self._charts_layout.removeWidget(canvas)
            canvas.deleteLater()
        self.canvases = []

    @staticmethod
    def _note(data) -> str:  # data: ChartData
        """Return the line explaining a missing estimate, or a neutral one."""
        if data.forecast_refusal is not None:
            reason = reports.explain_forecast_refusal(data.forecast_refusal)
            return t("charts.forecast_off", reason=reason)
        return t("charts.forecast_on", title=data.forecast_title)

    def draw(self) -> None:
        """Draw the charts of the current selection inside the window."""
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

        from sales_data_analyzer.charts.images import ChartInputs, build_figure, has_data

        def build():  # -> (ChartData, figures)
            data = self.session.chart_data()
            inputs = ChartInputs.from_data(data)
            kinds = [kind for kind in ("daily", "monthly", "products") if has_data(kind, inputs)]
            return data, [build_figure(kind, inputs) for kind in kinds]

        built = self.window_.attempt(build)
        if built is None:
            return
        data, figures = built
        self._clear()
        for figure in figures:
            figure.set_layout_engine("constrained")  # keep titles inside the widget
            canvas = FigureCanvasQTAgg(figure)
            canvas.setFixedHeight(int(figure.get_figheight() * CHART_PIXELS_PER_INCH))
            self._charts_layout.addWidget(canvas)
            self.canvases.append(canvas)
        self._charts_layout.activate()  # grow the scrolled area before the next paint
        self.note_label.setText(self._note(data))

    def save(self) -> None:
        """Save the charts as PNG files in a chosen folder, asking before replacing."""
        from sales_data_analyzer.charts.images import ChartInputs, save_charts

        folder = self.window_.prompter.choose_folder()
        if folder is None:
            return

        def write():  # -> (ChartData, paths)
            data = self.session.chart_data()
            written = save_charts(
                ChartInputs.from_data(data),
                folder,
                replace=lambda path: self.window_.prompter.confirm(
                    t("charts.replace", name=path.name)
                ),
            )
            return data, written

        saved = self.window_.attempt(write)
        if saved is None:
            return
        data, written = saved
        lines = (
            [t("charts.saved", files="\n".join(str(p) for p in written))]
            if written
            else [t("charts.nothing_saved")]
        )
        if data.forecast_refusal is not None:
            lines.insert(0, self._note(data))
        self.window_.prompter.inform("\n".join(lines))
