"""Terminal program over a database: start-up, exit, reopen and storage errors."""

import contextlib
from datetime import datetime, timedelta
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


class MaintenanceMenuTests(DatabaseMenuTestCase):
    """Options 13-17: edit, delete and list (contracts/terminal-menu.md)."""

    IMPORTED = ["1", "Acme", "Retail", "7", VALID]

    def test_edit_company_with_blank_keeps_sector_and_survives_restart(self) -> None:
        script = self.menu(["1", "Acme", "Retail", "13", "Acme Ltda", "", "0"])
        self.assertIn("New name (blank = keep): ", script.output)
        self.assertIn("Company updated: Acme Ltda (Retail)", script.output)
        second = self.menu(["2", "1", "0"])
        self.assertIn("Selected: Acme Ltda", second.output)

    def test_edit_company_refuses_a_used_name(self) -> None:
        script = self.menu(["1", "Acme", "Retail", "1", "Beta", "Food", "13", " acme ", "", "0"])
        self.assertIn("Not done: a company with this name already exists.", script.output)

    def test_edit_product(self) -> None:
        script = self.menu(self.IMPORTED + ["14", "007", "", "Coffee", "14", "999", "0"])
        self.assertIn("New category (blank = keep): ", script.output)
        self.assertIn("Product updated: 007 Coffee, premium (Coffee)", script.output)
        self.assertIn("Product not found.", script.output)

    def test_delete_product_refuses_sold_products_and_asks_before_deleting(self) -> None:
        script = self.menu(
            self.IMPORTED
            + ["3", "009", "Mug", "Kitchen", "15", "007", "15", "009", "n", "15", "009", "y", "0"]
        )
        self.assertIn(
            "Not done: this product appears in 1 sale and cannot be deleted.", script.output
        )
        self.assertIn("Delete product 009 Mug? [y/N] ", script.output)
        self.assertIn("Nothing was deleted.", script.output)
        self.assertIn("Product deleted: 009", script.output)
        self.assertEqual(row_counts(self.path)["product"], 2)

    def test_list_sales_follows_the_selection(self) -> None:
        script = self.menu(
            self.IMPORTED + ["16", "8", "2026-01-02", "2026-01-02", "16", "8", "2026-03-01",
                             "2026-03-01", "16", "0"]
        )  # fmt: skip
        tables = [i for i, line in enumerate(script.output) if line.startswith("Sale ID")]
        self.assertEqual(len(tables), 2)
        first = script.output[tables[0] : tables[0] + 4]
        self.assertEqual(
            first,
            [
                "Sale ID  Date and time        Items  Total",
                "001      2026-01-01T10:00:00      2  40.40",
                "002      2026-01-02T10:00:00      1   5.00",
                "2 sales",
            ],
        )
        self.assertTrue(script.output[tables[1] + 1].startswith("002 "))
        self.assertEqual(script.output[tables[1] + 2], "1 sale")
        self.assertIn("No sales in the current selection.", script.output)

    def test_delete_sale_confirms_with_items_and_total(self) -> None:
        script = self.menu(self.IMPORTED + ["17", "S9", "17", "001", "", "17", "001", "y", "0"])
        self.assertIn("Sale not found.", script.output)
        self.assertIn("Delete sale 001 (2 items, total 40.40)? [y/N] ", script.output)
        self.assertIn("Nothing was deleted.", script.output)
        self.assertIn("Sale deleted: 001", script.output)
        self.assertEqual(row_counts(self.path)["sale"], 1)
        self.assertEqual(row_counts(self.path)["sale_item"], 1)

    def test_options_need_a_company(self) -> None:
        script = self.menu(["13", "16", "0"])
        self.assertEqual(script.output.count("Not done: create or select a company first."), 2)


class ExplorationMenuTests(DatabaseMenuTestCase):
    """Options 18-19: grouped totals and period comparison."""

    FOURTEEN = str(FIXTURES / "forecast_14_days.csv")

    def table(self, script: Script, title: str) -> list[str]:
        """Return the lines from a result title up to the next prompt."""
        start = next(i for i, line in enumerate(script.output) if line.startswith(title))
        end = next(i for i in range(start, len(script.output)) if script.output[i] == "")
        return script.output[start:end]

    def test_weekly_totals_match_the_financial_analysis(self) -> None:
        script = self.menu(["1", "Acme", "Retail", "7", self.FOURTEEN, "18", "2", "10", "0"])
        table = self.table(script, "Sales by week")
        self.assertEqual(
            table[1].split(), ["Period", "Revenue", "Cost", "Gross", "profit", "Sales"]
        )
        self.assertEqual(
            [line.split()[0] for line in table[2:]], ["2026-W01", "2026-W02", "2026-W03", "Total"]
        )
        total = table[-1].split()
        revenue = next(line for line in script.output if line.startswith("Revenue"))
        self.assertEqual(total[1], revenue.split()[-1])

    def test_missing_days_question_and_note(self) -> None:
        lines = ["1", "Acme", "Retail", "7", VALID, "6", "003", "2026-01-05T10:00:00", "007",
                 "1", "1", "1", "", "18", "1", "n", "18", "1", "y", "0"]  # fmt: skip
        script = self.menu(lines)
        self.assertIn("2 days between the first and last sale have no sales.", script.output)
        self.assertIn(
            "2 days without recorded sales between the first and last sale "
            "(periods without sales are not listed).",
            script.output,
        )
        self.assertIn("2 days without sales shown as zero.", script.output)
        self.assertTrue(any(line.startswith("2026-01-03 ") for line in script.output))

    def test_category_and_weekday_views(self) -> None:
        script = self.menu(["1", "Acme", "Retail", "7", self.FOURTEEN, "18", "5", "18", "4", "0"])
        self.assertEqual(
            self.table(script, "Sales by category")[2].split()[:2], ["Beverages", "105"]
        )
        weekdays = self.table(script, "Revenue by weekday")
        self.assertEqual(weekdays[2].split(), ["Monday", "2", "170.00", "85.00"])
        self.assertEqual(weekdays[-1], "Averages count only days with sales.")

    def test_offset_data_says_days_are_utc(self) -> None:
        aware = str(FIXTURES / "aware_sales.csv")
        script = self.menu(["1", "Acme", "Retail", "7", aware, "18", "3", "0"])
        self.assertIn("Days are UTC days.", script.output)

    def test_empty_selection(self) -> None:
        script = self.menu(["1", "Acme", "Retail", "18", "0"])
        self.assertIn("No sales in the current selection.", script.output)

    def test_compare_periods_with_zero_base(self) -> None:
        script = self.menu(
            ["1", "Acme", "Retail", "7", VALID, "19", "2025-01-01", "2025-01-31",
             "2026-01-01", "2026-01-02", "0"]
        )  # fmt: skip
        table = self.table(script, "Period comparison")
        self.assertEqual(
            table[0],
            "Period comparison: first 2025-01-01 to 2025-01-31, second 2026-01-01 to 2026-01-02",
        )
        self.assertEqual(table[2].split(), ["Revenue", "0.00", "45.40", "+45.40", "n/a"])
        self.assertEqual(table[4].split()[-1], "n/a")

    def test_reversed_period_is_refused(self) -> None:
        script = self.menu(
            ["1", "Acme", "Retail", "19", "2026-01-02", "2026-01-01", "2026-01-01", "2026-01-02",
             "0"]
        )  # fmt: skip
        self.assertIn("Not done: the end date is before the start date.", script.output)


class ForecastComparisonMenuTests(DatabaseMenuTestCase):
    """Option 20: comparison table, honest notes, method choice and estimates."""

    def import_days(self, days: int, skip: tuple[int, ...] = ()) -> str:
        """Write a CSV with one sale per day and a weekly pattern; return its path."""
        lines = ["sale_id,date_time,product_id,product,category,quantity,unit_price,unit_cost"]
        for day in range(days):
            if day in skip:
                continue
            moment = (datetime(2026, 1, 5, 10) + timedelta(days=day)).isoformat()
            quantity = 1 + day // 7 + (4 if day % 7 == 5 else 0)
            lines.append(f"S{day},{moment},001,Pen,Office,{quantity},10.00,4.00")
        path = self.path.parent / f"history_{days}.csv"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return str(path)

    def test_strong_evidence_table_and_model_estimates(self) -> None:
        csv = self.import_days(63)
        script = self.menu(["1", "Acme", "Retail", "7", csv, "20", "21", "", "0"])
        text = script.text
        self.assertIn(
            "History: 63 days (2026-01-05 to 2026-03-08); evaluation: 4 blocks of 7 days "
            "from 2026-02-09",
            text,
        )
        self.assertIn("Lowest error in this evaluation: Linear trend + weekday.", text)
        self.assertNotIn("No model beat", text)
        self.assertIn("Method for the estimates (number, blank = Linear trend + weekday): ", text)
        self.assertIn("Estimates (Linear trend + weekday), next 21 days:", text)
        effects = next(line for line in script.output if line.startswith("Weekday effects"))
        self.assertRegex(effects, r"^Weekday effects vs Monday: Tue [+-]\d+\.\d\d, .*, Sun ")
        self.assertRegex(effects, r"; trend per day [+-]\d+\.\d\d\.$")
        self.assertIn("estimates beyond 14 days are extrapolation.", text)
        self.assertIn("Limitations: past errors do not guarantee future accuracy;", text)

    def test_weak_evidence_skips_and_chosen_method(self) -> None:
        csv = self.import_days(21)
        script = self.menu(["1", "Acme", "Retail", "7", csv, "20", "", "x", "2", "0"])
        text = script.text
        self.assertIn("Skipped: Linear trend + weekday (needs 35 days of history)", text)
        self.assertIn(
            "Evidence too limited to name a lowest-error method (7 evaluated days).", text
        )
        self.assertIn("Invalid value: expected a positive whole number up to 4.", text)
        header = next(i for i, line in enumerate(script.output) if line.startswith("#  Method"))
        second = script.output[header + 2]
        self.assertTrue(second.startswith("2  "))
        title = second[3:].split("  ")[0]
        self.assertIn(f"Estimates ({title}), next 7 days:", text)

    def test_missing_days_question(self) -> None:
        csv = self.import_days(20, skip=(3, 10))
        script = self.menu(["1", "Acme", "Retail", "7", csv, "20", "", "n", "20", "", "y", "", "0"])
        self.assertIn("Forecast cancelled.", script.output)
        self.assertIn(
            "2 missing days were treated as zero; weekly methods learn from these zeros.",
            script.output,
        )

    def test_too_little_history(self) -> None:
        csv = self.import_days(11)
        script = self.menu(["1", "Acme", "Retail", "7", csv, "20", "", "0"])
        self.assertIn(
            "Not done: 11 day(s) of history available, at least 12 needed.", script.output
        )


if __name__ == "__main__":
    unittest.main()
