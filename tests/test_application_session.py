"""Session use cases: companies, selection, analyses and forecast."""

import unittest

from sales_data_analyzer.application import (
    CompanyNotFoundError,
    DuplicateCompanyError,
    SalesSession,
)


class CompanyManagementTests(unittest.TestCase):
    """Create, list and select companies (FR-002 to FR-004)."""

    def setUp(self) -> None:
        self.session = SalesSession()

    def test_create_selects_new_company(self) -> None:
        first = self.session.create_company(" Coffee Shop ", "Retail")
        self.assertIs(self.session.current, first)
        self.assertEqual(first.company.name, "Coffee Shop")
        second = self.session.create_company("Bakery", "Food")
        self.assertIs(self.session.current, second)
        self.assertEqual(self.session.workspaces, (first, second))

    def test_duplicate_name_ignores_case_and_spaces(self) -> None:
        first = self.session.create_company("Coffee Shop", "Retail")
        with self.assertRaises(DuplicateCompanyError):
            self.session.create_company(" coffee shop ", "Other")
        self.assertEqual(self.session.workspaces, (first,))
        self.assertIs(self.session.current, first)

    def test_invalid_company_values_leave_session_unchanged(self) -> None:
        with self.assertRaises(ValueError):
            self.session.create_company("  ", "Retail")
        with self.assertRaises(TypeError):
            self.session.create_company("Shop", None)  # type: ignore[arg-type]
        self.assertEqual(self.session.workspaces, ())
        self.assertIsNone(self.session.current)

    def test_select_by_one_based_index(self) -> None:
        first = self.session.create_company("A", "X")
        self.session.create_company("B", "Y")
        self.assertIs(self.session.select_company(1), first)
        self.assertIs(self.session.current, first)
        for bad in (0, 3, -1):
            with self.subTest(bad=bad), self.assertRaises(CompanyNotFoundError):
                self.session.select_company(bad)
        self.assertIs(self.session.current, first)
        with self.assertRaises(TypeError):
            self.session.select_company(True)

    def test_select_without_companies(self) -> None:
        with self.assertRaises(CompanyNotFoundError):
            self.session.select_company(1)


if __name__ == "__main__":
    unittest.main()
