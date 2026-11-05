"""SQLite schema version 1: STRICT tables, keys and checks (data-model section 3)."""

import sqlite3
import unittest

from sales_data_analyzer.persistence import APPLICATION_ID, SCHEMA_VERSION, SQLiteSalesRepository

from support.databases import raw_connection, temporary_database


class SchemaTests(unittest.TestCase):
    """The database created by open() enforces the rules even without the program."""

    def setUp(self) -> None:
        self._context = temporary_database()
        self.path = self._context.__enter__()
        SQLiteSalesRepository.open(self.path).close()
        self.db = raw_connection(self.path)
        self.db.execute("INSERT INTO company VALUES (1, 'Acme', 'acme', 'Retail')")
        self.db.execute("INSERT INTO company VALUES (2, 'Beta', 'beta', 'Retail')")
        self.db.execute("INSERT INTO product VALUES (1, 1, '001', 'Pen', 'Office')")
        self.db.execute("INSERT INTO product VALUES (2, 2, '001', 'Pen', 'Office')")
        self.db.execute("INSERT INTO sale VALUES (1, 1, 'S1', '2026-01-01T10:00:00')")

    def tearDown(self) -> None:
        self.db.close()
        self._context.__exit__(None, None, None)

    def insert_item(self, *values: object) -> None:
        """Insert one sale_item row (sale, position, company, product, qty, price, cost)."""
        self.db.execute("INSERT INTO sale_item VALUES (?, ?, ?, ?, ?, ?, ?)", values)

    def test_identity_pragmas(self) -> None:
        self.assertEqual(self.db.execute("PRAGMA application_id").fetchone()[0], APPLICATION_ID)
        self.assertEqual(self.db.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)

    def test_tables_are_strict(self) -> None:
        rows = self.db.execute("SELECT name, strict FROM pragma_table_list WHERE schema = 'main'")
        strict = {name: flag for name, flag in rows if not name.startswith("sqlite_")}
        self.assertEqual(strict, {"company": 1, "product": 1, "sale": 1, "sale_item": 1})

    def test_valid_item_is_accepted(self) -> None:
        self.insert_item(1, 1, 1, 1, 2, "0.0000000", "4.25")
        self.assertEqual(self.db.execute("SELECT count(*) FROM sale_item").fetchone()[0], 1)

    def test_item_cannot_use_another_company_product(self) -> None:
        with self.assertRaises(sqlite3.IntegrityError):
            self.insert_item(1, 1, 1, 2, 1, "1", "1")

    def test_amount_text_must_be_plain_decimal(self) -> None:
        for amount in ("1E-7", "1.", ".5", "-1", "1.2.3", "", "abc"):
            with self.subTest(column="unit_price", amount=amount):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.insert_item(1, 1, 1, 1, 1, amount, "1")
            with self.subTest(column="unit_cost", amount=amount):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.insert_item(1, 1, 1, 1, 1, "1", amount)

    def test_item_cannot_claim_another_company_sale(self) -> None:
        with self.assertRaises(sqlite3.IntegrityError):
            self.insert_item(1, 1, 2, 2, 1, "1", "1")

    def test_timestamp_text_needs_seconds(self) -> None:
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO sale VALUES (2, 1, 'S2', '2026-01-01')")

    def test_quantity_and_position_must_be_positive(self) -> None:
        with self.assertRaises(sqlite3.IntegrityError):
            self.insert_item(1, 1, 1, 1, 0, "1", "1")
        with self.assertRaises(sqlite3.IntegrityError):
            self.insert_item(1, 0, 1, 1, 1, "1", "1")

    def test_codes_unique_per_company_and_names_by_key(self) -> None:
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO product VALUES (3, 1, '001', 'Other', 'Office')")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO company VALUES (3, 'ACME', 'acme', 'Retail')")

    def test_blank_text_is_rejected(self) -> None:
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO company VALUES (3, '  ', 'x', 'Retail')")

    def test_sold_product_cannot_be_deleted_and_sale_delete_cascades(self) -> None:
        self.insert_item(1, 1, 1, 1, 1, "1", "1")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("DELETE FROM product WHERE id = 1")
        self.db.execute("DELETE FROM sale WHERE id = 1")
        self.assertEqual(self.db.execute("SELECT count(*) FROM sale_item").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
