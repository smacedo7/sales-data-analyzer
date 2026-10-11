"""Display formatting rounds for reading only and never changes values."""

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
import unittest

from sales_data_analyzer.application import InsufficientHistoryError, NoSalesInSelectionError
from sales_data_analyzer.cli.formatting import (
    FORECAST_LIMITATIONS,
    explain_forecast_error,
    format_financial,
    format_forecast,
    format_float,
    format_money,
    format_optional_money,
    format_percent,
    format_products,
    format_scope,
    is_missing_days_error,
    plural,
)
from sales_data_analyzer.forecasting import DailyRevenue, ErrorMetrics, ForecastResult, Prediction


class PrimitiveFormattingTests(unittest.TestCase):
    """Money, percentages and statistical floats."""

    def test_money_rounds_half_up(self) -> None:
        self.assertEqual(format_money(Decimal("0.005")), "0.01")
        self.assertEqual(format_money(Decimal("2.675")), "2.68")
        self.assertEqual(format_money(Decimal("1050")), "1,050.00")
        self.assertEqual(format_money(Decimal("1234567.891")), "1,234,567.89")
        self.assertEqual(format_money(Decimal("-3")), "-3.00")

    def test_value_is_not_mutated(self) -> None:
        value = Decimal("10.125")
        format_money(value)
        self.assertEqual(value, Decimal("10.125"))

    def test_optional_and_percent(self) -> None:
        self.assertEqual(format_optional_money(None), "n/a")
        self.assertEqual(format_optional_money(Decimal("22.7")), "22.70")
        self.assertEqual(format_percent(Decimal("0.5991189427312775330396475771")), "59.9%")
        self.assertEqual(format_percent(Decimal("0.6")), "60.0%")
        self.assertEqual(format_percent(Decimal("-0.25")), "-25.0%")
        self.assertEqual(format_percent(None), "n/a")

    def test_float(self) -> None:
        self.assertEqual(format_float(2.842170943040401e-14), "0.00")
        self.assertEqual(format_float(21.602468994692867), "21.60")
        self.assertEqual(format_float(-1500.0), "-1,500.00")


if __name__ == "__main__":
    unittest.main()


class ImportFormattingTests(unittest.TestCase):
    """ID lists and import summaries."""

    def test_id_list(self) -> None:
        from sales_data_analyzer.cli.formatting import format_id_list

        self.assertEqual(format_id_list(("001", "002")), "001, 002")
        ids = tuple(f"{n:03}" for n in range(7))
        self.assertEqual(format_id_list(ids), "000, 001, 002, 003, 004 and 2 more")

    def test_summary(self) -> None:
        from sales_data_analyzer.application.workspace import ImportSummary
        from sales_data_analyzer.cli.formatting import format_import_summary

        self.assertEqual(
            format_import_summary(ImportSummary(2, 3, 2, 0)),
            "Imported 2 sales, 3 items. Products: 2 new, 0 reused.",
        )


class AnalysisFormattingTests(unittest.TestCase):
    """Golden output for the level 1 fixture and an empty selection."""

    def setUp(self) -> None:
        from sales_data_analyzer.application import SalesSession

        self.session = SalesSession()
        workspace = self.session.create_company("Coffee Shop", "Retail")
        workspace.import_sales(Path(__file__).parent / "fixtures" / "valid_sales.csv")
        self.names = {p.id: p.name for p in workspace.products}

    def test_financial(self) -> None:
        lines = format_financial(self.session.run_financial_analysis(), "Coffee Shop - all data")
        self.assertEqual(
            lines,
            [
                "Financial analysis - Coffee Shop - all data",
                "Revenue ............ 45.40",
                "Cost ............... 18.20",
                "Gross profit ....... 27.20",
                "Gross margin ....... 59.9%",
                "Average order ...... 22.70",
                "Sales ..............     2",
            ],
        )

    def test_products(self) -> None:
        lines = format_products(self.session.run_product_analysis(), "scope", self.names)
        self.assertEqual(
            lines,
            [
                "Product analysis - scope",
                "ID   Name             Qty  Revenue  Gross profit",
                "007  Coffee, premium    4    40.40         24.20",
                "008  Tea                1     5.00          3.00",
                "Top by quantity: 007, 008",
                "Top by revenue:  007, 008",
            ],
        )
        self.assertIn("?", format_products(self.session.run_product_analysis(), "s", {})[2])

    def test_empty_selection(self) -> None:
        from datetime import date

        self.session.set_period(date(2020, 1, 1), date(2020, 1, 1))
        financial = format_financial(self.session.run_financial_analysis(), "s")
        self.assertIn("Gross margin .......  n/a", financial)
        self.assertIn("Average order ......  n/a", financial)
        products = format_products(self.session.run_product_analysis(), "s", self.names)
        self.assertEqual(products[-1], "No products sold.")

    def test_scope_and_plural(self) -> None:
        self.assertEqual(format_scope("Shop", "all data", 1), "Shop - all data (1 sale)")
        self.assertEqual(plural(2, "sale"), "2 sales")


def _forecast(model_mae: float, baseline_mae: float) -> ForecastResult:
    """Small hand-built result: 5 training days, 2 test days, 2 future days."""
    start = date(2026, 1, 1)
    days = [DailyRevenue(start + timedelta(days=i), Decimal(10 * (i + 1))) for i in range(7)]
    return ForecastResult(
        training=tuple(days[:5]),
        test=tuple(days[5:]),
        test_predictions=tuple(Prediction(d.day, float(d.revenue)) for d in days[5:]),
        model_errors=ErrorMetrics(model_mae, model_mae),
        baseline_errors=ErrorMetrics(baseline_mae, 15.811388),
        baseline_revenue=50.0,
        future=(Prediction(date(2026, 1, 8), 80.0), Prediction(date(2026, 1, 9), 1234.5)),
    )


class ForecastFormattingTests(unittest.TestCase):
    """Forecast layout, limitations and error explanations (FR-024 to FR-026)."""

    def test_golden_output(self) -> None:
        lines = format_forecast(_forecast(0.0, 15.0), "Coffee Shop - all data")
        self.assertEqual(
            lines,
            [
                "Revenue forecast - Coffee Shop - all data",
                "Training days: 5 | Test days: 2",
                "Model     MAE 0.00  RMSE  0.00",
                "Baseline  MAE 15.00 RMSE 15.81 (repeats last training day)",
                "Better on test days (lower MAE): model",
                "Next 2 days:",
                "2026-01-08     80.00",
                "2026-01-09  1,234.50",
                *FORECAST_LIMITATIONS,
            ],
        )

    def test_limitations_cover_required_points(self) -> None:
        text = " ".join(FORECAST_LIMITATIONS)
        for phrase in (
            "straight-line",
            "seasonality",
            "holidays",
            "promotions",
            "worse than the baseline",
            "negative",
            "no accuracy guarantee",
        ):
            self.assertIn(phrase, text)

    def test_better_line(self) -> None:
        cases = ((1.0, 2.0, "model"), (3.0, 2.0, "baseline"), (2.0, 2.0, "tie (same MAE)"))
        for model, baseline, expected in cases:
            with self.subTest(expected=expected):
                lines = format_forecast(_forecast(model, baseline), "x")
                self.assertIn(f"Better on test days (lower MAE): {expected}", lines)

    def test_insufficient_history(self) -> None:
        self.assertEqual(
            explain_forecast_error(InsufficientHistoryError(3, 8)),
            "Not enough history: 3 day(s) available, at least 8 needed "
            "(5 training + 3 test). Add or import more days.",
        )

    def test_mapped_forecaster_messages(self) -> None:
        cases = {
            "history has missing days; explicitly select zero only for complete records": (
                "Some days between the first and last sale have no sales."
            ),
            "training revenue must vary to learn a trend": (
                "Training revenue is constant, so no trend can be learned."
            ),
            "at least two test days are required": "Test days must be at least 2.",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(explain_forecast_error(ValueError(raw)), expected)
        self.assertEqual(
            explain_forecast_error(NoSalesInSelectionError()), "No sales in the current selection."
        )

    def test_unknown_message_falls_back(self) -> None:
        self.assertEqual(explain_forecast_error(ValueError("something else")), "something else")

    def test_missing_days_detection(self) -> None:
        missing = ValueError(
            "history has missing days; explicitly select zero only for complete records"
        )
        self.assertTrue(is_missing_days_error(missing))
        self.assertFalse(is_missing_days_error(ValueError("other")))
        self.assertFalse(is_missing_days_error(TypeError(str(missing))))
