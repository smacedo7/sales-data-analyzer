"""SQLiteSalesRepository: opening, exact round trips, ordering and rollback."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import sqlite3
import tempfile
import unittest

from sales_data_analyzer.application import (
    ConcurrentChangeError,
    PersistenceError,
    StoredCompany,
)
from sales_data_analyzer.domain.company import Company
from sales_data_analyzer.domain.product import Product
from sales_data_analyzer.domain.sale import Sale
from sales_data_analyzer.persistence import (
    CorruptDataError,
    DatabaseOpenError,
    SQLiteSalesRepository,
    default_database_path,
)

from support.databases import raw_connection, row_counts, temporary_database


def make_sale(company: Company, code: str, when: datetime, *items: tuple) -> Sale:
    """Build a sale from (product, quantity, price, cost) tuples."""
    sale = Sale(code, company, when)
    for product, quantity, price, cost in items:
        sale.add_item(product, quantity, Decimal(price), Decimal(cost))
    return sale


class RepositoryTestCase(unittest.TestCase):
    """Provide a temporary database path and reopen helper."""

    def setUp(self) -> None:
        self._context = temporary_database()
        self.path = self._context.__enter__()
        self.addCleanup(self._context.__exit__, None, None, None)

    def open(self) -> SQLiteSalesRepository:
        """Open the test database and close it at the end of the test."""
        repository = SQLiteSalesRepository.open(self.path)
        self.addCleanup(repository.close)
        return repository

    def reopen(self) -> tuple[StoredCompany, ...]:
        """Load everything through a brand-new repository, as after a restart."""
        repository = SQLiteSalesRepository.open(self.path)
        try:
            return repository.load()
        finally:
            repository.close()


class OpenTests(RepositoryTestCase):
    """Creating, recognizing and refusing database files (FR-010, FR-011)."""

    def test_new_file_and_missing_folder_are_created(self) -> None:
        self.path = self.path.parent / "nested" / "folder" / "sales.sqlite3"
        repository = self.open()
        self.assertTrue(self.path.is_file())
        self.assertEqual(repository.location, str(self.path))
        self.assertEqual(repository.load(), ())

    def test_existing_empty_file_receives_schema(self) -> None:
        self.path.write_bytes(b"")
        self.assertEqual(self.open().load(), ())
        self.assertEqual(row_counts(self.path), dict.fromkeys(row_counts(self.path), 0))

    def test_foreign_keys_are_enabled_on_program_connections(self) -> None:
        repository = self.open()
        with repository._engine.connect() as connection:
            self.assertEqual(connection.exec_driver_sql("PRAGMA foreign_keys").scalar(), 1)

    def test_text_file_is_refused_unchanged(self) -> None:
        content = "# README\n\nThis is not a database.\n".encode() * 40
        self.path.write_bytes(content)
        with self.assertRaises(DatabaseOpenError) as caught:
            SQLiteSalesRepository.open(self.path)
        self.assertIn("not a database", str(caught.exception))
        self.assertNotIn(str(self.path), str(caught.exception))
        self.assertEqual(self.path.read_bytes(), content)

    def test_other_application_database_is_refused_unchanged(self) -> None:
        connection = sqlite3.connect(self.path)
        connection.execute("CREATE TABLE notes (text TEXT)")
        connection.commit()
        connection.close()
        before = self.path.read_bytes()
        with self.assertRaises(DatabaseOpenError) as caught:
            SQLiteSalesRepository.open(self.path)
        self.assertIn("not a Sales Data Analyzer database", str(caught.exception))
        self.assertEqual(self.path.read_bytes(), before)

    def test_newer_version_is_refused(self) -> None:
        self.open().close()
        connection = raw_connection(self.path)
        connection.execute("PRAGMA user_version = 2")
        connection.close()
        with self.assertRaises(DatabaseOpenError) as caught:
            SQLiteSalesRepository.open(self.path)
        self.assertIn("newer version", str(caught.exception))

    def test_folder_path_is_refused(self) -> None:
        with self.assertRaises(DatabaseOpenError):
            SQLiteSalesRepository.open(self.path.parent)

    def test_invalid_stored_rows_stop_loading(self) -> None:
        self.open().close()
        connection = raw_connection(self.path)
        connection.execute("PRAGMA ignore_check_constraints = ON")
        connection.execute("INSERT INTO company VALUES (1, ' ', 'x', 'Retail')")
        connection.execute("INSERT INTO company VALUES (2, 'Ok', 'ok', '')")
        connection.close()
        with self.assertRaises(CorruptDataError) as caught:
            self.reopen()
        self.assertEqual((caught.exception.table, caught.exception.count), ("company", 2))
        self.assertIn("2 invalid row(s) in company", str(caught.exception))

    def test_invalid_amount_text_stops_loading(self) -> None:
        repository = self.open()
        company = Company("Acme", "Retail")
        repository.add_company(company)
        pen = Product("001", company, "Pen", "Office")
        repository.add_sales(
            company, [pen], [make_sale(company, "S1", datetime(2026, 1, 1), (pen, 1, "1", "1"))]
        )
        connection = raw_connection(self.path)
        connection.execute("PRAGMA ignore_check_constraints = ON")
        connection.execute("UPDATE sale_item SET unit_price = 'abc'")
        connection.close()
        with self.assertRaises(CorruptDataError) as caught:
            self.reopen()
        self.assertEqual(caught.exception.table, "sale_item")

    def test_failed_schema_creation_leaves_no_tables(self) -> None:
        from sales_data_analyzer.persistence import schema

        original = schema.SCHEMA_VERSION
        schema.SCHEMA_VERSION = "not a number"  # makes the last PRAGMA fail
        try:
            with self.assertRaises(DatabaseOpenError):
                SQLiteSalesRepository.open(self.path)
        finally:
            schema.SCHEMA_VERSION = original
        connection = sqlite3.connect(self.path)
        tables = connection.execute("SELECT count(*) FROM sqlite_schema").fetchone()[0]
        application_id = connection.execute("PRAGMA application_id").fetchone()[0]
        connection.close()
        self.assertEqual((tables, application_id), (0, 0))


class RoundTripTests(RepositoryTestCase):
    """Everything written reads back equal after reopening (FR-001 to FR-007, SC-002)."""

    AMOUNTS = (
        "0",
        "0.1",
        "10.50",
        "19.999",
        "0.0000000",
        "1234567890.123456789",
        "12345678901234567890.123456789",
        "0.1234567890123456789012345",
    )

    def test_exact_amounts_keep_value_and_decimal_places(self) -> None:
        repository = self.open()
        company = Company("Acme", "Retail")
        repository.add_company(company)
        pen = Product("001", company, "Pen", "Office")
        items = [(pen, 1, amount, amount) for amount in self.AMOUNTS]
        repository.add_sales(
            company, [pen], [make_sale(company, "S1", datetime(2026, 1, 1, 10), *items)]
        )
        (stored,) = self.reopen()
        loaded = stored.sales.sales[0].items
        for item, amount in zip(loaded, self.AMOUNTS, strict=True):
            with self.subTest(amount=amount):
                self.assertEqual(item.unit_price, Decimal(amount))
                self.assertEqual(item.unit_price.as_tuple(), Decimal(amount).as_tuple())
                self.assertEqual(item.unit_cost.as_tuple(), Decimal(amount).as_tuple())

    def test_negative_zero_is_stored_as_zero(self) -> None:
        repository = self.open()
        company = Company("Acme", "Retail")
        repository.add_company(company)
        pen = Product("001", company, "Pen", "Office")
        repository.add_sales(
            company, [pen], [make_sale(company, "S1", datetime(2026, 1, 1), (pen, 1, "-0", "0"))]
        )
        (stored,) = self.reopen()
        self.assertEqual(stored.sales.sales[0].items[0].unit_price, Decimal(0))

    def test_timestamps_keep_instant_kind_and_microseconds(self) -> None:
        repository = self.open()
        local, utc = Company("Local", "Retail"), Company("Utc", "Retail")
        for company in (local, utc):
            repository.add_company(company)
        cases = {
            local: datetime(2026, 3, 1, 23, 59, 59, 123456),
            utc: datetime(2026, 3, 1, 2, 0, 0, 5, tzinfo=timezone.utc),
        }
        for company, when in cases.items():
            pen = Product("001", company, "Pen", "Office")
            repository.add_sales(
                company, [pen], [make_sale(company, "S1", when, (pen, 1, "1", "1"))]
            )
        loaded = {stored.company.name: stored.sales.sales[0].date_time for stored in self.reopen()}
        self.assertEqual(loaded["Local"], cases[local])
        self.assertIsNone(loaded["Local"].utcoffset())
        self.assertEqual(loaded["Utc"], cases[utc])
        self.assertEqual(loaded["Utc"].utcoffset(), timedelta(0))

    def test_identity_order_and_company_scope(self) -> None:
        repository = self.open()
        first, second = Company("Zeta", "Retail"), Company("Alpha", "Food")
        repository.add_company(first)
        repository.add_company(second)
        catalog = {
            company: (Product("010", company, "B", "X"), Product("002", company, "A", "Y"))
            for company in (first, second)
        }
        for company, products in catalog.items():
            repository.add_sales(company, products, [])
        late, early = catalog[first]
        repository.add_sales(
            first,
            [],
            [
                make_sale(
                    first, "S9", datetime(2026, 1, 2), (late, 1, "1", "1"), (early, 2, "2", "1")
                ),
                make_sale(first, "S1", datetime(2026, 1, 1), (early, 3, "3", "1")),
            ],
        )
        stored = self.reopen()
        self.assertEqual([s.company.name for s in stored], ["Zeta", "Alpha"])
        zeta = stored[0]
        self.assertEqual([p.id for p in zeta.products], ["002", "010"])
        self.assertEqual([sale.id for sale in zeta.sales.sales], ["S9", "S1"])
        self.assertEqual([item.product.id for item in zeta.sales.sales[0].items], ["010", "002"])
        self.assertEqual(len(stored[1].products), 2)
        self.assertEqual(stored[1].sales.sales, ())
        catalog_by_id = {product.id: product for product in zeta.products}
        for sale in zeta.sales.sales:
            for item in sale.items:
                self.assertIs(item.product, catalog_by_id[item.product.id])
                self.assertIs(item.product.company, zeta.company)

    def test_reopening_twice_does_not_duplicate(self) -> None:
        repository = self.open()
        company = Company("Acme", "Retail")
        repository.add_company(company)
        pen = Product("001", company, "Pen", "Office")
        repository.add_sales(
            company, [pen], [make_sale(company, "S1", datetime(2026, 1, 1), (pen, 1, "1", "1"))]
        )
        before = row_counts(self.path)
        self.reopen()
        self.reopen()
        self.assertEqual(row_counts(self.path), before)
        self.assertEqual(before, {"company": 1, "product": 1, "sale": 1, "sale_item": 1})

    def test_company_key_uses_casefold(self) -> None:
        repository = self.open()
        repository.add_company(Company("Straße", "Retail"))
        with self.assertRaises(ConcurrentChangeError):
            repository.add_company(Company("STRASSE", "Retail"))
        self.assertEqual(row_counts(self.path)["company"], 1)

    def test_loaded_companies_accept_new_writes(self) -> None:
        repository = self.open()
        repository.add_company(Company("Acme", "Retail"))
        repository.close()
        repository = self.open()
        (stored,) = repository.load()
        repository.add_product(stored.company, Product("001", stored.company, "Pen", "Office"))
        self.assertEqual(row_counts(self.path)["product"], 1)

    def test_unknown_company_is_a_programming_error(self) -> None:
        repository = self.open()
        company = Company("Ghost", "Retail")
        with self.assertRaises(LookupError):
            repository.add_product(company, Product("001", company, "Pen", "Office"))


class FailingRepository(SQLiteSalesRepository):
    """Fails while inserting the items of the N-th sale of a write."""

    fail_at = 3

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.calls = 0

    def _insert_items(self, *args: object, **kwargs: object) -> None:
        self.calls += 1
        if self.calls == self.fail_at:
            raise sqlite3.OperationalError("disk I/O error")
        super()._insert_items(*args, **kwargs)


class RollbackTests(RepositoryTestCase):
    """A failed write stores nothing (FR-012, SC-003)."""

    def test_failure_in_third_sale_rolls_back_everything(self) -> None:
        repository = FailingRepository.open(self.path)
        self.addCleanup(repository.close)
        company = Company("Acme", "Retail")
        repository.add_company(company)
        pen = Product("001", company, "Pen", "Office")
        sales = [
            make_sale(company, f"S{n}", datetime(2026, 1, n), (pen, 1, "1", "1"))
            for n in range(1, 6)
        ]
        with self.assertRaises(PersistenceError):
            repository.add_sales(company, [pen], sales)
        self.assertEqual(
            row_counts(self.path), {"company": 1, "product": 0, "sale": 0, "sale_item": 0}
        )

    def test_quantity_out_of_range_rolls_back(self) -> None:
        repository = self.open()
        company = Company("Acme", "Retail")
        repository.add_company(company)
        pen = Product("001", company, "Pen", "Office")
        sale = make_sale(company, "S1", datetime(2026, 1, 1), (pen, 2**63, "1", "1"))
        with self.assertRaises(PersistenceError):
            repository.add_sales(company, [pen], [sale])
        self.assertEqual(row_counts(self.path)["product"], 0)

    def test_locked_database_is_reported_as_busy(self) -> None:
        repository = self.open()
        holder = sqlite3.connect(self.path, autocommit=True, timeout=0)
        self.addCleanup(holder.close)
        holder.execute("BEGIN IMMEDIATE")
        try:
            with self.assertRaises(PersistenceError) as caught:
                repository.add_company(Company("Acme", "Retail"))
        finally:
            holder.execute("ROLLBACK")
        self.assertIn("busy", str(caught.exception))
        self.assertEqual(row_counts(self.path)["company"], 0)


class DefaultPathTests(unittest.TestCase):
    """Per-user application data folder (research R6)."""

    HOME = Path(tempfile.gettempdir()) / "home"

    def test_macos(self) -> None:
        path = default_database_path(platform="darwin", environ={}, home=self.HOME)
        expected = self.HOME / "Library" / "Application Support" / "Sales Data Analyzer"
        self.assertEqual(path, expected / "sales.sqlite3")

    def test_windows(self) -> None:
        local = str(self.HOME / "AppData" / "Local")
        path = default_database_path(
            platform="win32", environ={"LOCALAPPDATA": local}, home=self.HOME
        )
        self.assertEqual(path, Path(local) / "Sales Data Analyzer" / "sales.sqlite3")
        fallback = default_database_path(platform="win32", environ={}, home=self.HOME)
        self.assertEqual(fallback.parent.parent, self.HOME / "AppData" / "Local")

    def test_other_systems(self) -> None:
        xdg = str(self.HOME / "data")
        path = default_database_path(
            platform="linux", environ={"XDG_DATA_HOME": xdg}, home=self.HOME
        )
        self.assertEqual(path, Path(xdg) / "sales-data-analyzer" / "sales.sqlite3")
        relative = default_database_path(
            platform="linux", environ={"XDG_DATA_HOME": "relative"}, home=self.HOME
        )
        self.assertEqual(relative.parent.parent, self.HOME / ".local" / "share")


if __name__ == "__main__":
    unittest.main()
