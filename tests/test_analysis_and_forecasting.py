"""Accounting, identity and temporal evaluation regression tests."""
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sales_data_analyzer.analysis import Analysis, FinancialAnalysis, ProductAnalysis
from sales_data_analyzer.domain.company import Company
from sales_data_analyzer.domain.product import Product
from sales_data_analyzer.domain.sale import Sale
from sales_data_analyzer.domain.sales_dataset import SalesDataset
from sales_data_analyzer.forecasting import RevenueForecaster, daily_revenue


def dataset(values: list[int | Decimal], *, reverse: bool = False) -> SalesDataset:
    """Build one daily transaction per value, optionally in reverse input order."""
    company = Company("Synthetic", "Retail")
    result = SalesDataset(company)
    product = Product("p", company, "Product", "Test")
    indices = list(range(len(values)))
    for i in reversed(indices) if reverse else indices:
        sale = Sale(str(i), company, datetime(2026, 1, 1) + timedelta(days=i))
        sale.add_item(product, 1, Decimal(values[i]), Decimal(0))
        result.add_sale(sale)
    return result


class AnalysisTests(unittest.TestCase):
    """Verify exact arithmetic and shared polymorphic result semantics."""

    def test_exact_financial_metrics(self) -> None:
        """Historical cost and fractional prices determine exact profit and ticket."""
        data = dataset([Decimal("10.25"), Decimal("5.75")])
        data.sales[0].add_item(data.sales[0].items[0].product, 2, Decimal("2"), Decimal("3"))
        metrics = FinancialAnalysis().run(data).financial
        self.assertEqual((metrics.revenue, metrics.cost, metrics.gross_profit), (Decimal(20), Decimal(6), Decimal(14)))
        self.assertEqual(metrics.gross_margin, Decimal("0.7"))
        self.assertEqual(metrics.average_order_value, Decimal(10))

    def test_empty_and_zero(self) -> None:
        """Empty totals are zero; undefined margin and ticket remain None."""
        data = SalesDataset(Company("Empty", "Retail"))
        result = FinancialAnalysis().run(data)
        self.assertEqual(result.financial.revenue, Decimal(0))
        self.assertIsNone(result.financial.average_order_value)
        self.assertIsNone(result.financial.gross_margin)
        self.assertEqual(ProductAnalysis().run(data).products, ())
        zero = FinancialAnalysis().run(dataset([0])).financial
        self.assertIsNone(zero.gross_margin)
        self.assertEqual(zero.average_order_value, Decimal(0))

    def test_product_identity_and_tie_order(self) -> None:
        """Same-ID objects combine and ties use ID independently of insertion order."""
        data = dataset([4])
        sale = data.sales[0]
        sale.add_item(Product("p", data.company, "Renamed", "Test"), 1, Decimal(2), Decimal(3))
        sale.add_item(Product("a", data.company, "Other", "Test"), 2, Decimal(3), Decimal(1))
        result = ProductAnalysis().run(data)
        self.assertEqual(result.quantity_ranking, ("a", "p"))
        self.assertEqual(result.revenue_ranking, ("a", "p"))
        self.assertEqual([(r.product_id, r.quantity, r.revenue, r.gross_profit) for r in result.products],
                         [("a", 2, Decimal(6), Decimal(4)), ("p", 2, Decimal(6), Decimal(3))])

    def test_distinct_rankings_and_loss(self) -> None:
        """Quantity and revenue rankings differ; loss remains a signed amount."""
        data = dataset([1])
        data.sales[0].add_item(Product("a", data.company, "A", "T"), 2, Decimal(0), Decimal(3))
        result = ProductAnalysis().run(data)
        self.assertEqual(result.quantity_ranking, ("a", "p"))
        self.assertEqual(result.revenue_ranking, ("p", "a"))
        self.assertEqual(result.products[0].gross_profit, Decimal(-6))
        self.assertEqual(FinancialAnalysis().run(data).financial.gross_margin, Decimal(-5))

    def test_polymorphism_and_validation(self) -> None:
        """Concrete analyses share a contract and reject invalid datasets."""
        with self.assertRaises(TypeError):
            Analysis()
        data = dataset([1])
        for analysis in (FinancialAnalysis(), ProductAnalysis()):
            self.assertIs(analysis.run(data).company, data.company)
            with self.assertRaises(TypeError):
                analysis.run([])


class ForecastTests(unittest.TestCase):
    """Verify chronological holdout, training-only baseline and forecast boundaries."""

    def test_linear_trend_and_baseline(self) -> None:
        """Known linear data gives exact future dates and nearly zero model error."""
        result = RevenueForecaster().forecast(dataset([10, 20, 30, 40, 50, 60, 70], reverse=True), horizon=3)
        self.assertEqual([r.revenue for r in result.training], [Decimal(i) for i in (10, 20, 30, 40, 50)])
        self.assertEqual(result.baseline_revenue, 50)
        self.assertEqual(result.baseline_errors.mae, 15)
        self.assertAlmostEqual(result.baseline_errors.rmse, (250 ** .5))
        self.assertAlmostEqual(result.model_errors.mae, 0)
        self.assertEqual(result.future[0].day.isoformat(), "2026-01-08")
        self.assertEqual(result.future[-1].day.isoformat(), "2026-01-10")
        self.assertAlmostEqual(result.future[-1].revenue, 100)

    def test_test_targets_never_influence_evaluation_fit(self) -> None:
        """Changing holdout targets cannot alter test predictions or baseline."""
        forecaster = RevenueForecaster()
        first = forecaster.forecast(dataset([10, 20, 30, 40, 50, 60, 70]))
        changed = forecaster.forecast(dataset([10, 20, 30, 40, 50, 600, 700]))
        self.assertEqual(first.test_predictions, changed.test_predictions)
        self.assertEqual(first.baseline_revenue, changed.baseline_revenue)
        self.assertGreater(changed.model_errors.mae, first.model_errors.mae)
        self.assertNotEqual(first.future, changed.future)

    def test_missing_days_and_daily_sum(self) -> None:
        """Missing records require a declared policy; multiple sales sum by day."""
        original = dataset([10, 20, 30])
        sparse = SalesDataset(original.company)
        sparse.add_sale(original.sales[2])
        sparse.add_sale(original.sales[0])
        with self.assertRaises(ValueError):
            daily_revenue(sparse)
        self.assertEqual([r.revenue for r in daily_revenue(sparse, missing_days="zero")], [Decimal(10), Decimal(0), Decimal(30)])
        another = Sale("extra", original.company, original.sales[0].date_time)
        another.add_item(original.sales[0].items[0].product, 1, Decimal(7), Decimal(0))
        original.add_sale(another)
        self.assertEqual(daily_revenue(original)[0].revenue, Decimal(17))

    def test_timezone_policy(self) -> None:
        """Aware sales need an explicit shared company timezone for grouping."""
        data = SalesDataset(Company("Aware", "Retail"))
        sale = Sale("1", data.company, datetime(2026, 1, 2, 1, tzinfo=timezone.utc))
        sale.add_item(Product("p", data.company, "P", "T"), 1, Decimal(1), Decimal(0))
        data.add_sale(sale)
        with self.assertRaises(ValueError):
            daily_revenue(data)
        self.assertEqual(daily_revenue(data, timezone=timezone(timedelta(hours=-3)))[0].day.isoformat(), "2026-01-01")
        with self.assertRaises(ValueError):
            daily_revenue(dataset([1]), timezone=timezone.utc)

    def test_calendar_overflow(self) -> None:
        """Future dates outside the calendar raise a clear validation error."""
        data = SalesDataset(Company("End", "Retail"))
        product = Product("p", data.company, "P", "T")
        for i in range(7):
            sale = Sale(str(i), data.company, datetime(9999, 12, 25) + timedelta(days=i))
            sale.add_item(product, 1, Decimal(i + 1), Decimal(0))
            data.add_sale(sale)
        with self.assertRaisesRegex(ValueError, "calendar range"):
            RevenueForecaster().forecast(data)

    def test_invalid_inputs(self) -> None:
        """Reject insufficient, constant, huge and incorrectly configured inputs."""
        forecaster = RevenueForecaster()
        for values in ([], [1, 2, 3], [1] * 7, [Decimal("1e999")] * 7):
            with self.subTest(values=values), self.assertRaises(ValueError):
                forecaster.forecast(dataset(values))
        for name in ("horizon", "test_days"):
            for value in (True, 1.5, "2"):
                with self.subTest(name=name, value=value), self.assertRaises(TypeError):
                    forecaster.forecast(dataset(list(range(7))), **{name: value})
            with self.assertRaises(ValueError):
                forecaster.forecast(dataset(list(range(7))), **{name: 0})
        with self.assertRaises(ValueError):
            forecaster.forecast(dataset(list(range(7))), test_days=1)
        with self.assertRaises(ValueError):
            daily_revenue(dataset([1]), missing_days="ignore")
        with self.assertRaises(TypeError):
            forecaster.forecast(None)
        with self.assertRaises(TypeError):
            daily_revenue(dataset([1]), timezone="UTC")


if __name__ == "__main__":
    unittest.main()
