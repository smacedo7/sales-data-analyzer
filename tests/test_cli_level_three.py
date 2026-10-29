"""Terminal program over a database: start-up, exit, reopen and storage errors."""

import contextlib
import io
from pathlib import Path
import sqlite3
import unittest
from unittest import mock

from sales_data_analyzer.application import SalesSession
from sales_data_analyzer.cli import run
from sales_data_analyzer.persistence import SQLiteSalesRepository

from menu_script import Script
from support.databases import row_counts, temporary_database

FIXTURES = Path(__file__).parent / "fixtures"
VALID = str(FIXTURES / "valid_sales.csv")

# The level 2 scripted session (tests/test_cli_end_to_end.py) without its exit lines.
LEVEL_TWO_SESSION = [
    "1", "Café Açaí", "Retail", "7", VALID, "10", "7", VALID,
    "8", "2026-01-02", "2026-01-02", "10", "9", "11", "12", "", "",
]  # fmt: skip


class DatabaseMenuTestCase(unittest.TestCase):
    """Run scripted menus over sessions loaded from a temporary database."""

    def setUp(self) -> None:
        context = temporary_database()
        self.path = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)

    def menu(self, lines: list[str]) -> Script:
        """Run a scripted menu over a freshly opened session, like one program run."""
        repository = SQLiteSalesRepository.open(self.path)
        try:
            script = Script(lines, SalesSession.open(repository))
            self.assertEqual(script.run(), 0)
        finally:
            repository.close()
        return script


class StartAndExitTests(DatabaseMenuTestCase):
    """Start-up text, immediate exit and end of input (contracts/terminal-menu.md)."""

    def test_start_shows_database_and_counts_and_exit_needs_no_confirmation(self) -> None:
        script = self.menu(["0"])
        self.assertIn("Sales Data Analyzer - level 3 (terminal)", script.output)
        self.assertIn(f"Database: {self.path}", script.output)
        self.assertIn("Loaded 0 company(ies), 0 product(s), 0 sale(s).", script.output)
        self.assertNotIn("Exit? [y/N] ", script.output)
        self.assertEqual(script.output[-1], f"Data is saved in {self.path}.")

    def test_end_of_input_reports_saved_data(self) -> None:
        script = self.menu(["1", "Shop"])
        self.assertEqual(script.output[-1], f"Data is saved in {self.path}.")
        self.assertNotIn("discarded", script.text)

    def test_second_run_sees_the_first_run_data(self) -> None:
        first = self.menu(["1", "Acme", "Retail", "7", VALID, "10", "0"])
        second = self.menu(["2", "1", "10", "0"])
        self.assertIn("Loaded 1 company(ies), 2 product(s), 2 sale(s).", second.output)
        revenue = [line for line in first.output if line.startswith("Revenue")]
        self.assertEqual(len(revenue), 1)
        self.assertEqual(revenue, [line for line in second.output if line.startswith("Revenue")])

    def test_level_two_session_gives_the_same_results_over_a_database(self) -> None:
        memory = Script(LEVEL_TWO_SESSION + ["0", "y"])
        memory.run()
        stored = self.menu(LEVEL_TWO_SESSION + ["0"])

        def results(script: Script) -> list[str]:
            start = script.output.index("Company: none")
            return [
                line
                for line in script.output[start:]
                if "Exit" not in line and "Data is" not in line and "lost" not in line
            ]

        self.assertEqual(results(stored), results(memory))


class StorageErrorTests(DatabaseMenuTestCase):
    """Failed writes are reported and change nothing (FR-013)."""

    def test_busy_database_message(self) -> None:
        self.menu(["1", "Acme", "Retail", "0"])
        holder = sqlite3.connect(self.path, autocommit=True, timeout=0)
        self.addCleanup(holder.close)
        repository = SQLiteSalesRepository.open(self.path)
        self.addCleanup(repository.close)
        script = Script(
            ["2", "1", "3", "001", "Pen", "Office", "4", "0"], SalesSession.open(repository)
        )
        holder.execute("BEGIN IMMEDIATE")
        try:
            script.run()
        finally:
            holder.execute("ROLLBACK")
        self.assertIn(
            "Not done: the database is busy; another copy of the program may be using it. "
            "Nothing was changed.",
            script.output,
        )
        self.assertEqual(row_counts(self.path)["product"], 0)

    def test_refused_import_is_not_stored(self) -> None:
        self.menu(["1", "Acme", "Retail", "7", str(FIXTURES / "invalid_sales.csv"), "0"])
        second = self.menu(["0"])
        self.assertIn("Loaded 1 company(ies), 0 product(s), 0 sale(s).", second.output)


class CommandLineTests(DatabaseMenuTestCase):
    """`run()` arguments and open failures (exit status 2, file unchanged)."""

    def run_cli(self, argv: list[str], stdin: str) -> tuple[int, str, str]:
        """Call run() with redirected standard streams."""
        out, err = io.StringIO(), io.StringIO()
        with (
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(err),
            mock.patch("sys.stdin", io.StringIO(stdin)),
        ):
            status = run(argv)
        return status, out.getvalue(), err.getvalue()

    def test_database_option_is_used(self) -> None:
        status, out, _ = self.run_cli(["--database", str(self.path)], "1\nAcme\nRetail\n0\n")
        self.assertEqual(status, 0)
        self.assertIn(f"Database: {self.path}", out)
        self.assertEqual(row_counts(self.path)["company"], 1)

    def test_default_database_is_used_without_option(self) -> None:
        default = self.path.parent / "user data" / "sales.sqlite3"
        with mock.patch(
            "sales_data_analyzer.persistence.default_database_path", return_value=default
        ):
            status, out, _ = self.run_cli([], "1\nAcme\nRetail\n0\n")
        self.assertEqual(status, 0)
        self.assertIn(f"Database: {default}", out)
        self.assertEqual(row_counts(default)["company"], 1)

    def test_non_database_file_is_refused_unchanged(self) -> None:
        self.path.write_text("not a database\n" * 100, encoding="utf-8")
        before = self.path.read_bytes()
        status, out, err = self.run_cli(["--database", str(self.path)], "")
        self.assertEqual(status, 2)
        self.assertEqual(
            err.strip(),
            "Cannot open the database: the file is not a database. The file was not changed.",
        )
        self.assertNotIn(str(self.path), err)
        self.assertEqual(self.path.read_bytes(), before)

    def test_invalid_rows_are_refused(self) -> None:
        self.menu(["1", "Acme", "Retail", "0"])
        connection = sqlite3.connect(self.path, autocommit=True)
        connection.execute("PRAGMA ignore_check_constraints = ON")
        connection.execute("UPDATE company SET sector = ' '")
        connection.close()
        status, _, err = self.run_cli(["--database", str(self.path)], "")
        self.assertEqual(status, 2)
        self.assertIn("1 invalid row(s) in company", err)


if __name__ == "__main__":
    unittest.main()
