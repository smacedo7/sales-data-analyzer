"""Desktop adapter (level 4): a PySide6 window over the application session.

This is the only package that imports PySide6. It opens the same SQLite
database as the terminal menu and calls the same application services.
"""

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys

OPEN_FAILURE_STATUS = 2
"""Exit status when the database cannot be used (same as the terminal)."""

__all__ = ["OPEN_FAILURE_STATUS", "main", "run"]


def _parse_arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    """Parse the command line (`--database PATH`)."""
    parser = argparse.ArgumentParser(
        prog="sales-data-analyzer-desktop",
        description="Sales Data Analyzer: desktop window over a local SQLite database.",
    )
    parser.add_argument(
        "--database",
        type=Path,
        metavar="PATH",
        help="database file to use (default: the same file as the terminal menu)",
    )
    return parser.parse_args(argv)


def _application():  # -> QApplication
    """Return the running QApplication, creating it on first use."""
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([sys.argv[0] if sys.argv else "sales"])


def run(argv: Sequence[str] | None = None, *, show_error=None, execute: bool = True) -> int:
    """Open the database, show the window until it is closed and return the exit status.

    A database that cannot be opened or loaded is reported (`show_error`, by
    default a message box) without changing the file, and the status is 2. The
    repository is always closed. With `execute=False` the window is built and
    closed at once (used by tests to check start-up without an event loop).
    """
    arguments = _parse_arguments(argv)
    from sales_data_analyzer.application import SalesSession
    from sales_data_analyzer.persistence import (
        DatabaseOpenError,
        SQLiteSalesRepository,
        default_database_path,
    )

    application = _application()
    if show_error is None:
        from PySide6.QtWidgets import QMessageBox

        def show_error(text: str) -> None:
            QMessageBox.critical(None, "Sales Data Analyzer", text)

    path = arguments.database if arguments.database is not None else default_database_path()
    try:
        repository = SQLiteSalesRepository.open(path)
    except DatabaseOpenError as error:
        show_error(f"Cannot open the database: {error}. The file was not changed.")
        return OPEN_FAILURE_STATUS
    try:
        try:
            session = SalesSession.open(repository)
        except DatabaseOpenError as error:
            show_error(f"Cannot open the database: {error}. The file was not changed.")
            return OPEN_FAILURE_STATUS
        from .main_window import MainWindow

        window = MainWindow(session)
        window.show()
        if not execute:
            window.close()
            return 0
        return application.exec()
    finally:
        repository.close()


def main() -> None:
    """Console-script entry point: run the desktop window and exit with its status."""
    raise SystemExit(run())
