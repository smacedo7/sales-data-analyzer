"""Charts page: one explorable Matplotlib chart at a time, plus the PNG export.

The figures come from the level 3 chart builders (translated labels only). The
page adds what a static image cannot do: a chart-type selector, the period of
the header, zoom and pan with Matplotlib's navigation toolbar, the exact value
under the mouse and a canvas that follows the window size. Values shown on
hover are the exact Decimals of ChartData, formatted for display.
"""

from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QSizePolicy, QToolBar, QVBoxLayout, QWidget

from sales_data_analyzer.application import ChartData

from .. import reports
from ..main_window import MainWindow, Page
from ..messages import describe_failure
from ..texts import day, integer, method_title, money, t, template, weekday
from ..widgets import button, clear_layout, label, page_header

SCREEN_DPI = 90
"""Figure resolution in the window (the Qt canvas multiplies it on high-density screens)."""

KINDS = ("daily", "monthly", "products", "weekday")
"""Chart types offered by the selector, in order."""

TOOLBAR_KEYS = {
    "Home": "charts.tool.home",
    "Back": "charts.tool.back",
    "Forward": "charts.tool.forward",
    "Pan": "charts.tool.pan",
    "Zoom": "charts.tool.zoom",
}
"""Matplotlib toolbar actions kept, with their translated tooltips."""


@dataclass(frozen=True)
class HoverPoint:
    """A drawn value the mouse can point at: position in data units and its text."""

    x: float
    y: float
    text: str


def chart_labels(dpi: float = 120):  # -> ChartLabels
    """Return the chart texts, axis number format and resolution for the active language."""
    from sales_data_analyzer.charts.images import ChartLabels

    return ChartLabels(
        daily=t("charts.kind.daily"),
        monthly=t("charts.kind.monthly"),
        products=template("charts.top_title"),
        weekday=t("charts.kind.weekday"),
        revenue=t("charts.axis_revenue"),
        estimate=template("charts.legend_estimate"),
        axis_number=lambda value: integer(round(value)),
        dpi=dpi,
    )


def hover_points(kind: str, data: ChartData) -> list[HoverPoint]:
    """Return the points and bars of a chart with their exact values as text.

    Line points use Matplotlib date numbers on x; vertical bars use their index;
    horizontal top-product bars use their row counted from the bottom.
    """
    from matplotlib.dates import date2num

    if kind == "daily":
        points = [
            HoverPoint(date2num(when), float(value),
                       t("charts.hover_day", day=day(when), value=money(value)))
            for when, value in data.daily
        ]  # fmt: skip
        points += [
            HoverPoint(date2num(when), value,
                       t("charts.hover_estimate", day=day(when),
                         value=money(Decimal(repr(round(value, 2))))))
            for when, value in data.forecast
        ]  # fmt: skip
        return points
    if kind == "monthly":
        return [
            HoverPoint(index, float(value), t("charts.hover_bar", label=name, value=money(value)))
            for index, (name, value) in enumerate(data.monthly)
        ]
    if kind == "weekday":
        return [
            HoverPoint(index, float(value or 0),
                       t("charts.hover_bar", label=weekday(index), value=money(value)))
            for index, value in data.weekday
        ]  # fmt: skip
    rows = list(reversed(data.top_products))  # drawn with the largest at the top
    return [
        HoverPoint(float(row.revenue), index,
                   t("charts.hover_bar", label=row.label, value=money(row.revenue)))
        for index, row in enumerate(rows)
    ]  # fmt: skip


def _navigation_class():  # -> type
    """Return the zoom/pan navigation class (Matplotlib is imported lazily)."""
    from matplotlib.backend_bases import NavigationToolbar2

    class Navigation(NavigationToolbar2):
        """Matplotlib's backend-independent zoom, pan and view history for one Qt canvas.

        Only public Matplotlib and Qt APIs are used: the zoom rectangle is drawn
        with the Qt canvas's `drawRectangle`, and there is no Matplotlib Qt toolbar.
        """

        def draw_rubberband(self, event, x0, y0, x1, y1) -> None:
            """Draw the zoom rectangle (display coordinates, origin at the bottom)."""
            height = self.canvas.get_width_height(physical=True)[1]
            rect = [int(v) for v in (x0, height - y0, x1 - x0, y0 - y1)]
            self.canvas.drawRectangle(rect)

        def remove_rubberband(self) -> None:
            """Remove the zoom rectangle."""
            self.canvas.drawRectangle(None)

    return Navigation


def chart_navigation(canvas):  # -> NavigationToolbar2
    """Return the navigation (zoom, pan, view history) of a canvas."""
    return _navigation_class()(canvas)


TOOLBAR_ACTIONS = (
    ("home", "home", False),
    ("back", "back", False),
    ("forward", "forward", False),
    ("pan", "move", True),
    ("zoom", "zoom_to_rect", True),
)
"""(navigation method, Matplotlib icon name, checkable) in toolbar order."""


def navigation_toolbar(navigation, parent: QWidget) -> QToolBar:
    """Return a Qt toolbar with translated tooltips driving navigation.

    Icons are Matplotlib's own image files, found with the public
    `matplotlib.get_data_path()`; pan and zoom show which mode is active.
    """
    import matplotlib

    images = Path(matplotlib.get_data_path()) / "images"
    toolbar = QToolBar(parent)
    toolbar.setObjectName("chartToolbar")
    toolbar.setIconSize(QSize(24, 24))
    keys = {"home": "Home", "back": "Back", "forward": "Forward", "pan": "Pan", "zoom": "Zoom"}
    modes = {"pan": "pan/zoom", "zoom": "zoom rect"}
    actions = {}

    def sync() -> None:
        for name, mode in modes.items():
            actions[name].setChecked(str(navigation.mode) == mode)

    for method, icon, checkable in TOOLBAR_ACTIONS:
        action = toolbar.addAction(QIcon(str(images / f"{icon}_large.png")), "")
        action.setToolTip(t(TOOLBAR_KEYS[keys[method]]))
        action.setCheckable(checkable)
        action.triggered.connect(lambda _=False, m=method: (getattr(navigation, m)(), sync()))
        actions[method] = action
    return toolbar


class InteractiveChart(QWidget):
    """A Matplotlib canvas with a translated zoom/pan toolbar and value tooltips."""

    def __init__(self, figure, points: list[HoverPoint], kind: str) -> None:
        """Embed figure; points are what the mouse can point at."""
        super().__init__()
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

        figure.set_layout_engine("constrained")
        legend = figure.axes[0].get_legend()
        if legend is not None:
            legend.set_loc("best")  # move away from the data in narrow windows
        self.canvas = FigureCanvasQTAgg(figure)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.canvas.setMinimumHeight(260)
        self.navigation = chart_navigation(self.canvas)
        self.toolbar = navigation_toolbar(self.navigation, self)
        self.figure = figure
        self.axes = figure.axes[0]
        self.points = points
        self.kind = kind
        self.annotation = self.axes.annotate(
            "", xy=(0, 0), xytext=(12, 12), textcoords="offset points",
            bbox={"boxstyle": "round,pad=0.4", "fc": "#fffaf2", "ec": "#d5cdc0"},
            fontsize=9, zorder=10, annotation_clip=False,
        )  # fmt: skip
        self.annotation.set_visible(False)
        self.canvas.mpl_connect("motion_notify_event", self.on_move)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas, 1)

    def nearest(self, x_pixels: float, y_pixels: float, radius: float = 24) -> HoverPoint | None:
        """Return the drawn point closest to a mouse position (pixels), within radius."""
        best, best_distance = None, radius
        rows = [p.y for p in self.points]
        bar_half_height = (
            abs(self.axes.transData.transform((0, 0.3))[1] - self.axes.transData.transform((0, 0))[1])
            if self.kind == "products" and rows else radius
        )  # fmt: skip
        (x_low, x_high), (y_low, y_high) = (
            sorted(self.axes.get_xlim()),
            sorted(self.axes.get_ylim()),
        )
        for point in self.points:
            if not (x_low <= point.x <= x_high and y_low <= point.y <= y_high):
                continue  # zoomed or panned out of view
            px, py = self.axes.transData.transform((point.x, point.y))
            if self.kind == "products":  # horizontal bars: the row decides
                distance = abs(py - y_pixels) if x_pixels <= px + radius else radius + 1
                distance = distance if abs(py - y_pixels) <= bar_half_height else radius + 1
            elif self.kind in ("monthly", "weekday"):  # vertical bars: the column decides
                distance = abs(px - x_pixels) if y_pixels <= py + radius else radius + 1
            else:
                distance = ((px - x_pixels) ** 2 + (py - y_pixels) ** 2) ** 0.5
            if distance < best_distance:
                best, best_distance = point, distance
        return best

    def on_move(self, event) -> None:
        """Show the value of the nearest point, or hide the tooltip."""
        point = self.nearest(event.x, event.y) if event.inaxes is self.axes else None
        visible = point is not None
        changed = self.annotation.get_visible() != visible
        if point is not None:
            changed = changed or self.annotation.get_text() != point.text
            self.annotation.xy = (point.x, point.y)
            self.annotation.set_text(point.text)
            right_half = event.x > self.canvas.width() * self.canvas.device_pixel_ratio * 0.6
            self.annotation.set_horizontalalignment("right" if right_half else "left")
            self.annotation.xyann = (-12 if right_half else 12, 12)  # keep it inside the plot
        self.annotation.set_visible(visible)
        if changed:
            self.canvas.draw_idle()


class ChartsPage(Page):
    """One chart of the active selection, chosen by type, explorable in place."""

    key = "charts"

    def __init__(self, window: MainWindow) -> None:
        """Build the selector, the save button, the note and the chart area."""
        super().__init__(window)
        self.kind_box = QComboBox()
        for kind in KINDS:
            self.kind_box.addItem(t(f"charts.kind.{kind}"), kind)
        self.kind_box.currentIndexChanged.connect(lambda _: self.draw())
        self.save_button = button(t("charts.save"), self.save)
        self.note_label = label("", "note")
        self.chart: InteractiveChart | None = None
        self.data: ChartData | None = None
        self._stale = True
        options = QHBoxLayout()
        options.addWidget(label(t("charts.kind"), wrap=False))
        options.addWidget(self.kind_box)
        options.addStretch()
        options.addWidget(self.save_button)
        self.area = QVBoxLayout()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 16)
        layout.setSpacing(10)
        layout.addLayout(page_header(t("charts.title"), t("charts.subtitle")))
        layout.addLayout(options)
        layout.addWidget(self.note_label)
        layout.addLayout(self.area, 1)

    def choose(self, kind: str) -> None:
        """Select a chart type (draws it at once)."""
        self.kind_box.setCurrentIndex(self.kind_box.findData(kind))

    def refresh(self) -> None:
        """Forget the chart values; draw again only when the page is on screen."""
        self._stale = True
        self.data = None
        self.chart = None
        clear_layout(self.area)
        if self.isVisible():
            self.draw()

    def showEvent(self, event) -> None:  # noqa: N802 - Qt naming
        """Draw a pending chart when the page appears (the comparison is the slow part)."""
        super().showEvent(event)
        if self._stale:
            self.draw()

    def draw(self) -> None:
        """Draw the chosen chart of the current selection, or show the empty state."""
        from sales_data_analyzer.charts.images import ChartInputs, build_figure, has_data

        self._stale = False
        clear_layout(self.area)
        self.chart = None
        self.note_label.setText("")
        if self.session.current is None:
            return
        empty = self.window_.empty_state()
        self.save_button.setEnabled(empty is None)
        if empty is not None:
            self.area.addWidget(empty)
            return
        if self.data is None:
            try:  # also runs from refresh, so failures are shown inline, never re-refreshed
                self.data = self.session.chart_data()
            except Exception as error:
                self.area.addWidget(label(describe_failure(error), "banner"))
                return
        kind = self.kind_box.currentData()
        inputs = replace(
            ChartInputs.from_data(self.data, weekday_names=[weekday(i)[:3] for i in range(7)]),
            title=self._subtitle(),
            forecast_title=self._method(),
        )
        if not has_data(kind, inputs):
            self.area.addWidget(label(t("charts.no_data"), "banner"))
            return
        figure = build_figure(kind, inputs, chart_labels(SCREEN_DPI))
        if kind == "daily":
            from matplotlib.dates import DateFormatter

            figure.axes[0].xaxis.set_major_formatter(DateFormatter(t("charts.date_axis")))
        self.chart = InteractiveChart(figure, hover_points(kind, self.data), kind)
        self.area.addWidget(self.chart, 1)
        self.note_label.setText(self._note() if kind == "daily" else t("charts.period_note"))

    def _note(self) -> str:
        """Explain the estimate line, or why it is missing."""
        if self.data.forecast_refusal is not None:
            reason = reports.explain_forecast_refusal(self.data.forecast_refusal)
            return t("charts.forecast_off", reason=reason)
        return t("charts.forecast_on", title=self._method())

    def _method(self) -> str | None:
        """Return the translated name of the method behind the estimate line."""
        if self.data.forecast_key is None:
            return self.data.forecast_title
        return method_title(self.data.forecast_key, self.data.forecast_title or "")

    def _subtitle(self) -> str:
        """Return 'company — period' in the active language."""
        company = self.session.require_current().company.name
        return f"{company} — {reports.period_text(self.session.selection)}"

    def save(self) -> None:
        """Save the three level 3 charts as PNG files, asking before replacing any."""
        from sales_data_analyzer.charts.images import ChartInputs, save_charts

        folder = self.window_.prompter.choose_folder()
        if folder is None:
            return

        def replace(path) -> bool:
            return self.window_.prompter.confirm(t("charts.replace", name=path.name))

        def write():  # -> (ChartData, paths)
            data = self.session.chart_data()
            return data, save_charts(ChartInputs.from_data(data), folder, replace=replace)

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
            reason = reports.explain_forecast_refusal(data.forecast_refusal)
            lines.insert(0, t("charts.forecast_off", reason=reason))
        self.window_.prompter.inform("\n".join(lines))
