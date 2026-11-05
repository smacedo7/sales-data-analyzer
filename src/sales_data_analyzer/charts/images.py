"""PNG charts written with Matplotlib's Agg renderer (no window, no pyplot state).

Each file is written to a temporary name in the target folder and then moved into
place, so a failure never leaves a partial file and an existing chart is replaced
only after the caller agreed.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import os
from pathlib import Path
import tempfile
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from matplotlib.figure import Figure

    from sales_data_analyzer.application import ChartData

# Reference palette (validated): categorical slots 1 and 2 on the light surface.
_SURFACE = "#fcfcfb"
_TEXT = "#0b0b0b"
_MUTED = "#52514e"
_GRID = "#e4e3df"
_HISTORY = "#2a78d6"
_FORECAST = "#eb6834"

_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

DAILY_FILE = "daily_revenue.png"
MONTHLY_FILE = "monthly_revenue.png"
PRODUCTS_FILE = "top_products.png"


class ChartWriteError(OSError):
    """Raised when the chart folder cannot be created or written; no file was left."""


@dataclass(frozen=True)
class ChartInputs:
    """Exact values to draw; forecast is empty when no estimate is available."""

    title: str
    daily: tuple[tuple[date, Decimal], ...]
    monthly: tuple[tuple[str, Decimal], ...]
    top_products: tuple[tuple[str, Decimal], ...]
    forecast: tuple[tuple[date, float], ...] = ()
    forecast_title: str | None = None
    weekday: tuple[tuple[str, Decimal], ...] = ()

    @classmethod
    def from_data(
        cls, data: "ChartData", weekday_names: Sequence[str] = _WEEKDAYS
    ) -> "ChartInputs":
        """Return the inputs for the application's chart values (labels as 'ID name').

        Weekdays without sales in the counted days are drawn as zero.
        """
        return cls(
            title=data.title,
            daily=data.daily,
            monthly=data.monthly,
            top_products=tuple((row.label, row.revenue) for row in data.top_products),
            forecast=data.forecast,
            forecast_title=data.forecast_title,
            weekday=tuple(
                (weekday_names[index], average if average is not None else Decimal(0))
                for index, average in data.weekday
            ),
        )


ChartKind = Literal["daily", "monthly", "products", "weekday"]
"""Chart kinds: the three level 3 charts saved as PNG, plus the weekday averages."""

CHART_KINDS: tuple[ChartKind, ...] = ("daily", "monthly", "products", "weekday")


@dataclass(frozen=True)
class ChartLabels:
    """Visible chart texts and the axis number format (English defaults for PNG files).

    The desktop window passes translated texts; `products` is formatted with
    `{count}` and `estimate` with `{title}`.
    """

    daily: str = "Daily revenue"
    monthly: str = "Monthly revenue"
    products: str = "Top {count} products by revenue"
    weekday: str = "Average revenue per weekday (days with sales)"
    revenue: str = "Revenue"
    estimate: str = "Estimate ({title})"
    axis_number: Callable[[float], str] = lambda value: f"{value:,.0f}"


def has_data(kind: ChartKind, inputs: ChartInputs) -> bool:
    """Return True when the chart of this kind has values to draw."""
    return bool({"daily": inputs.daily, "monthly": inputs.monthly,
                 "products": inputs.top_products, "weekday": inputs.weekday}[kind])  # fmt: skip


def build_figure(
    kind: ChartKind, inputs: ChartInputs, labels: ChartLabels | None = None
) -> "Figure":
    """Return the styled Matplotlib figure of one chart, with no canvas attached.

    The same builders draw the PNG files (default English labels) and the charts
    embedded in the desktop window (translated labels and its own Qt canvas).
    Raise ValueError for an unknown kind or a chart without data.
    """
    builders = {"daily": _daily_chart, "monthly": _monthly_chart,
                "products": _products_chart, "weekday": _weekday_chart}  # fmt: skip
    if kind not in builders:
        raise ValueError("unknown chart kind")
    if not has_data(kind, inputs):
        raise ValueError("this chart has no data")
    return builders[kind](inputs, labels or ChartLabels())


def _figure(width: float = 8.0, height: float = 4.5):  # -> (Figure, Axes)
    """Return a canvas-less figure with one styled axes."""
    from matplotlib.figure import Figure

    figure = Figure(figsize=(width, height), dpi=120, facecolor=_SURFACE)
    axes = figure.add_subplot()
    axes.set_facecolor(_SURFACE)
    for side in ("top", "right"):
        axes.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        axes.spines[side].set_color(_GRID)
    axes.tick_params(colors=_MUTED, labelsize=9)
    axes.grid(color=_GRID, linewidth=0.8)
    axes.set_axisbelow(True)
    return figure, axes


def _titles(axes, title: str, subtitle: str) -> None:
    """Set a left-aligned title and a muted subtitle."""
    axes.set_title(title, loc="left", color=_TEXT, fontsize=12, fontweight="bold", pad=22)
    axes.text(0, 1.02, subtitle, transform=axes.transAxes, color=_MUTED, fontsize=9, va="bottom")


def _daily_chart(inputs: ChartInputs, labels: ChartLabels):
    figure, axes = _figure()
    days = [day for day, _ in inputs.daily]
    axes.plot(days, [float(v) for _, v in inputs.daily], color=_HISTORY, linewidth=2,
              marker="o", markersize=3, label=labels.revenue)  # fmt: skip
    if inputs.forecast:
        axes.plot([d for d, _ in inputs.forecast], [v for _, v in inputs.forecast],
                  color=_FORECAST, linewidth=2, linestyle="--", marker="o", markersize=3,
                  label=labels.estimate.format(title=inputs.forecast_title))  # fmt: skip
        legend = axes.legend(frameon=False, fontsize=9, loc="upper left")
        for text in legend.get_texts():
            text.set_color(_TEXT)
    axes.set_ylim(bottom=0)
    axes.yaxis.set_major_formatter(_money_formatter(labels))
    figure.autofmt_xdate()
    _titles(axes, labels.daily, inputs.title)
    return figure


def _monthly_chart(inputs: ChartInputs, texts: ChartLabels):
    figure, axes = _figure()
    labels = [label for label, _ in inputs.monthly]
    axes.bar(labels, [float(v) for _, v in inputs.monthly], color=_HISTORY, width=0.6)
    axes.grid(axis="x", visible=False)
    if len(labels) < 4:  # keep a lone bar from filling the whole plot
        axes.set_xlim(-1.5, len(labels) + 0.5)
    axes.yaxis.set_major_formatter(_money_formatter(texts))
    if len(labels) > 8:
        axes.tick_params(axis="x", labelrotation=45)
    _titles(axes, texts.monthly, inputs.title)
    return figure


def _weekday_chart(inputs: ChartInputs, texts: ChartLabels):
    figure, axes = _figure()
    names = [name for name, _ in inputs.weekday]
    axes.bar(names, [float(v) for _, v in inputs.weekday], color=_HISTORY, width=0.6)
    axes.grid(axis="x", visible=False)
    axes.yaxis.set_major_formatter(_money_formatter(texts))
    _titles(axes, texts.weekday, inputs.title)
    return figure


def _products_chart(inputs: ChartInputs, labels: ChartLabels):
    rows = list(reversed(inputs.top_products))  # largest at the top
    figure, axes = _figure(height=max(2.5, 0.45 * len(rows) + 1.5))
    axes.barh([label for label, _ in rows], [float(v) for _, v in rows],
              color=_HISTORY, height=0.6)  # fmt: skip
    axes.grid(axis="y", visible=False)
    axes.xaxis.set_major_formatter(_money_formatter(labels))
    _titles(axes, labels.products.format(count=len(rows)), inputs.title)
    return figure


def _money_formatter(labels: ChartLabels):
    from matplotlib.ticker import FuncFormatter

    return FuncFormatter(lambda value, _: labels.axis_number(value))


def save_charts(
    inputs: ChartInputs, folder: str | Path, *, replace: Callable[[Path], bool]
) -> tuple[Path, ...]:
    """Write the daily, monthly and top-product charts into folder; return written files.

    A chart without data is not written. For an existing file, replace(path) decides;
    a False answer keeps the file. All charts are rendered to temporary files first
    and only then moved into place, so a rendering failure leaves no new file (a
    folder that fails between two moves keeps the files already moved). Raise ChartWriteError when the folder cannot be created or written;
    temporary files are always removed.
    """
    folder = Path(folder)
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError:
        raise ChartWriteError("the folder cannot be written") from None
    if not folder.is_dir():
        raise ChartWriteError("the folder cannot be written")
    plans: Sequence[tuple[str, bool, Callable]] = (
        (DAILY_FILE, bool(inputs.daily), _daily_chart),
        (MONTHLY_FILE, bool(inputs.monthly), _monthly_chart),
        (PRODUCTS_FILE, bool(inputs.top_products), _products_chart),
    )
    targets = [
        (folder / name, draw)
        for name, has_data, draw in plans
        if has_data and (not (folder / name).exists() or replace(folder / name))
    ]
    staged: list[tuple[str, Path]] = []
    try:
        for target, draw in targets:  # render everything before touching any target
            staged.append((_render(draw(inputs, ChartLabels()), folder), target))
        for temporary, target in staged:
            os.replace(temporary, target)
    except OSError:
        raise ChartWriteError("the folder cannot be written") from None
    finally:
        for temporary, _ in staged:
            Path(temporary).unlink(missing_ok=True)
    return tuple(target for _, target in staged)


def _render(figure, folder: Path) -> str:
    """Save figure as PNG (Agg canvas) into a new temporary file in folder; return its path."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    FigureCanvasAgg(figure)
    handle, temporary = tempfile.mkstemp(prefix=".chart-", suffix=".png", dir=folder)
    try:
        with os.fdopen(handle, "wb") as stream:
            figure.savefig(stream, format="png", facecolor=_SURFACE, bbox_inches="tight")
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return temporary
