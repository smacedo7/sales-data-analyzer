"""Charts for the terminal: text bars (no dependency) and PNG files (Matplotlib).

`charts.images` is imported only when images are saved, so text charts never load
Matplotlib.
"""

from .text import bar_lines

__all__ = ["bar_lines"]
