"""Workspace catalog, CSV import policies and manual sales."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import unittest

from sales_data_analyzer.application import (
    CatalogConflictError,
    DuplicateProductError,
    DuplicateSaleError,
    EmptySaleError,
    TimestampAwarenessError,
    UnknownProductError,
)
from sales_data_analyzer.application.workspace import CompanyWorkspace, ImportSummary, ItemInput
from sales_data_analyzer.domain.company import Company
from sales_data_analyzer.importing import ImportValidationError

FIXTURES = Path(__file__).parent / "fixtures"
VALID = FIXTURES / "valid_sales.csv"


def snapshot(workspace: CompanyWorkspace) -> tuple:
    """Observable state used to prove refused operations change nothing."""
    return (
        workspace.products,
        workspace.sales.sales,
        tuple(len(sale.items) for sale in workspace.sales.sales),
    )


class CatalogTests(unittest.TestCase):
    """Register and find products (FR-006, FR-007)."""

    def setUp(self) -> None:
        self.workspace = CompanyWorkspace(Company("Shop", "Retail"))

    def test_register_and_find(self) -> None:
        coffee = self.workspace.register_product(" 007 ", "Coffee", "Beverages")
        tea = self.workspace.register_product("001", "Tea", "Beverages")
        self.assertEqual(coffee.id, "007")
        self.assertIs(coffee.company, self.workspace.company)
        self.assertEqual(self.workspace.products, (tea, coffee))
        self.assertIs(self.workspace.find_product(" 007"), coffee)
        self.assertIsNone(self.workspace.find_product("7"))

    def test_duplicate_and_invalid_products(self) -> None:
        self.workspace.register_product("007", "Coffee", "Beverages")
        before = snapshot(self.workspace)
        with self.assertRaises(DuplicateProductError):
            self.workspace.register_product(" 007 ", "Other", "X")
        with self.assertRaises(ValueError):
            self.workspace.register_product("008", " ", "X")
        self.assertEqual(snapshot(self.workspace), before)

    def test_same_id_in_two_companies(self) -> None:
        other = CompanyWorkspace(Company("Other", "Retail"))
        self.workspace.register_product("007", "Coffee", "Beverages")
        other.register_product("007", "Coffee", "Beverages")
        self.assertIsNot(self.workspace.products[0], other.products[0])

    def test_wrong_types(self) -> None:
        with self.assertRaises(TypeError):
            CompanyWorkspace("Shop")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            self.workspace.find_product(7)  # type: ignore[arg-type]


class ImportTests(unittest.TestCase):
    """Import policies (FR-011 to FR-018)."""

    def setUp(self) -> None:
        self.workspace = CompanyWorkspace(Company("Shop", "Retail"))

    def test_valid_import(self) -> None:
        summary = self.workspace.import_sales(VALID)
        self.assertEqual(summary, ImportSummary(2, 3, 2, 0))
        self.assertEqual([p.id for p in self.workspace.products], ["007", "008"])
        sale = self.workspace.sales.sales[0]
        self.assertIs(sale.company, self.workspace.company)
        self.assertEqual(sale.items[0].unit_price, Decimal("10.10"))
        self.assertEqual(sale.items[0].unit_cost, Decimal("4.05"))
        self.assertIs(sale.items[0].product, self.workspace.find_product("007"))
        self.assertEqual(
            sum(s.calculate_total() for s in self.workspace.sales.sales), Decimal("45.40")
        )

    def test_invalid_file_changes_nothing(self) -> None:
        self.workspace.import_sales(VALID)
        before = snapshot(self.workspace)
        with self.assertRaises(ImportValidationError):
            self.workspace.import_sales(FIXTURES / "invalid_sales.csv")
        with self.assertRaises(ImportValidationError):
            self.workspace.import_sales(FIXTURES / "missing.csv")
        self.assertEqual(snapshot(self.workspace), before)

    def test_repeated_import_is_refused(self) -> None:
        self.workspace.import_sales(VALID)
        before = snapshot(self.workspace)
        with self.assertRaises(DuplicateSaleError) as caught:
            self.workspace.import_sales(VALID)
        self.assertEqual(caught.exception.sale_ids, ("001", "002"))
        self.assertEqual(snapshot(self.workspace), before)

    def test_identical_catalog_product_is_reused(self) -> None:
        coffee = self.workspace.register_product("007", "Coffee, premium", "Beverages")
        summary = self.workspace.import_sales(VALID)
        self.assertEqual((summary.new_products, summary.reused_products), (1, 1))
        items = [item for sale in self.workspace.sales.sales for item in sale.items]
        self.assertTrue(all(i.product is coffee for i in items if i.product.id == "007"))

    def test_catalog_conflict_is_refused(self) -> None:
        self.workspace.register_product("007", "Coffee", "Beverages")
        before = snapshot(self.workspace)
        with self.assertRaises(CatalogConflictError) as caught:
            self.workspace.import_sales(VALID)
        self.assertEqual(caught.exception.product_ids, ("007",))
        self.assertEqual(snapshot(self.workspace), before)

    def test_category_difference_is_a_conflict(self) -> None:
        self.workspace.register_product("008", "Tea", "Infusions")
        with self.assertRaises(CatalogConflictError):
            self.workspace.import_sales(VALID)

    def test_mixing_offsets_is_refused(self) -> None:
        self.workspace.import_sales(VALID)
        before = snapshot(self.workspace)
        with self.assertRaises(TimestampAwarenessError):
            self.workspace.import_sales(FIXTURES / "aware_sales.csv")
        self.assertEqual(snapshot(self.workspace), before)

    def test_aware_import_into_empty_company(self) -> None:
        summary = self.workspace.import_sales(FIXTURES / "aware_sales.csv")
        self.assertEqual(summary.sales_added, 1)
        self.assertIsNotNone(self.workspace.sales.sales[0].date_time.utcoffset())

    def test_importer_type(self) -> None:
        with self.assertRaises(TypeError):
            self.workspace.import_sales(VALID, importer=object())  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()


class RecordSaleTests(unittest.TestCase):
    """Manual sales (FR-008 to FR-010)."""

    def setUp(self) -> None:
        self.workspace = CompanyWorkspace(Company("Shop", "Retail"))
        self.coffee = self.workspace.register_product("001", "Coffee", "Beverages")
        self.workspace.register_product("002", "Tea", "Beverages")
        self.when = datetime(2026, 1, 5, 10)
        self.items = (
            ItemInput("001", 2, Decimal("10.50"), Decimal("4.00")),
            ItemInput(" 002 ", 1, Decimal("5.00"), Decimal("2.00")),
        )

    def test_record_exact_totals(self) -> None:
        sale = self.workspace.record_sale(" S-1 ", self.when, self.items)
        self.assertEqual(sale.id, "S-1")
        self.assertEqual(sale.calculate_total(), Decimal("26.00"))
        self.assertEqual(sale.calculate_cost(), Decimal("10.00"))
        self.assertIs(sale.items[0].product, self.coffee)
        self.assertEqual(self.workspace.sales.sales, (sale,))
        self.assertTrue(self.workspace.has_sale("S-1 "))

    def test_refusals_change_nothing(self) -> None:
        self.workspace.record_sale("S-1", self.when, self.items)
        before = snapshot(self.workspace)
        cases = (
            ("S-1", self.when, self.items, DuplicateSaleError),
            ("S-2", self.when, (), EmptySaleError),
            ("S-2", self.when, (ItemInput("999", 1, Decimal(1), Decimal(1)),), UnknownProductError),
            ("S-2", self.when.replace(tzinfo=timezone.utc), self.items, TimestampAwarenessError),
            ("S-2", self.when, (ItemInput("001", 0, Decimal(1), Decimal(1)),), ValueError),
            ("S-2", self.when, (ItemInput("001", 1, Decimal(-1), Decimal(1)),), ValueError),
            ("S-2", "2026-01-05", self.items, TypeError),
            ("S-2", self.when, None, TypeError),
            (
                "S-2",
                datetime(1, 1, 1, 0, 30, tzinfo=timezone(timedelta(hours=1))),
                self.items,
                ValueError,
            ),
            (" ", self.when, self.items, ValueError),
        )
        for sale_id, when, items, error in cases:
            with self.subTest(error=error.__name__, sale_id=sale_id), self.assertRaises(error):
                self.workspace.record_sale(sale_id, when, items)
            self.assertEqual(snapshot(self.workspace), before)

    def test_items_may_be_any_iterable(self) -> None:
        sale = self.workspace.record_sale("S-1", self.when, (item for item in self.items))
        self.assertEqual(len(sale.items), 2)

    def test_duplicate_is_checked_before_items(self) -> None:
        self.workspace.record_sale("S-1", self.when, self.items)
        with self.assertRaises(DuplicateSaleError):
            self.workspace.record_sale("S-1", self.when, ())

    def test_offsets_are_normalized_to_utc(self) -> None:
        local = datetime(2026, 1, 5, 10, tzinfo=timezone(timedelta(hours=-3)))
        sale = self.workspace.record_sale("A-1", local, self.items)
        self.assertEqual(sale.date_time, datetime(2026, 1, 5, 13, tzinfo=timezone.utc))
        self.assertEqual(sale.date_time.utcoffset(), timedelta(0))

    def test_history_is_independent_of_catalog_objects(self) -> None:
        sale = self.workspace.record_sale("S-1", self.when, self.items)
        self.coffee.name = "Coffee renamed"
        self.assertEqual(sale.items[0].unit_price, Decimal("10.50"))
        self.assertEqual(sale.calculate_total(), Decimal("26.00"))
