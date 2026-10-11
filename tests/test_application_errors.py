"""Application errors expose details as attributes and keep messages safe."""

import unittest

from sales_data_analyzer.application import (
    ApplicationError,
    CatalogConflictError,
    DuplicateSaleError,
    InsufficientHistoryError,
    NoCompanySelectedError,
    SalesSession,
)


class ApplicationErrorTests(unittest.TestCase):
    """Cover the hierarchy, attributes and message safety."""

    def test_hierarchy(self) -> None:
        self.assertTrue(issubclass(ApplicationError, ValueError))
        for error in (NoCompanySelectedError(), DuplicateSaleError(("1",))):
            self.assertIsInstance(error, ApplicationError)

    def test_ids_are_attributes_not_message_text(self) -> None:
        sales = DuplicateSaleError(("001", "SECRET-42"))
        products = CatalogConflictError(("007",))
        self.assertEqual(sales.sale_ids, ("001", "SECRET-42"))
        self.assertEqual(products.product_ids, ("007",))
        self.assertIn("2 sale ID(s)", str(sales))
        self.assertNotIn("SECRET-42", str(sales))
        self.assertNotIn("007", str(products))

    def test_history_counts(self) -> None:
        error = InsufficientHistoryError(3, 7)
        self.assertEqual((error.available_days, error.required_days), (3, 7))
        self.assertIn("3 day(s)", str(error))


class SessionSkeletonTests(unittest.TestCase):
    """A new session has no company and refuses company operations."""

    def test_empty_session(self) -> None:
        session = SalesSession()
        self.assertIsNone(session.current)
        self.assertEqual(session.workspaces, ())
        with self.assertRaises(NoCompanySelectedError):
            session.require_current()


if __name__ == "__main__":
    unittest.main()
