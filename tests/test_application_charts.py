"""Chart values assembled by the session for every interface (level 4 shared rules)."""

from datetime import date, timedelta
from decimal import Decimal
import unittest

from sales_data_analyzer.application import (
    ChartData,
    InsufficientHistoryError,
    NoCompanySelectedError,
    NoSalesInSelectionError,
    ProductRevenue,
    SalesSession,
)

from support.sessions import START, daily_session


class TopProductsTests(unittest.TestCase):
    def test_ranking_order_names_and_exact_revenue(self) -> None:
        session = daily_session(3)
        rows = session.top_products()
        # P1: 10 + 11 + 12 = 33; P2: 2 x 3.25 on days 0 and 2 = 13.00
        self.assertEqual(
            rows,
            (
                ProductRevenue("P1", "Pen", Decimal("33")),
                ProductRevenue("P2", "Ink", Decimal("13.00")),
            ),
        )
        self.assertEqual(rows[0].label, "P1 Pen")

    def test_limit_and_follows_the_selection(self) -> None:
        session = daily_session(3)
        self.assertEqual(len(session.top_products(limit=1)), 1)
        session.set_period(START + timedelta(days=1), START + timedelta(days=1))
        self.assertEqual(session.top_products(), (ProductRevenue("P1", "Pen", Decimal("11")),))

    def test_invalid_limit_and_no_company(self) -> None:
        session = daily_session(1)
        with self.assertRaises(ValueError):
            session.top_products(limit=0)
        with self.assertRaises(TypeError):
            session.top_products(limit=True)
        with self.assertRaises(NoCompanySelectedError):
            SalesSession().top_products()


class ChartDataTests(unittest.TestCase):
    def test_values_match_the_session_services(self) -> None:
        session = daily_session(21)
        data = session.chart_data()
        self.assertIsInstance(data, ChartData)
        self.assertEqual(data.title, "Acme - all data")
        self.assertEqual(
            data.daily, tuple((r.start, r.revenue) for r in session.sales_over_time("day").rows)
        )
        self.assertEqual(
            data.monthly, tuple((r.label, r.revenue) for r in session.sales_over_time("month").rows)
        )
        self.assertEqual(data.top_products, session.top_products())
        comparison = session.compare_forecasts()
        self.assertEqual(data.forecast, tuple((p.day, p.revenue) for p in comparison.future))
        self.assertEqual(data.forecast_title, comparison.chosen_title)
        self.assertIsNone(data.forecast_refusal)

    def test_short_history_keeps_the_refusal_instead_of_raising(self) -> None:
        data = daily_session(5).chart_data()
        self.assertEqual(data.forecast, ())
        self.assertIsNone(data.forecast_title)
        self.assertIsInstance(data.forecast_refusal, InsufficientHistoryError)
        self.assertIsNone(data.forecast_refusal.__traceback__)
        self.assertEqual(len(data.daily), 5)

    def test_missing_days_refusal_is_kept(self) -> None:
        data = daily_session(21, skip=(4,)).chart_data()
        self.assertEqual(data.forecast, ())
        self.assertIsInstance(data.forecast_refusal, ValueError)
        self.assertNotIn(START + timedelta(days=4), [day for day, _ in data.daily])

    def test_empty_selection_is_refused(self) -> None:
        session = daily_session(3)
        session.set_period(date(2025, 1, 1), date(2025, 1, 2))
        with self.assertRaises(NoSalesInSelectionError):
            session.chart_data()
        self.assertIn("2025-01-01 to 2025-01-02", session.selection.describe())


if __name__ == "__main__":
    unittest.main()
