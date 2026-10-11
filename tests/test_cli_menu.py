"""Scripted terminal sessions exercising the menu like a user would."""

from pathlib import Path
import unittest

from sales_data_analyzer.application import SalesSession
from sales_data_analyzer.cli.menu import DATA_NOTICE, NEEDS_COMPANY, TerminalMenu

from menu_script import Script


class MenuShellTests(unittest.TestCase):
    """Start, invalid input, exit confirmation and failure containment."""

    def test_start_shows_notice_and_exit_confirms(self) -> None:
        script = Script(["0", "y"])
        self.assertEqual(script.run(), 0)
        self.assertIn(DATA_NOTICE, script.output)
        self.assertIn("Company: none", script.output)
        self.assertIn("All data from this session will be lost.", script.output)

    def test_exit_declined_keeps_running(self) -> None:
        script = Script(["0", "n", "0", "y"])
        self.assertEqual(script.run(), 0)
        self.assertEqual(script.output.count("Exit? [y/N] "), 2)

    def test_invalid_option_and_answer(self) -> None:
        script = Script(["99", "abc", "0", "maybe", "y"])
        self.assertEqual(script.run(), 0)
        self.assertEqual(script.output.count("Invalid option."), 2)
        self.assertIn("Invalid value: answer y or n.", script.output)

    def test_end_of_input_exits_cleanly(self) -> None:
        script = Script([])
        self.assertEqual(script.run(), 0)
        self.assertIn("Data is kept in memory only and was discarded.", script.output)

    def test_company_guard(self) -> None:
        for option in map(str, range(3, 13)):
            with self.subTest(option=option):
                script = Script([option, "0", "y"])
                script.run()
                self.assertIn(NEEDS_COMPANY, script.output)

    def test_unexpected_error_is_contained_without_message(self) -> None:
        script = Script(["1", "0", "y"])

        def explode() -> None:
            raise RuntimeError("secret/path/data.csv")

        script.menu._options = tuple(
            option.__class__(option.number, option.label, explode, False)
            if option.number == 1
            else option
            for option in script.menu._options
        )
        self.assertEqual(script.run(), 0)
        self.assertIn("Unexpected error (RuntimeError). Your data is unchanged.", script.output)
        self.assertNotIn("secret", script.text)

    def test_default_session_is_created(self) -> None:
        self.assertIsNotNone(TerminalMenu(input_fn=lambda _: "", output_fn=lambda _: None).session)


if __name__ == "__main__":
    unittest.main()


class CompanyMenuTests(unittest.TestCase):
    """User Story 1 acceptance scenarios through the menu."""

    def test_create_list_and_select(self) -> None:
        script = Script(["1", "Coffee Shop", "Retail", "1", "Bakery", "Food", "2", "1", "0", "y"])
        script.run()
        self.assertIn("Company created and selected: Coffee Shop", script.output)
        self.assertIn("Company: Bakery (Food) | Selection: all data (0 sales)", script.output)
        self.assertIn("2. Bakery (Food)", script.output)
        self.assertIn("Selected: Coffee Shop", script.output)
        self.assertTrue(script.last_header.startswith("Company: Coffee Shop (Retail)"))

    def test_duplicate_company_is_refused(self) -> None:
        script = Script(["1", "Coffee Shop", "Retail", "1", " coffee shop ", "X", "0", "y"])
        script.run()
        self.assertIn("Not done: a company with this name already exists.", script.output)
        self.assertEqual(len(script.menu.session.workspaces), 1)

    def test_empty_values_are_asked_again(self) -> None:
        script = Script(["1", "  ", "Shop", "", "Retail", "0", "y"])
        script.run()
        self.assertEqual(script.output.count("Invalid value: a non-empty value is required."), 2)
        self.assertIn("Company created and selected: Shop", script.output)

    def test_select_with_no_companies_and_bad_number(self) -> None:
        script = Script(["2", "1", "A", "X", "2", "5", "0", "y"])
        script.run()
        self.assertIn("No companies yet.", script.output)
        self.assertIn("Not done: choose a company number from 1 to 1.", script.output)


FIXTURES = Path(__file__).parent / "fixtures"
VALID = str(FIXTURES / "valid_sales.csv")
NEW_COMPANY = ["1", "Coffee Shop", "Retail"]
EXIT = ["0", "y"]


class ImportMenuTests(unittest.TestCase):
    """User Story 2 acceptance scenarios through the menu."""

    def test_import_then_repeat_is_refused(self) -> None:
        script = Script([*NEW_COMPANY, "7", VALID, "7", f'"{VALID}"', *EXIT])
        script.run()
        self.assertIn("Imported 2 sales, 3 items. Products: 2 new, 0 reused.", script.output)
        self.assertIn(
            "Import refused: 2 sale ID(s) already exist in this company: 001, 002. "
            "Nothing was imported.",
            script.output,
        )
        self.assertEqual(len(script.menu.session.current.sales.sales), 2)

    def test_invalid_and_missing_files(self) -> None:
        invalid = str(FIXTURES / "invalid_sales.csv")
        missing = str(FIXTURES / "does-not-exist.csv")
        script = Script([*NEW_COMPANY, "7", invalid, "7", missing, *EXIT])
        script.run()
        self.assertIn(
            "Import refused at line 2, field quantity: expected positive integer.", script.output
        )
        self.assertIn("Import refused: cannot read file.", script.output)
        self.assertNotIn("does-not-exist", "\n".join(script.output[-20:]))
        self.assertEqual(script.menu.session.current.sales.sales, ())

    def test_catalog_conflict(self) -> None:
        session = SalesSession()
        session.create_company("Coffee Shop", "Retail").register_product(
            "007", "Coffee", "Beverages"
        )
        script = Script(["7", VALID, *EXIT], session=session)
        script.run()
        self.assertIn(
            "Import refused: 1 product ID(s) have a different name or category in the "
            "catalog: 007. Nothing was imported.",
            script.output,
        )


class AnalysisMenuTests(unittest.TestCase):
    """User Story 3 acceptance scenarios through the menu."""

    def setUp(self) -> None:
        self.base = [*NEW_COMPANY, "7", VALID]

    def test_analyses_on_all_data(self) -> None:
        script = Script([*self.base, "10", "11", *EXIT])
        script.run()
        self.assertIn("Financial analysis - Coffee Shop - all data (2 sales)", script.output)
        self.assertIn("Revenue ............ 45.40", script.output)
        self.assertIn("Gross margin ....... 59.9%", script.output)
        self.assertIn("007  Coffee, premium    4    40.40         24.20", script.output)

    def test_period_selection_and_clear(self) -> None:
        script = Script([*self.base, "8", "2026-01-02", "2026-01-02", "10", "9", "10", *EXIT])
        script.run()
        self.assertIn("Selection: 2026-01-02 to 2026-01-02 (1 sale)", script.output)
        self.assertIn("Revenue ............  5.00", script.output)
        self.assertIn("Selection: all data", script.output)
        self.assertTrue(script.last_header.endswith("Selection: all data (2 sales)"))

    def test_empty_period_shows_na(self) -> None:
        script = Script([*self.base, "8", "2020-01-01", "2020-01-31", "10", *EXIT])
        script.run()
        self.assertIn("Gross margin .......  n/a", script.output)

    def test_invalid_dates(self) -> None:
        script = Script(
            [
                *self.base,
                "8",
                "02/01/2026",
                "2026-01-02",
                "2026-01-01",
                "8",
                "2026-01-01",
                "2026-01-01",
                "8",
                "2026-01-03",
                "2026-01-02",
                *EXIT,
            ]
        )
        script.run()
        self.assertIn("Invalid value: expected a date as YYYY-MM-DD.", script.output)
        self.assertIn("Not done: the end date is before the start date.", script.output)
        self.assertTrue(script.last_header.endswith("2026-01-01 to 2026-01-01 (1 sale)"))


class CatalogAndSaleMenuTests(unittest.TestCase):
    """User Story 4 acceptance scenarios through the menu."""

    PRODUCTS = ["3", "001", "Coffee", "Beverages", "3", "002", "Tea", "Beverages"]

    def test_register_list_and_find(self) -> None:
        script = Script(
            [
                *NEW_COMPANY,
                "4",
                *self.PRODUCTS,
                "3",
                " 001 ",
                "X",
                "Y",
                "4",
                "5",
                "001",
                "5",
                "999",
                *EXIT,
            ]
        )
        script.run()
        self.assertIn("Catalog is empty.", script.output)
        self.assertIn("Product registered: 001 Coffee (Beverages)", script.output)
        self.assertIn("Not done: this product ID already exists in the catalog.", script.output)
        self.assertIn("001  Coffee  Beverages", script.output)
        self.assertIn("001: Coffee (Beverages)", script.output)
        self.assertIn("Product not found.", script.output)

    def test_record_sale_and_analyse(self) -> None:
        script = Script(
            [
                *NEW_COMPANY,
                *self.PRODUCTS,
                "6",
                "S-1",
                "2026-01-05T10:00:00",
                "001",
                "2",
                "10.50",
                "4.00",
                "002",
                "1",
                "5.00",
                "2.00",
                "",
                "10",
                *EXIT,
            ]
        )
        script.run()
        self.assertIn("Sale S-1 recorded: 2 items, total 26.00.", script.output)
        self.assertIn("Revenue ............ 26.00", script.output)
        self.assertIn("Cost ............... 10.00", script.output)

    def test_sale_refusals_and_retries(self) -> None:
        script = Script(
            [
                *NEW_COMPANY,
                "6",
                *self.PRODUCTS,
                "6",
                "S-1",
                "2026-01-05T10:00:00",
                "001",
                "1",
                "1",
                "1",
                "",
                "6",
                "S-1",
                "6",
                "S-2",
                "05/01/2026",
                "2026-01-06T10:00:00",
                "999",
                "001",
                "0",
                "2",
                "-1",
                "abc",
                "3.50",
                "1.00",
                "",
                "6",
                "S-3",
                "2026-01-07T10:00:00",
                "",
                *EXIT,
            ]
        )
        script.run()
        self.assertIn(
            "Not done: the catalog is empty; register or import products first.", script.output
        )
        self.assertIn("Not done: this sale ID already exists in this company.", script.output)
        self.assertIn("Product not found in the catalog; try again or leave blank.", script.output)
        self.assertIn("Invalid value: expected a positive whole number.", script.output)
        self.assertIn(
            "Invalid value: expected a non-negative decimal such as 10.50 (no separators).",
            script.output,
        )
        self.assertIn("Sale S-2 recorded: 1 item, total 7.00.", script.output)
        self.assertIn(
            "Not done: a sale needs at least one item. Nothing was stored.", script.output
        )
        sales = script.menu.session.current.sales.sales
        self.assertEqual([sale.id for sale in sales], ["S-1", "S-2"])
