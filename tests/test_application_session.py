"""Session use cases: companies, selection, analyses and forecast."""

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import unittest

from sales_data_analyzer.analysis import FinancialAnalysis
from sales_data_analyzer.application import (
    CompanyNotFoundError,
    DuplicateCompanyError,
    InvalidPeriodError,
    NoCompanySelectedError,
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


FIXTURES = Path(__file__).parent / "fixtures"


class SelectionTests(unittest.TestCase):
    """Inclusive periods over naive and aware data (FR-019)."""

    def setUp(self) -> None:
        self.session = SalesSession()
        self.session.create_company("Shop", "Retail").import_sales(FIXTURES / "valid_sales.csv")

    def test_all_data_by_default(self) -> None:
        self.assertTrue(self.session.selection.is_all)
        self.assertEqual(self.session.selection.describe(), "all data")
        self.assertEqual(len(self.session.selected_sales().sales), 2)

    def test_inclusive_single_day(self) -> None:
        self.session.set_period(date(2026, 1, 2), date(2026, 1, 2))
        self.assertEqual(self.session.selection.describe(), "2026-01-02 to 2026-01-02")
        self.assertEqual([s.id for s in self.session.selected_sales().sales], ["002"])
        self.assertEqual(self.session.run_financial_analysis().financial.revenue, Decimal("5.00"))

    def test_empty_period_and_clear(self) -> None:
        self.session.set_period(date(2025, 1, 1), date(2025, 1, 31))
        result = self.session.run_financial_analysis().financial
        self.assertEqual((result.revenue, result.gross_margin), (Decimal(0), None))
        self.session.clear_period()
        self.assertEqual(len(self.session.selected_sales().sales), 2)

    def test_invalid_period_keeps_previous_selection(self) -> None:
        self.session.set_period(date(2026, 1, 1), date(2026, 1, 1))
        with self.assertRaises(InvalidPeriodError):
            self.session.set_period(date(2026, 1, 3), date(2026, 1, 2))
        with self.assertRaises(InvalidPeriodError):
            self.session.set_period(date(2026, 1, 3), date.max)
        with self.assertRaises(TypeError):
            self.session.set_period(datetime(2026, 1, 1), datetime(2026, 1, 2))
        self.assertEqual(self.session.selection.start, date(2026, 1, 1))

    def test_company_change_resets_selection(self) -> None:
        self.session.set_period(date(2026, 1, 1), date(2026, 1, 1))
        self.session.create_company("Other", "Retail")
        self.assertTrue(self.session.selection.is_all)

    def test_aware_data_uses_utc_days(self) -> None:
        session = SalesSession()
        session.create_company("Aware", "Retail").import_sales(FIXTURES / "aware_sales.csv")
        self.assertTrue(session.data_is_aware())
        session.set_period(date(2026, 1, 3), date(2026, 1, 3))
        self.assertEqual(len(session.selected_sales().sales), 1)
        self.assertFalse(self.session.data_is_aware())

    def test_requires_company(self) -> None:
        empty = SalesSession()
        for call in (
            empty.selected_sales,
            empty.clear_period,
            empty.run_financial_analysis,
            empty.run_product_analysis,
        ):
            with self.subTest(call=call.__name__), self.assertRaises(NoCompanySelectedError):
                call()


class AnalysisTests(unittest.TestCase):
    """Analyses delegate to the existing level 1 classes (FR-020, FR-021)."""

    def test_matches_direct_analysis(self) -> None:
        session = SalesSession()
        workspace = session.create_company("Shop", "Retail")
        workspace.import_sales(FIXTURES / "valid_sales.csv")
        financial = session.run_financial_analysis()
        self.assertEqual(financial, FinancialAnalysis().run(workspace.sales))
        self.assertEqual(financial.financial.gross_profit, Decimal("27.20"))
        products = session.run_product_analysis()
        self.assertEqual(products.quantity_ranking, ("007", "008"))
