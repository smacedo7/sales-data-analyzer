import unittest
from datetime import datetime
from decimal import Decimal

from sales_data_analyzer.domain.company import Company
from sales_data_analyzer.domain.product import Product
from sales_data_analyzer.domain.sale import Sale


class SaleTests(unittest.TestCase):
    def setUp(self):
        self.company = Company("Store", "Retail")
        self.product = Product("P1", self.company, "Coffee", "Drink")
        self.sale = Sale(" S1 ", self.company, datetime(2026, 1, 1))

    def test_identity_empty_totals_and_read_only_fields(self):
        self.assertEqual(self.sale.id, "S1")
        self.assertIs(self.sale.company, self.company)
        self.assertEqual(self.sale.items, ())
        for method in (self.sale.calculate_total, self.sale.calculate_cost):
            self.assertEqual(method(), Decimal("0"))
            self.assertIsInstance(method(), Decimal)
        for field in ("id", "company", "date_time", "items"):
            with self.assertRaises(AttributeError):
                setattr(self.sale, field, getattr(self.sale, field))

    def test_owned_items_snapshot_and_exact_totals(self):
        snapshot = self.sale.items
        other = Sale("S2", self.company, self.sale.date_time)
        for sale in (self.sale, other):
            sale.add_item(self.product, 3, Decimal("0.10"), Decimal("0.04"))
        self.assertIsNot(self.sale.items[0], other.items[0])
        self.sale.add_item(self.product, 2, Decimal("0.20"), Decimal("0.05"))
        self.assertEqual(snapshot, ())
        self.assertEqual(self.sale.calculate_total(), Decimal("0.70"))
        self.assertEqual(self.sale.calculate_cost(), Decimal("0.22"))

    def test_invalid_constructor(self):
        for field, value, error in (("id", " ", ValueError), ("id", 1, TypeError),
                                    ("company", None, TypeError), ("date_time", "2026", TypeError)):
            args = dict(id="S1", company=self.company, date_time=datetime(2026, 1, 1))
            args[field] = value
            with self.subTest(field=field), self.assertRaises(error):
                Sale(**args)

    def test_failed_addition_preserves_items(self):
        foreign = Product("P2", Company("Store", "Retail"), "Tea", "Drink")
        for overrides, error in ((dict(product=foreign), ValueError),
                                 (dict(product=None), TypeError), (dict(quantity=True), TypeError),
                                 (dict(quantity=0), ValueError), (dict(unit_price=0.1), TypeError),
                                 (dict(unit_cost=Decimal("NaN")), ValueError)):
            args = dict(product=self.product, quantity=1, unit_price=Decimal("1"), unit_cost=Decimal("0"))
            args.update(overrides)
            with self.subTest(overrides=overrides), self.assertRaises(error):
                self.sale.add_item(**args)
            self.assertEqual(self.sale.items, ())
