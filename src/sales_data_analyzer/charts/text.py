"""Horizontal bar charts drawn with '#' characters, portable to any console."""

from collections.abc import Callable, Sequence
from decimal import ROUND_HALF_UP, Decimal


def bar_lines(
    rows: Sequence[tuple[str, Decimal]],
    *,
    width: int = 40,
    value_text: Callable[[Decimal], str] = str,
) -> list[str]:
    """Return one line per row: label, bar scaled to the largest value, and the value.

    Bars are proportional to `width` columns for the largest value; a positive value
    always gets at least one '#', and zero gets none. Values are printed with
    value_text (exact `str` by default). Raise ValueError for negative values or a
    width below 1.
    """
    if isinstance(width, bool) or not isinstance(width, int) or width < 1:
        raise ValueError("width must be a positive integer")
    if any(value < 0 for _, value in rows):
        raise ValueError("bar values cannot be negative")
    if not rows:
        return []
    largest = max(value for _, value in rows)
    label_width = max(len(label) for label, _ in rows)
    lines = []
    for label, value in rows:
        length = 0
        if value > 0:
            scaled = (value * width / largest).quantize(Decimal(1), rounding=ROUND_HALF_UP)
            length = max(1, int(scaled))
        bar = "#" * length
        lines.append(f"{label:<{label_width}} | {bar:<{width}} {value_text(value)}")
    return lines
