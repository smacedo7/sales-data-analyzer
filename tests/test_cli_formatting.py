"""Display formatting rounds for reading only and never changes values."""

from decimal import Decimal
from pathlib import Path
import unittest

from sales_data_analyzer.cli.formatting import (
    format_financial,
    format_float,
    format_money,
    format_optional_money,
    format_percent,
    format_products,
    format_scope,
    plural,
)


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
