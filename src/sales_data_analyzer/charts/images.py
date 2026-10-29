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

# Reference palette (validated): categorical slots 1 and 2 on the light surface.
_SURFACE = "#fcfcfb"
_TEXT = "#0b0b0b"
_MUTED = "#52514e"
_GRID = "#e4e3df"
_HISTORY = "#2a78d6"
_FORECAST = "#eb6834"

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


def _figure(width: float = 8.0, height: float = 4.5):  # -> (Figure, Axes)
    """Return a figure with an Agg canvas and one styled axes."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    figure = Figure(figsize=(width, height), dpi=120, facecolor=_SURFACE)
    FigureCanvasAgg(figure)
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


def _daily_chart(inputs: ChartInputs):
    figure, axes = _figure()
    days = [day for day, _ in inputs.daily]
    axes.plot(days, [float(v) for _, v in inputs.daily], color=_HISTORY, linewidth=2,
              marker="o", markersize=3, label="Revenue")  # fmt: skip
    if inputs.forecast:
        axes.plot([d for d, _ in inputs.forecast], [v for _, v in inputs.forecast],
                  color=_FORECAST, linewidth=2, linestyle="--",
                  label=f"Estimate ({inputs.forecast_title})")  # fmt: skip
        legend = axes.legend(frameon=False, fontsize=9, loc="upper left")
        for text in legend.get_texts():
            text.set_color(_TEXT)
    axes.set_ylim(bottom=0)
    axes.yaxis.set_major_formatter(_money_formatter())
    figure.autofmt_xdate()
    _titles(axes, "Daily revenue", inputs.title)
    return figure


def _monthly_chart(inputs: ChartInputs):
    figure, axes = _figure()
    labels = [label for label, _ in inputs.monthly]
    axes.bar(labels, [float(v) for _, v in inputs.monthly], color=_HISTORY, width=0.6)
    axes.grid(axis="x", visible=False)
    if len(labels) < 4:  # keep a lone bar from filling the whole plot
        axes.set_xlim(-1.5, len(labels) + 0.5)
    axes.yaxis.set_major_formatter(_money_formatter())
    if len(labels) > 8:
        axes.tick_params(axis="x", labelrotation=45)
    _titles(axes, "Monthly revenue", inputs.title)
    return figure


def _products_chart(inputs: ChartInputs):
    rows = list(reversed(inputs.top_products))  # largest at the top
    figure, axes = _figure(height=max(2.5, 0.45 * len(rows) + 1.5))
    axes.barh([label for label, _ in rows], [float(v) for _, v in rows],
              color=_HISTORY, height=0.6)  # fmt: skip
    axes.grid(axis="y", visible=False)
    axes.xaxis.set_major_formatter(_money_formatter())
    _titles(axes, f"Top {len(rows)} products by revenue", inputs.title)
    return figure


def _money_formatter():
    from matplotlib.ticker import FuncFormatter

    return FuncFormatter(lambda value, _: f"{value:,.0f}")


def save_charts(
    inputs: ChartInputs, folder: str | Path, *, replace: Callable[[Path], bool]
) -> tuple[Path, ...]:
    """Write the daily, monthly and top-product charts into folder; return written files.

    A chart without data is not written. For an existing file, replace(path) decides;
    a False answer keeps the file. Raise ChartWriteError when the folder cannot be
    created or written; temporary files are removed in that case.
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
    written: list[Path] = []
    for name, has_data, draw in plans:
        target = folder / name
        if not has_data or (target.exists() and not replace(target)):
            continue
        _write(draw(inputs), target)
        written.append(target)
    return tuple(written)


def _write(figure, target: Path) -> None:
    """Save figure as PNG next to target, then move it into place."""
    try:
        handle, temporary = tempfile.mkstemp(prefix=".chart-", suffix=".png", dir=target.parent)
    except OSError:
        raise ChartWriteError("the folder cannot be written") from None
    try:
        with os.fdopen(handle, "wb") as stream:
            figure.savefig(stream, format="png", facecolor=_SURFACE, bbox_inches="tight")
        os.replace(temporary, target)
    except OSError:
        Path(temporary).unlink(missing_ok=True)
        raise ChartWriteError("the folder cannot be written") from None
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
