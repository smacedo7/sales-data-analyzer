import unittest
from decimal import Decimal

from sales_data_analyzer.domain.company import Company
from sales_data_analyzer.domain.product import Product
from sales_data_analyzer.domain.sale_item import SaleItem


class ProductTests(unittest.TestCase):
    def setUp(self):
        self.company = Company("Store", "Retail")
        self.product = Product(" P001 ", self.company, " Coffee ", " Drinks ")

    def test_normalized_fields_and_company_association(self):
        self.assertEqual(self.product.id, "P001")
        self.assertEqual(self.product.name, "Coffee")
        self.assertEqual(self.product.category, "Drinks")
        self.assertIs(self.product.company, self.company)

    def test_text_validation_on_creation(self):
        for field in ("id", "name", "category"):
            for value, error in (("   ", ValueError), (None, TypeError), (1, TypeError)):
                with self.subTest(field=field, value=value):
                    args = dict(id="P001", company=self.company, name="Coffee", category="Drinks")
                    args[field] = value
                    with self.assertRaises(error):
                        Product(**args)

    def test_invalid_company(self):
        with self.assertRaises(TypeError):
            Product("P001", "Store", "Coffee", "Drinks")

    def test_updates_validate_before_replacing_existing_values(self):
        for field in ("name", "category"):
            setattr(self.product, field, " Updated ")
            self.assertEqual(getattr(self.product, field), "Updated")
            for value, error in ((" ", ValueError), (None, TypeError)):
                with self.assertRaises(error):
                    setattr(self.product, field, value)
                self.assertEqual(getattr(self.product, field), "Updated")

    def test_identity_and_owner_are_read_only(self):
        for field, value in (("id", "P002"), ("company", self.company)):
            with self.assertRaises(AttributeError):
                setattr(self.product, field, value)

    def test_shared_validation_normalizes_company_fields(self):
        company = Company(" Store ", " Retail ")
        self.assertEqual((company.name, company.sector), ("Store", "Retail"))


class SaleItemTests(unittest.TestCase):
    def setUp(self):
        self.product = Product("P001", Company("Store", "Retail"), "Coffee", "Drinks")

    def make_item(self, **overrides):
        args = dict(product=self.product, quantity=3, unit_price=Decimal("0.10"), unit_cost=Decimal("0.04"))
        args.update(overrides)
        return SaleItem(**args)

    def test_exact_totals(self):
        item = self.make_item()
        self.assertEqual(item.calculate_subtotal(), Decimal("0.30"))
        self.assertEqual(item.calculate_cost(), Decimal("0.12"))
        self.assertIs(item.product, self.product)

    def test_invalid_product(self):
        with self.assertRaises(TypeError):
            self.make_item(product="P001")

    def test_invalid_quantities(self):
        for quantity, error in ((0, ValueError), (-1, ValueError), (True, TypeError), (1.5, TypeError), ("2", TypeError)):
            with self.subTest(quantity=quantity), self.assertRaises(error):
                self.make_item(quantity=quantity)

    def test_invalid_amounts(self):
        for field in ("unit_price", "unit_cost"):
            for value in (Decimal("-1"), Decimal("NaN"), Decimal("sNaN"), Decimal("Infinity"), Decimal("-Infinity")):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    self.make_item(**{field: value})
            for value in (0.1, 1, "1.00", None, True):
                with self.subTest(field=field, value=value), self.assertRaises(TypeError):
                    self.make_item(**{field: value})

    def test_zero_amounts_and_sales_below_cost_are_allowed(self):
        free = self.make_item(unit_price=Decimal("0"), unit_cost=Decimal("0"))
        self.assertEqual(free.calculate_subtotal(), Decimal("0"))
        self.assertEqual(free.calculate_cost(), Decimal("0"))
        loss = self.make_item(unit_cost=Decimal("1"))
        self.assertGreater(loss.calculate_cost(), loss.calculate_subtotal())

    def test_historical_fields_are_read_only(self):
        item = self.make_item()
        for field in ("product", "quantity", "unit_price", "unit_cost"):
            with self.subTest(field=field), self.assertRaises(AttributeError):
                setattr(item, field, getattr(item, field))
        self.product.name = "Updated coffee"
        self.assertEqual(item.unit_price, Decimal("0.10"))
        self.assertEqual(item.unit_cost, Decimal("0.04"))


if __name__ == "__main__":
    unittest.main()
