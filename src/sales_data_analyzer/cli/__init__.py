"""Terminal adapter: the only package that reads input or prints output."""

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys

from .menu import TerminalMenu

__all__ = ["TerminalMenu", "run"]

OPEN_FAILURE_STATUS = 2
"""Exit status when the database cannot be used."""


def _parse_arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    """Parse the command line (`--database PATH`)."""
    parser = argparse.ArgumentParser(
        prog="sales-data-analyzer",
        description="Sales Data Analyzer: terminal menu over a local SQLite database.",
    )
    parser.add_argument(
        "--database",
        type=Path,
        metavar="PATH",
        help="database file to use (default: a file in your user data folder)",
    )
    return parser.parse_args(argv)


def run(argv: Sequence[str] | None = None) -> int:
    """Open the database, start the interactive menu and return the exit status.

    `argv` defaults to the process arguments. A database that cannot be opened or
    loaded is reported without changing the file, and the status is 2.
    """
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
    arguments = _parse_arguments(argv)

    from sales_data_analyzer.application import SalesSession
    from sales_data_analyzer.persistence import (
        DatabaseOpenError,
        SQLiteSalesRepository,
        default_database_path,
    )

    path = arguments.database if arguments.database is not None else default_database_path()
    try:
        repository = SQLiteSalesRepository.open(path)
    except DatabaseOpenError as error:
        print(f"Cannot open the database: {error}. The file was not changed.", file=sys.stderr)
        return OPEN_FAILURE_STATUS
    try:
        try:
            session = SalesSession.open(repository)
        except DatabaseOpenError as error:
            print(f"Cannot open the database: {error}. The file was not changed.", file=sys.stderr)
            return OPEN_FAILURE_STATUS
        return TerminalMenu(session).run()
    finally:
        repository.close()
