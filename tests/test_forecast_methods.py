"""User story 5: each forecast candidate on hand-made series (research R8)."""

from datetime import date, datetime, timedelta
from decimal import Decimal
import unittest

from sales_data_analyzer.domain.company import Company
from sales_data_analyzer.domain.product import Product
from sales_data_analyzer.domain.sale import Sale
from sales_data_analyzer.domain.sales_dataset import SalesDataset
from sales_data_analyzer.forecasting import (
    DEFAULT_METHODS,
    ConstantRevenueError,
    DailyRevenue,
    ForecastMethod,
    LastValueBaseline,
    LinearTrendModel,
    MovingAverageBaseline,
    RevenueForecaster,
    SeasonalNaiveBaseline,
    WeekdayTrendModel,
)

START = date(2026, 1, 5)  # a Monday


def series(values, start: date = START) -> tuple[DailyRevenue, ...]:
    """Return consecutive daily rows with the given revenue values."""
    return tuple(
        DailyRevenue(start + timedelta(days=i), Decimal(str(v))) for i, v in enumerate(values)
    )


def following(rows, count: int) -> list[date]:
    """Return the count days after the last row."""
    return [rows[-1].day + timedelta(days=i) for i in range(1, count + 1)]


class BaselineTests(unittest.TestCase):
    def test_last_value(self) -> None:
        rows = series([1, 2, 3])
        self.assertEqual(LastValueBaseline().predict(rows, following(rows, 2)), (3.0, 3.0))

    def test_moving_average_uses_the_last_window(self) -> None:
        rows = series([100, 1, 2, 3, 4, 5, 6, 7])
        self.assertEqual(MovingAverageBaseline(7).predict(rows, following(rows, 3)), (4.0,) * 3)

    def test_same_weekday_repeats_for_horizons_above_seven(self) -> None:
        rows = series(range(14))
        days = following(rows, 9)
        expected = (7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 7.0, 8.0)
        self.assertEqual(SeasonalNaiveBaseline().predict(rows, days), expected)

    def test_minimum_training_days(self) -> None:
        cases = (
            (LastValueBaseline(), 1),
            (MovingAverageBaseline(7), 7),
            (SeasonalNaiveBaseline(), 14),
            (LinearTrendModel(), 5),
            (WeekdayTrendModel(), 28),
        )
        for method, minimum in cases:
            with self.subTest(method=method.key):
                self.assertEqual(method.min_training_days, minimum)
                rows = series(range(1, minimum))
                with self.assertRaises(ValueError):
                    method.predict(rows, following(series(range(1, 2)), 1))

    def test_default_order_and_kinds(self) -> None:
        self.assertEqual(
            [m.key for m in DEFAULT_METHODS],
            ["last_value", "moving_average_7", "same_weekday", "linear_trend", "weekday_trend"],
        )
        self.assertEqual([m.kind for m in DEFAULT_METHODS], ["baseline"] * 3 + ["model"] * 2)
        for method in DEFAULT_METHODS:
            self.assertIsInstance(method, ForecastMethod)
            if method.kind == "baseline":
                self.assertIsNone(method.fit_summary(series(range(1, 40))))

    def test_invalid_parameters(self) -> None:
        with self.assertRaises(ValueError):
            MovingAverageBaseline(0)
        with self.assertRaises(ValueError):
            SeasonalNaiveBaseline(5)


class RegressionTests(unittest.TestCase):
    def test_linear_trend_matches_the_level_two_forecaster(self) -> None:
        values = [10, 12, 11, 15, 14, 18, 17, 21, 20]
        company = Company("Acme", "Retail")
        product = Product("001", company, "Pen", "Office")
        data = SalesDataset(company)
        for i, value in enumerate(values):
            sale = Sale(f"S{i}", company, datetime(2026, 1, 5 + i, 10))
            sale.add_item(product, 1, Decimal(value), Decimal(0))
            data.add_sale(sale)
        level_two = RevenueForecaster().forecast(data, horizon=3, test_days=2)
        rows = series(values)
        estimates = LinearTrendModel().predict(rows, following(rows, 3))
        for ours, theirs in zip(estimates, level_two.future, strict=True):
            self.assertAlmostEqual(ours, theirs.revenue, places=9)

    def test_linear_trend_summary(self) -> None:
        summary = LinearTrendModel().fit_summary(series([5, 7, 9, 11, 13]))
        self.assertAlmostEqual(summary.trend_per_day, 2.0)
        self.assertIsNone(summary.weekday_effects)

    def test_weekday_model_recovers_known_effects(self) -> None:
        effects = [0, 5, -3, 0, 10, 40, -20]
        values = [100 + 2 * i + effects[i % 7] for i in range(35)]
        rows = series(values)
        summary = WeekdayTrendModel().fit_summary(rows)
        self.assertAlmostEqual(summary.trend_per_day, 2.0, places=6)
        for fitted, expected in zip(summary.weekday_effects, effects[1:], strict=True):
            self.assertAlmostEqual(fitted, expected, places=6)
        estimates = WeekdayTrendModel().predict(rows, following(rows, 7))
        self.assertAlmostEqual(estimates[0], 100 + 2 * 35, places=6)  # Monday
        self.assertAlmostEqual(estimates[5], 100 + 2 * 40 + 40, places=6)  # Saturday

    def test_constant_revenue_is_refused(self) -> None:
        for method in (LinearTrendModel(), WeekdayTrendModel()):
            with self.subTest(method=method.key), self.assertRaises(ConstantRevenueError):
                method.predict(series([3] * 30), [date(2026, 3, 1)])


if __name__ == "__main__":
    unittest.main()
