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
from sales_data_analyzer.gui.widgets import cells

from support.databases import row_counts
from support.sessions import daily_session

FIXTURES = Path(__file__).parent / "fixtures"
NOT_SAVED = "Não foi possível gravar no banco de dados. Nada foi alterado."


def page(window, key):
    """Return the window's page with the given navigation key."""
    return window.page(key)


class ButtonWiringTests(WindowTestCase):
    """Buttons are connected to their handlers (signals pass no stray arguments)."""

    def test_every_action_button_runs_its_handler(self) -> None:
        win = self.window(daily_session(35))
        self.prompter.queue("company", CompanyValues("Bolt", "Tools"))
        page(win, "home").new_button.click()
        self.assertEqual(win.session.current.company.name, "Bolt")
        win.go("home")
        page(win, "home").open_buttons[0].click()
        self.assertEqual(win.session.current.company.name, "Acme")

        catalog, sales = page(win, "catalog"), page(win, "sales")
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

        analyses = page(win, "analyses")
        analyses.choose("month")
        self.assertEqual(analyses.shown.title, "Vendas por mês")
        forecast = page(win, "forecast")
        forecast.compare_button.click()
        self.assertEqual(forecast.shown.tables[0].title, "Comparação de métodos")
        forecast.use_method_button.click()
        forecast.linear_button.click()
        self.assertEqual(forecast.shown.tables[0].title, "Previsão linear")
        charts = page(win, "charts")
        win.go("charts")
        charts.kind_box.setCurrentIndex(1)
        self.assertEqual(charts.chart.kind, "monthly")
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
        page(self.win, "catalog").register_product()
        self.repository = self.win.session.repository

    def assert_unchanged(self, before: dict[str, int], catalog: list, sales: list) -> None:
        self.assertEqual(self.prompter.warnings, [NOT_SAVED])
        self.assertEqual(row_counts(self.path), before)
        self.assertEqual(cells(page(self.win, "catalog").table), catalog)
        self.assertEqual(cells(page(self.win, "sales").table), sales)

    def snapshot(self):
        return (
            row_counts(self.path),
            cells(page(self.win, "catalog").table),
            cells(page(self.win, "sales").table),
        )

    def test_register_product(self) -> None:
        before = self.snapshot()
        self.prompter.queue("product", ProductValues("P2", "Ink", "Supplies"))
        with mock.patch.object(self.repository, "add_product", side_effect=PersistenceError()):
            page(self.win, "catalog").register_product()
        self.assert_unchanged(*before)

    def test_record_sale(self) -> None:
        before = self.snapshot()
        values = SaleValues(
            "S1", datetime(2026, 3, 1), (ItemInput("P1", 1, Decimal(1), Decimal(0)),)
        )
        self.prompter.queue("sale", values)
        with mock.patch.object(self.repository, "add_sales", side_effect=PersistenceError()):
            page(self.win, "sales").record_sale()
        self.assert_unchanged(*before)

    def test_import(self) -> None:
        before = self.snapshot()
        self.prompter.queue("open_csv", FIXTURES / "valid_sales.csv")
        with mock.patch.object(self.repository, "add_sales", side_effect=PersistenceError()):
            page(self.win, "sales").import_csv()
        self.assert_unchanged(*before)
        self.assertEqual(self.prompter.notices, [])


class ReopenTests(StoredWindowTestCase):
    def test_import_and_deletions_survive_reopen(self) -> None:
        win = self.open_window()
        self.prompter.queue("company", CompanyValues("Acme", "Retail"))
        win.new_company()
        self.prompter.queue("open_csv", FIXTURES / "valid_sales.csv")
        page(win, "sales").import_csv()
        sales = page(win, "sales")
        sales.select("002")
        self.prompter.queue("confirm", True, True)
        sales.delete_sale()
        catalog = page(win, "catalog")
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
        with mock.patch.object(page(win, "sales"), "refresh", side_effect=RuntimeError()):
            win.new_company()
        self.assertEqual(
            self.prompter.warnings,
            [
                "Já existe uma empresa com esse nome (maiúsculas e espaços não contam).",
                "Ocorreu um erro inesperado (RuntimeError). Seus dados não foram alterados.",
            ],
        )

    def test_uncaught_slot_errors_are_shown(self) -> None:
        win = self.window()
        hook = _report_uncaught(win)
        hook(ValueError, ValueError("bad"), None)
        self.assertEqual(self.prompter.warnings, ["Um valor não é válido: bad"])


if __name__ == "__main__":
    unittest.main()
