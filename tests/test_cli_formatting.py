"""Display formatting rounds for reading only and never changes values."""

from decimal import Decimal
import unittest

from sales_data_analyzer.cli.formatting import (
    format_float,
    format_money,
    format_optional_money,
    format_percent,
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
