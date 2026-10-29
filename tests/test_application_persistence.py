"""Application use cases over a repository: contract types, persistence and atomicity."""

from dataclasses import FrozenInstanceError
import unittest

from sales_data_analyzer.application import (
    ApplicationError,
    ConcurrentChangeError,
    PersistenceError,
    SalesRepository,
    StorageLimitError,
    StoredCompany,
)
from sales_data_analyzer.domain.company import Company
from sales_data_analyzer.domain.sales_dataset import SalesDataset


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


if __name__ == "__main__":
    unittest.main()
