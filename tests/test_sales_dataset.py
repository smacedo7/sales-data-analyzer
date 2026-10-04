import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sales_data_analyzer.domain.company import Company
from sales_data_analyzer.domain.product import Product
from sales_data_analyzer.domain.sale import Sale
from sales_data_analyzer.domain.sales_dataset import SalesDataset


class SalesDatasetTests(unittest.TestCase):
    def setUp(self):
        self.company = Company("Store", "Retail")
        self.product = Product("P1", self.company, "Coffee", "Drinks")
        self.dataset = SalesDataset(self.company)
        self.start = datetime(2026, 1, 1)

    def make_sale(self, id="S1", date_time=None):
        sale = Sale(id, self.company, date_time or self.start)
        sale.add_item(self.product, 1, Decimal("1"), Decimal("0.5"))
        return sale

    def test_company_and_collection_are_read_only(self):
        with self.assertRaises(TypeError):
            SalesDataset(None)
        self.assertIs(self.dataset.company, self.company)
        for field in ("company", "sales"):
            with self.assertRaises(AttributeError):
                setattr(self.dataset, field, None)
        snapshot = self.dataset.sales
        self.dataset.add_sale(self.make_sale())
        self.assertEqual(snapshot, ())

    def test_invalid_additions_are_atomic(self):
        sale = self.make_sale()
        self.dataset.add_sale(sale)
        foreign = Sale("S2", Company("Store", "Retail"), self.start)
        empty = Sale("S3", self.company, self.start)
        for value, error in ((None, TypeError), (foreign, ValueError), (empty, ValueError),
                             (sale, ValueError), (self.make_sale(" S1 "), ValueError),
                             (self.make_sale("S4", self.start.replace(tzinfo=timezone.utc)), ValueError)):
            with self.subTest(value=value), self.assertRaises(error):
                self.dataset.add_sale(value)
            self.assertEqual(self.dataset.sales, (sale,))

    def test_half_open_filter_order_and_shared_mutation(self):
        end = self.start + timedelta(days=1)
        before = self.make_sale("before", self.start - timedelta(seconds=1))
        first = self.make_sale("first", self.start)
        middle = self.make_sale("middle", self.start + timedelta(hours=12))
        last = self.make_sale("last", end)
        for sale in (middle, before, first, last):
            self.dataset.add_sale(sale)
        filtered = self.dataset.filter_period(self.start, end)
        self.assertIsNot(filtered, self.dataset)
        self.assertIs(filtered.company, self.company)
        self.assertEqual(filtered.sales, (middle, first))
        self.assertIs(filtered.sales[1], first)
        first.add_item(self.product, 2, Decimal("1"), Decimal("0.5"))
        self.assertEqual(filtered.sales[1].calculate_total(), Decimal("3"))
        filtered.add_sale(self.make_sale("new"))
        self.assertEqual(len(self.dataset.sales), 4)

    def test_invalid_bounds_even_for_empty_dataset(self):
        for start, end, error in ((None, self.start, TypeError),
                                  (self.start, "tomorrow", TypeError),
                                  (self.start, self.start, ValueError),
                                  (self.start + timedelta(days=1), self.start, ValueError),
                                  (self.start, self.start.replace(tzinfo=timezone.utc), ValueError)):
            with self.subTest(start=start, end=end), self.assertRaises(error):
                self.dataset.filter_period(start, end)
        self.assertEqual(self.dataset.filter_period(self.start, self.start + timedelta(days=1)).sales, ())

    def test_aware_offsets_compare_actual_instants_and_no_matches(self):
        utc = self.start.replace(tzinfo=timezone.utc)
        local = utc.astimezone(timezone(timedelta(hours=-3)))
        sale = self.make_sale(date_time=local)
        self.dataset.add_sale(sale)
        self.assertEqual(self.dataset.filter_period(utc, utc + timedelta(seconds=1)).sales, (sale,))
        self.assertEqual(self.dataset.filter_period(utc + timedelta(days=1), utc + timedelta(days=2)).sales, ())
        with self.assertRaises(ValueError):
            self.dataset.filter_period(self.start, self.start + timedelta(days=1))
