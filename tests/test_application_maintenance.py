"""User story 3: edit companies and products, delete products and sales (FR-008 to FR-013)."""

from datetime import datetime
from decimal import Decimal
from pathlib import Path
import unittest

from sales_data_analyzer.analysis import ProductAnalysis
from sales_data_analyzer.application import (
    ConcurrentChangeError,
    DuplicateCompanyError,
    ItemInput,
    PersistenceError,
    ProductInUseError,
    ProductNotFoundError,
    SaleNotFoundError,
    SalesSession,
)
from sales_data_analyzer.persistence import SQLiteSalesRepository

from support.databases import raw_connection, row_counts
from test_application_persistence import PersistentSessionTestCase, describe

FIXTURES = Path(__file__).parent / "fixtures"


def item(product_id: str, quantity: int = 1, price: str = "10.50") -> ItemInput:
    """Return an item with a fixed cost of 4.25."""
    return ItemInput(product_id, quantity, Decimal(price), Decimal("4.25"))


class RefusingRepository(SQLiteSalesRepository):
    """Repository whose maintenance writes always fail, as a full disk would."""

    def _refuse(self, *args: object) -> None:
        raise PersistenceError()

    update_company = update_product = delete_product = delete_sale = _refuse


class MaintenanceTestCase(PersistentSessionTestCase):
    """A company with two products and two sales, the first sale using both products."""

    def setUp(self) -> None:
        super().setUp()
        self.fill(self.session)

    def fill(self, session: SalesSession) -> None:
        """Create the sample data in session."""
        self.acme = session.create_company("Acme", "Retail")
        self.acme.register_product("001", "Pen", "Office")
        self.acme.register_product("002", "Ink", "Office")
        self.acme.register_product("003", "Clip", "Office")
        self.acme.record_sale("S1", datetime(2026, 1, 1, 10), [item("001", 2), item("002")])
        self.acme.record_sale("S2", datetime(2026, 1, 2, 10), [item("001", price="3")])

    def reopened(self) -> SalesSession:
        """Return a new session loaded from the same file."""
        return self.start()


class EditCompanyTests(MaintenanceTestCase):
    def test_rename_and_sector_are_stored(self) -> None:
        self.session.update_company("  Acme Ltda  ", "Wholesale")
        company = self.reopened().workspaces[0].company
        self.assertEqual((company.name, company.sector), ("Acme Ltda", "Wholesale"))

    def test_none_keeps_each_value(self) -> None:
        self.session.update_company(None, "Food")
        self.session.update_company("Acme 2", None)
        company = self.reopened().workspaces[0].company
        self.assertEqual((company.name, company.sector), ("Acme 2", "Food"))

    def test_name_must_stay_unique_ignoring_case_and_spaces(self) -> None:
        self.session.create_company("Café Açaí", "Food")
        self.session.select_company(1)
        for name in ("café açaí", "  CAFÉ AÇAÍ "):
            with self.subTest(name=name), self.assertRaises(DuplicateCompanyError):
                self.session.update_company(name, None)
        self.assertEqual(self.acme.company.name, "Acme")

    def test_changing_only_the_case_of_its_own_name_is_allowed(self) -> None:
        self.session.update_company("ACME", None)
        self.assertEqual(self.reopened().workspaces[0].company.name, "ACME")

    def test_invalid_sector_leaves_name_and_database_unchanged(self) -> None:
        before = describe(self.reopened())
        with self.assertRaises(ValueError):
            self.session.update_company("Other", "   ")
        self.assertEqual(self.acme.company.name, "Acme")
        self.assertEqual(describe(self.reopened()), before)

    def test_failed_write_keeps_old_values(self) -> None:
        session = self.start(RefusingRepository)
        session.select_company(1)
        with self.assertRaises(PersistenceError):
            session.update_company("Other", "Food")
        company = session.current.company
        self.assertEqual((company.name, company.sector), ("Acme", "Retail"))


class EditProductTests(MaintenanceTestCase):
    def test_edit_is_stored_and_item_prices_are_kept(self) -> None:
        self.acme.update_product(" 001 ", "Blue pen", "Writing")
        workspace = self.reopened().workspaces[0]
        product = workspace.find_product("001")
        self.assertEqual((product.name, product.category), ("Blue pen", "Writing"))
        first = workspace.sales.sales[0].items[0]
        self.assertIs(first.product, product)
        self.assertEqual((first.unit_price, first.unit_cost), (Decimal("10.50"), Decimal("4.25")))

    def test_product_analysis_rows_follow_the_shared_product(self) -> None:
        self.acme.update_product("001", "Blue pen", None)
        result = ProductAnalysis().run(self.acme.sales)
        self.assertEqual(result.products[0].product_id, "001")
        self.assertEqual(self.acme.sales.sales[1].items[0].product.name, "Blue pen")

    def test_invalid_category_leaves_name_and_database_unchanged(self) -> None:
        before = describe(self.reopened())
        with self.assertRaises(ValueError):
            self.acme.update_product("001", "New", " ")
        self.assertEqual(self.acme.find_product("001").name, "Pen")
        self.assertEqual(describe(self.reopened()), before)

    def test_unknown_product_is_refused(self) -> None:
        with self.assertRaises(ProductNotFoundError):
            self.acme.update_product("999", "X", "Y")

    def test_failed_write_keeps_old_values(self) -> None:
        workspace = self.start(RefusingRepository).workspaces[0]
        with self.assertRaises(PersistenceError):
            workspace.update_product("001", "X", "Y")
        product = workspace.find_product("001")
        self.assertEqual((product.name, product.category), ("Pen", "Office"))

    def test_row_removed_by_another_copy_is_reported_and_nothing_changes(self) -> None:
        db = raw_connection(self.path)
        db.execute("DELETE FROM product WHERE code = '003'")
        db.close()
        with self.assertRaises(ConcurrentChangeError):
            self.acme.update_product("003", "X", None)
        self.assertEqual(self.acme.find_product("003").name, "Clip")


class DeleteProductTests(MaintenanceTestCase):
    def test_unsold_product_is_deleted_from_memory_and_database(self) -> None:
        self.acme.delete_product("003")
        self.assertIsNone(self.acme.find_product("003"))
        self.assertEqual([p.id for p in self.reopened().workspaces[0].products], ["001", "002"])

    def test_sold_product_is_refused_with_the_sale_count(self) -> None:
        for product_id, count in (("001", 2), ("002", 1)):
            with self.subTest(product_id=product_id):
                with self.assertRaises(ProductInUseError) as caught:
                    self.acme.delete_product(product_id)
                self.assertEqual(caught.exception.sale_count, count)
                self.assertIn(f"{count} sale(s)", str(caught.exception))
        self.assertEqual(row_counts(self.path)["product"], 3)

    def test_unknown_product_is_refused(self) -> None:
        with self.assertRaises(ProductNotFoundError) as caught:
            self.acme.delete_product(" 999 ")
        self.assertEqual(caught.exception.product_id, "999")

    def test_product_is_deletable_after_its_sales_are_deleted(self) -> None:
        self.acme.delete_sale("S1")
        self.acme.delete_product("002")
        self.assertEqual(row_counts(self.path)["product"], 2)

    def test_failed_write_keeps_the_product(self) -> None:
        workspace = self.start(RefusingRepository).workspaces[0]
        with self.assertRaises(PersistenceError):
            workspace.delete_product("003")
        self.assertIsNotNone(workspace.find_product("003"))


class DeleteSaleTests(MaintenanceTestCase):
    def test_sale_and_items_are_removed_from_memory_and_database(self) -> None:
        deleted = self.acme.delete_sale(" S1 ")
        self.assertEqual(deleted.id, "S1")
        self.assertEqual([s.id for s in self.acme.sales.sales], ["S2"])
        self.assertEqual(
            row_counts(self.path), {"company": 1, "product": 3, "sale": 1, "sale_item": 1}
        )
        self.assertEqual([s.id for s in self.reopened().workspaces[0].sales.sales], ["S2"])

    def test_unknown_sale_is_refused(self) -> None:
        with self.assertRaises(SaleNotFoundError):
            self.acme.delete_sale("S9")

    def test_order_after_delete_and_add_matches_after_reopen(self) -> None:
        self.acme.delete_sale("S1")
        self.acme.record_sale("S1", datetime(2025, 12, 31, 10), [item("002")])
        self.acme.record_sale("S0", datetime(2026, 2, 1, 10), [item("003")])
        expected = ["S2", "S1", "S0"]
        self.assertEqual([s.id for s in self.acme.sales.sales], expected)
        self.assertEqual([s.id for s in self.reopened().workspaces[0].sales.sales], expected)

    def test_failed_write_keeps_the_sale(self) -> None:
        workspace = self.start(RefusingRepository).workspaces[0]
        with self.assertRaises(PersistenceError):
            workspace.delete_sale("S1")
        self.assertEqual([s.id for s in workspace.sales.sales], ["S1", "S2"])

    def test_sale_removed_by_another_copy_is_reported(self) -> None:
        db = raw_connection(self.path)
        db.execute("DELETE FROM sale WHERE code = 'S2'")
        db.close()
        with self.assertRaises(ConcurrentChangeError):
            self.acme.delete_sale("S2")
        self.assertEqual(len(self.acme.sales.sales), 2)

    def test_list_sales_uses_the_selection(self) -> None:
        self.session.set_period(datetime(2026, 1, 2).date(), datetime(2026, 1, 2).date())
        selected = self.acme.list_sales(self.session.selected_sales())
        self.assertEqual([s.id for s in selected], ["S2"])
        self.assertEqual([s.id for s in self.acme.list_sales()], ["S1", "S2"])


class InMemoryMaintenanceTests(unittest.TestCase):
    """Without a repository the same use cases work in memory (level 2 sessions)."""

    def test_edit_and_delete_without_database(self) -> None:
        session = SalesSession()
        workspace = session.create_company("Acme", "Retail")
        workspace.import_sales(FIXTURES / "valid_sales.csv")
        session.update_company("Acme 2", None)
        sale = workspace.sales.sales[0]
        workspace.delete_sale(sale.id)
        self.assertEqual(session.current.company.name, "Acme 2")
        self.assertNotIn(sale, workspace.sales.sales)


if __name__ == "__main__":
    unittest.main()
