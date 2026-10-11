"""Workspace catalog, CSV import policies and manual sales."""

from decimal import Decimal
from pathlib import Path
import unittest

from sales_data_analyzer.application import (
    CatalogConflictError,
    DuplicateProductError,
    DuplicateSaleError,
    TimestampAwarenessError,
)
from sales_data_analyzer.application.workspace import CompanyWorkspace, ImportSummary
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
