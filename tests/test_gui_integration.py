"""Desktop window integration: real button clicks, rollback on storage failure, reopen."""

from datetime import datetime
from decimal import Decimal
from pathlib import Path
import unittest
from unittest import mock

from support.qt import StoredWindowTestCase, WindowTestCase

from sales_data_analyzer.application import ItemInput, PersistenceError
from sales_data_analyzer.gui import _report_uncaught
from sales_data_analyzer.gui.forms import CompanyValues, ProductValues, SaleValues
from sales_data_analyzer.gui.pages import (
    AnalysesPage,
    CatalogPage,
    ChartsPage,
    ForecastPage,
    SalesPage,
)
from sales_data_analyzer.gui.tables import cells

from support.databases import row_counts
from support.sessions import daily_session

FIXTURES = Path(__file__).parent / "fixtures"
NOT_SAVED = "Not done: the database could not be updated. Nothing was changed."


def page(window, kind):
    """Return the window's page of the given class."""
    return next(p for p in window.pages if isinstance(p, kind))


class ButtonWiringTests(WindowTestCase):
    """Buttons are connected to their handlers (signals pass no stray arguments)."""

    def test_every_action_button_runs_its_handler(self) -> None:
        win = self.window(daily_session(35))
        self.prompter.queue("company", CompanyValues("Bolt", "Tools"))
        win.new_company_button.click()
        self.assertEqual(win.session.current.company.name, "Bolt")
        win.company_box.activated.emit(1)

        catalog, sales = page(win, CatalogPage), page(win, SalesPage)
        self.prompter.queue("product", ProductValues("P3", "Clip", "Office"))
        catalog.register_button.click()
        self.prompter.queue(
            "sale",
            SaleValues(
                "X1", datetime(2026, 2, 9, 12), (ItemInput("P3", 1, Decimal(1), Decimal(0)),)
            ),
        )
        sales.record_button.click()
        self.assertIn("X1", [row[0] for row in cells(sales.table)])

        analyses = page(win, AnalysesPage)
        analyses.show_button.click()
        self.assertTrue(analyses.output.toPlainText().startswith("Financial analysis - Acme"))
        forecast = page(win, ForecastPage)
        forecast.compare_button.click()
        self.assertTrue(forecast.output.toPlainText().startswith("Forecast comparison - Acme"))
        forecast.use_method_button.click()
        forecast.linear_button.click()
        self.assertTrue(forecast.output.toPlainText().startswith("Revenue forecast - Acme"))
        charts = page(win, ChartsPage)
        charts.refresh_button.click()
        self.assertEqual(len(charts.canvases), 3)
        win.all_data_button.click()
        self.assertEqual(self.prompter.warnings, [])
        self.assertNoPendingAnswers()


class RollbackTests(StoredWindowTestCase):
    """A storage failure during a window action leaves the file and the tables as they were."""

    def setUp(self) -> None:
        super().setUp()
        self.win = self.open_window()
        self.prompter.queue("company", CompanyValues("Acme", "Retail"))
        self.win.new_company()
        self.prompter.queue("product", ProductValues("P1", "Pen", "Office"))
        page(self.win, CatalogPage).register_product()
        self.repository = self.win.session.repository

    def assert_unchanged(self, before: dict[str, int], catalog: list, sales: list) -> None:
        self.assertEqual(self.prompter.warnings, [NOT_SAVED])
        self.assertEqual(row_counts(self.path), before)
        self.assertEqual(cells(page(self.win, CatalogPage).table), catalog)
        self.assertEqual(cells(page(self.win, SalesPage).table), sales)

    def snapshot(self):
        return (
            row_counts(self.path),
            cells(page(self.win, CatalogPage).table),
            cells(page(self.win, SalesPage).table),
        )

    def test_register_product(self) -> None:
        before = self.snapshot()
        self.prompter.queue("product", ProductValues("P2", "Ink", "Supplies"))
        with mock.patch.object(self.repository, "add_product", side_effect=PersistenceError()):
            page(self.win, CatalogPage).register_product()
        self.assert_unchanged(*before)

    def test_record_sale(self) -> None:
        before = self.snapshot()
        values = SaleValues(
            "S1", datetime(2026, 3, 1), (ItemInput("P1", 1, Decimal(1), Decimal(0)),)
        )
        self.prompter.queue("sale", values)
        with mock.patch.object(self.repository, "add_sales", side_effect=PersistenceError()):
            page(self.win, SalesPage).record_sale()
        self.assert_unchanged(*before)

    def test_import(self) -> None:
        before = self.snapshot()
        self.prompter.queue("open_csv", FIXTURES / "valid_sales.csv")
        with mock.patch.object(self.repository, "add_sales", side_effect=PersistenceError()):
            page(self.win, SalesPage).import_csv()
        self.assert_unchanged(*before)
        self.assertEqual(self.prompter.notices, [])


class ReopenTests(StoredWindowTestCase):
    def test_import_and_deletions_survive_reopen(self) -> None:
        win = self.open_window()
        self.prompter.queue("company", CompanyValues("Acme", "Retail"))
        win.new_company()
        self.prompter.queue("open_csv", FIXTURES / "valid_sales.csv")
        page(win, SalesPage).import_csv()
        sales = page(win, SalesPage)
        sales.select("002")
        self.prompter.queue("confirm", True, True)
        sales.delete_sale()
        catalog = page(win, CatalogPage)
        catalog.select("008")
        catalog.delete_product()  # unsold once sale 002 is gone

        stored = self.reopen().workspaces[0]
        self.assertEqual([s.id for s in stored.sales.sales], ["001"])
        self.assertEqual([p.id for p in stored.products], ["007"])
        self.assertEqual(stored.sales.sales[0].items[0].unit_price, Decimal("10.10"))
        self.assertNoPendingAnswers()


class SafetyTests(WindowTestCase):
    def test_unexpected_error_text_shows_only_the_type(self) -> None:
        win = self.window()
        self.prompter.queue("company", CompanyValues("A", "B"))
        with mock.patch.object(
            win.session, "create_company", side_effect=RuntimeError("/secret/path value")
        ):
            win.new_company()
        self.assertNotIn("secret", " ".join(self.prompter.warnings))

    def test_failing_redraw_after_a_failure_is_reported_once(self) -> None:
        win = self.window(daily_session(3))
        self.prompter.queue("company", CompanyValues("Acme", "X"))  # duplicate name
        with mock.patch.object(page(win, SalesPage), "refresh", side_effect=RuntimeError()):
            win.new_company()
        self.assertEqual(
            self.prompter.warnings,
            [
                "Not done: a company with this name already exists.",
                "Unexpected error (RuntimeError). Your data is unchanged.",
            ],
        )

    def test_uncaught_slot_errors_are_shown(self) -> None:
        win = self.window()
        hook = _report_uncaught(win)
        hook(ValueError, ValueError("bad"), None)
        self.assertEqual(self.prompter.warnings, ["Not done: bad."])


if __name__ == "__main__":
    unittest.main()
