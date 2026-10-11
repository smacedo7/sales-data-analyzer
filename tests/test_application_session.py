"""Session use cases: companies, selection, analyses and forecast."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import unittest

from sales_data_analyzer.analysis import FinancialAnalysis
from sales_data_analyzer.application import (
    CompanyNotFoundError,
    DuplicateCompanyError,
    InsufficientHistoryError,
    InvalidPeriodError,
    ItemInput,
    NoCompanySelectedError,
    NoSalesInSelectionError,
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


def _daily_session(revenues: dict[int, int], tz: timezone | None = None) -> SalesSession:
    """Session with one sale per January 2026 day; day -> revenue at price 1."""
    session = SalesSession()
    workspace = session.create_company("Shop", "Retail")
    workspace.register_product("p1", "Coffee", "Beverages")
    for day, revenue in revenues.items():
        item = ItemInput("p1", revenue, Decimal("1"), Decimal("0"))
        workspace.record_sale(f"S{day}", datetime(2026, 1, day, 1, 0, tzinfo=tz), [item])
    return session


class ForecastTests(unittest.TestCase):
    """run_forecast wraps the existing RevenueForecaster (FR-023 to FR-028)."""

    def test_fixture_matches_level_one_example(self) -> None:
        session = SalesSession()
        session.create_company("Shop", "Retail").import_sales(FIXTURES / "forecast_14_days.csv")
        result = session.run_forecast(horizon=3, test_days=3)
        self.assertEqual(len(result.training), 11)
        self.assertEqual(len(result.test), 3)
        self.assertEqual([p.day for p in result.future], [date(2026, 1, d) for d in (15, 16, 17)])
        for prediction, expected in zip(result.future, (150, 160, 170), strict=True):
            self.assertAlmostEqual(prediction.revenue, expected, places=6)
        self.assertAlmostEqual(result.model_errors.mae, 0, places=6)

    def test_defaults_give_seven_future_days(self) -> None:
        session = SalesSession()
        session.create_company("Shop", "Retail").import_sales(FIXTURES / "forecast_14_days.csv")
        result = session.run_forecast()
        self.assertEqual((len(result.training), len(result.test), len(result.future)), (12, 2, 7))

    def test_empty_selection_is_refused(self) -> None:
        session = _daily_session({1: 1, 2: 2})
        session.set_period(date(2026, 2, 1), date(2026, 2, 2))
        with self.assertRaises(NoSalesInSelectionError):
            session.run_forecast()

    def test_short_history_reports_counts(self) -> None:
        session = _daily_session({1: 1, 2: 2, 3: 3})
        with self.assertRaises(InsufficientHistoryError) as caught:
            session.run_forecast(test_days=3)
        self.assertEqual((caught.exception.available_days, caught.exception.required_days), (3, 8))

    def test_short_history_counts_calendar_span_with_gaps(self) -> None:
        session = _daily_session({1: 1, 4: 2})
        with self.assertRaises(InsufficientHistoryError) as caught:
            session.run_forecast()
        self.assertEqual((caught.exception.available_days, caught.exception.required_days), (4, 7))

    def test_missing_days_need_explicit_zero(self) -> None:
        session = _daily_session({d: d for d in range(1, 9) if d != 4})
        with self.assertRaises(ValueError) as caught:
            session.run_forecast()
        self.assertEqual(
            str(caught.exception),
            "history has missing days; explicitly select zero only for complete records",
        )
        result = session.run_forecast(missing_days="zero")
        self.assertEqual(result.training[3].revenue, Decimal(0))

    def test_constant_training_revenue_message(self) -> None:
        session = _daily_session({d: 5 for d in range(1, 8)})
        with self.assertRaises(ValueError) as caught:
            session.run_forecast()
        self.assertEqual(str(caught.exception), "training revenue must vary to learn a trend")

    def test_too_few_test_days_message(self) -> None:
        session = _daily_session({d: d for d in range(1, 8)})
        with self.assertRaises(ValueError) as caught:
            session.run_forecast(test_days=1)
        self.assertEqual(str(caught.exception), "at least two test days are required")

    def test_aware_data_grouped_by_offset(self) -> None:
        session = _daily_session({d: d for d in range(1, 8)}, tz=timezone.utc)
        utc = session.run_forecast()
        self.assertEqual(utc.training[0].day, date(2026, 1, 1))
        shifted = session.run_forecast(utc_offset=timedelta(hours=-3))
        self.assertEqual(shifted.training[0].day, date(2025, 12, 31))

    def test_naive_data_ignores_offset(self) -> None:
        session = _daily_session({d: d for d in range(1, 8)})
        result = session.run_forecast(utc_offset=timedelta(hours=-3))
        self.assertEqual(result.training[0].day, date(2026, 1, 1))
