"""Terminal adapter: the only package that reads input or prints output."""

import sys

from .menu import TerminalMenu

__all__ = ["TerminalMenu", "run"]


def run() -> int:
    """Start the interactive menu on standard input/output and return the exit status."""
    for stream in (sys.stdin, sys.stdout):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
    return TerminalMenu().run()
