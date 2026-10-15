"""Helpers to drive TerminalMenu with scripted input in tests."""

from collections.abc import Iterable

from sales_data_analyzer.application import SalesSession
from sales_data_analyzer.cli.menu import TerminalMenu


class Script:
    """Feed lines to the menu and capture every prompt and output line."""

    def __init__(self, lines: Iterable[str], session: SalesSession | None = None) -> None:
        self._lines = iter(lines)
        self.output: list[str] = []
        self.menu = TerminalMenu(session, self._input, self.output.append)

    def _input(self, prompt: str) -> str:
        self.output.append(prompt)
        try:
            return next(self._lines)
        except StopIteration:
            raise EOFError from None

    def run(self) -> int:
        """Run the menu until exit or the end of the script."""
        return self.menu.run()

    @property
    def text(self) -> str:
        """All captured output joined by newlines."""
        return "\n".join(self.output)

    @property
    def last_header(self) -> str:
        """The most recent menu header line."""
        return [line for line in self.output if line.startswith("Company: ")][-1]
