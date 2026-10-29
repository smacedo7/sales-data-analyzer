"""Application use cases over a repository: contract types, persistence and atomicity."""

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import sqlite3
import tempfile
import unittest

from sales_data_analyzer.analysis import FinancialAnalysis
from sales_data_analyzer.application import (
    ApplicationError,
    CatalogConflictError,
    ConcurrentChangeError,
    DuplicateSaleError,
    ItemInput,
    PersistenceError,
    SalesRepository,
    SalesSession,
    StorageLimitError,
    StoredCompany,
    TimestampAwarenessError,
)
from sales_data_analyzer.domain.company import Company
from sales_data_analyzer.domain.sales_dataset import SalesDataset
from sales_data_analyzer.importing import ImportValidationError
from sales_data_analyzer.persistence import SQLiteSalesRepository

from support.databases import row_counts, temporary_database

FIXTURES = Path(__file__).parent / "fixtures"


class ContractTypeTests(unittest.TestCase):
    """Repository interface and storage errors (contracts/application-api.md)."""

    def test_repository_is_abstract(self) -> None:
        with self.assertRaises(TypeError):
            SalesRepository()  # type: ignore[abstract]

    def test_stored_company_is_frozen(self) -> None:
        company = Company("Acme", "Retail")
        stored = StoredCompany(company, (), SalesDataset(company))
        with self.assertRaises(FrozenInstanceError):
            stored.products = ()  # type: ignore[misc]

    def test_storage_errors_are_application_errors_with_safe_messages(self) -> None:
        for error in (PersistenceError(), ConcurrentChangeError(), StorageLimitError()):
            with self.subTest(error=type(error).__name__):
                self.assertIsInstance(error, ApplicationError)
                self.assertNotIn("/", str(error))
        self.assertIsInstance(ConcurrentChangeError(), PersistenceError)
        self.assertEqual(str(PersistenceError()), "the database could not be updated")


def snapshot(session: SalesSession) -> tuple:
    """Observable in-memory state of every company."""
    return tuple(
        (
            w.company.name,
            w.products,
            w.sales.sales,
            tuple(len(sale.items) for sale in w.sales.sales),
        )
        for w in session.workspaces
    )


def describe(session: SalesSession) -> tuple:
    """Comparable description of all data, independent of object identity."""
    return tuple(
        (
            w.company.name,
            w.company.sector,
            tuple((p.id, p.name, p.category) for p in w.products),
            tuple(
                (
                    sale.id,
                    sale.date_time,
                    tuple(
                        (i.product.id, i.quantity, i.unit_price, i.unit_cost) for i in sale.items
                    ),
                )
                for sale in w.sales.sales
            ),
        )
        for w in session.workspaces
    )


class FailOnItems(SQLiteSalesRepository):
    """Repository whose N-th item insertion fails, to prove rollback (research R4)."""

    fail_at = 1

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.calls = 0

    def _insert_items(self, *args: object, **kwargs: object) -> None:
        self.calls += 1
        if self.calls == self.fail_at:
            raise sqlite3.OperationalError("disk I/O error")
        super()._insert_items(*args, **kwargs)


class PersistentSessionTestCase(unittest.TestCase):
    """Sessions over a temporary database, reopened like a program restart."""

    repository_class: type[SQLiteSalesRepository] = SQLiteSalesRepository

    def setUp(self) -> None:
        context = temporary_database()
        self.path = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
        self.session = self.start()

    def start(self, repository_class: type[SQLiteSalesRepository] | None = None) -> SalesSession:
        """Open the database and load a new session from it."""
        repository = (repository_class or self.repository_class).open(self.path)
        self.addCleanup(repository.close)
        return SalesSession.open(repository)


class SurviveRestartTests(PersistentSessionTestCase):
    """User story 1: data survives closing the program (FR-001 to FR-007, SC-001)."""

    def fill(self) -> None:
        """Create two companies with catalogs, manual sales and an import."""
        acme = self.session.create_company("Acme", "Retail")
        acme.register_product("001", "Pen", "Office")
        acme.record_sale(
            "S1",
            datetime(2026, 1, 1, 9, 30, 0, 250000),
            [ItemInput("001", 2, Decimal("10.50"), Decimal("4.25"))],
        )
        acme.import_sales(FIXTURES / "valid_sales.csv")
        beta = self.session.create_company("Beta", "Food")
        beta.register_product("001", "Bread", "Bakery")
        beta.record_sale(
            "S1",
            datetime(2026, 1, 1, 12, tzinfo=timezone.utc),
            [ItemInput("001", 1, Decimal("0.1"), Decimal("1234567890.123456789"))],
        )

    def test_reopened_session_equals_the_original(self) -> None:
        self.fill()
        reopened = self.start()
        self.assertEqual(describe(reopened), describe(self.session))
        self.assertIsNone(reopened.current)
        for before, after in zip(self.session.workspaces, reopened.workspaces, strict=True):
            self.assertEqual(
                FinancialAnalysis().run(after.sales).financial,
                FinancialAnalysis().run(before.sales).financial,
            )

    def test_reopened_items_share_catalog_products(self) -> None:
        self.fill()
        for workspace in self.start().workspaces:
            for sale in workspace.sales.sales:
                for item in sale.items:
                    self.assertIs(item.product, workspace.find_product(item.product.id))

    def test_reopened_session_keeps_working_and_never_duplicates(self) -> None:
        self.fill()
        reopened = self.start()
        acme = reopened.select_company(1)
        with self.assertRaises(DuplicateSaleError):
            acme.import_sales(FIXTURES / "valid_sales.csv")
        acme.register_product("002", "Ink", "Office")
        self.start()
        third = self.start()
        self.assertEqual(describe(third), describe(reopened))
        self.assertEqual(row_counts(self.path)["company"], 2)

    def test_company_names_stay_unique_after_restart(self) -> None:
        self.session.create_company("Acme", "Retail")
        reopened = self.start()
        with self.assertRaises(ApplicationError):
            reopened.create_company(" ACME ", "Other")
        self.assertEqual(row_counts(self.path)["company"], 1)

    def test_memory_session_is_unchanged_level_two_behavior(self) -> None:
        session = SalesSession()
        self.assertIsNone(session.repository)
        session.create_company("Acme", "Retail").register_product("001", "Pen", "Office")
        self.assertEqual(row_counts(self.path)["company"], 0)


class AllOrNothingTests(PersistentSessionTestCase):
    """User story 2: refused or failed writes change nothing (FR-012 to FR-014, SC-003)."""

    def setUp(self) -> None:
        super().setUp()
        self.acme = self.session.create_company("Acme", "Retail")
        self.acme.register_product("001", "Pen", "Office")
        self.acme.import_sales(FIXTURES / "valid_sales.csv")

    def assert_unchanged(self, action, error: type[Exception]) -> None:
        """Run action, expect error, and prove memory and database are unchanged."""
        counts, memory = row_counts(self.path), snapshot(self.session)
        with self.assertRaises(error):
            action()
        self.assertEqual(row_counts(self.path), counts)
        self.assertEqual(snapshot(self.session), memory)
        self.assertEqual(describe(self.start()), describe(self.session))

    def write_csv(self, text: str) -> Path:
        """Write a temporary CSV file and return its path."""
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: [p.unlink() for p in folder.iterdir()] and folder.rmdir())
        path = folder / "sales.csv"
        path.write_text(text, encoding="utf-8")
        return path

    def test_valid_import_is_stored(self) -> None:
        self.assertEqual(
            row_counts(self.path), {"company": 1, "product": 3, "sale": 2, "sale_item": 3}
        )

    def test_refused_imports_store_nothing(self) -> None:
        header = "sale_id,date_time,product_id,product,category,quantity,unit_price,unit_cost\n"
        cases = {
            "invalid line": (FIXTURES / "invalid_sales.csv", ImportValidationError),
            "duplicate sale": (FIXTURES / "valid_sales.csv", DuplicateSaleError),
            "catalog conflict": (
                self.write_csv(header + "X1,2026-02-01T10:00:00,001,Pencil,Office,1,1.00,0.50\n"),
                CatalogConflictError,
            ),
            "mixed awareness": (FIXTURES / "aware_sales.csv", TimestampAwarenessError),
            "quantity too large": (
                self.write_csv(header + f"X2,2026-02-01T10:00:00,001,Pen,Office,{2**63},1,1\n"),
                StorageLimitError,
            ),
        }
        for name, (path, error) in cases.items():
            with self.subTest(case=name):
                self.assert_unchanged(lambda path=path: self.acme.import_sales(path), error)

    def test_failure_in_the_middle_of_an_import_rolls_back(self) -> None:
        session = self.start(type("FailThird", (FailOnItems,), {"fail_at": 3}))
        acme = session.select_company(1)
        header = "sale_id,date_time,product_id,product,category,quantity,unit_price,unit_cost\n"
        rows = "".join(
            f"N{n},2026-03-0{n}T10:00:00,{n:03d}9,New {n},Office,1,1.00,0.50\n" for n in range(1, 6)
        )
        path = self.write_csv(header + rows)
        self.session = session
        self.assert_unchanged(lambda: acme.import_sales(path), PersistenceError)

    def test_failed_manual_sale_and_product_change_nothing(self) -> None:
        session = self.start(FailOnItems)
        acme = session.select_company(1)
        self.session = session
        item = [ItemInput("001", 1, Decimal("1"), Decimal("1"))]
        self.assert_unchanged(
            lambda: acme.record_sale("M1", datetime(2026, 4, 1), item), PersistenceError
        )
        too_large = [ItemInput("001", 2**63, Decimal("1"), Decimal("1"))]
        self.assert_unchanged(
            lambda: acme.record_sale("M2", datetime(2026, 4, 1), too_large), StorageLimitError
        )

    def test_failed_product_and_company_writes_change_nothing(self) -> None:
        holder = sqlite3.connect(self.path, autocommit=True, timeout=0)
        self.addCleanup(holder.close)
        holder.execute("BEGIN IMMEDIATE")
        try:
            counts, memory = snapshot(self.session), self.acme.products
            with self.assertRaises(PersistenceError):
                self.acme.register_product("002", "Ink", "Office")
            with self.assertRaises(PersistenceError):
                self.session.create_company("Beta", "Food")
            self.assertEqual(self.acme.products, memory)
            self.assertEqual(snapshot(self.session), counts)
        finally:
            holder.execute("ROLLBACK")
        self.assertIsNone(self.acme.find_product("002"))


if __name__ == "__main__":
    unittest.main()
