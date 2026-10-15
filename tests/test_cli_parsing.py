"""Terminal parsing accepts exactly the formats documented for users."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import unittest

from sales_data_analyzer.cli.parsing import (
    InputError,
    parse_amount,
    parse_date,
    parse_datetime,
    parse_path,
    parse_positive_int,
    parse_text,
    parse_utc_offset,
    parse_yes_no,
)
from sales_data_analyzer.importing import ImportValidationError, SalesValidator

ROW = {
    "sale_id": "1",
    "date_time": "2026-01-01T10:00:00",
    "product_id": "p",
    "product": "P",
    "category": "C",
    "quantity": "1",
    "unit_price": "1",
    "unit_cost": "1",
}


def _validator_accepts(field: str, value: str) -> bool:
    try:
        SalesValidator().validate({**ROW, field: value}, 2)
    except ImportValidationError:
        return False
    return True


def _parser_accepts(parser, value: str) -> bool:
    try:
        parser(value)
    except InputError:
        return False
    return True


class ParsingTests(unittest.TestCase):
    """Valid and invalid inputs for each parser."""

    def test_text(self) -> None:
        self.assertEqual(parse_text("  Coffee Shop "), "Coffee Shop")
        with self.assertRaises(InputError):
            parse_text("   ")

    def test_positive_int(self) -> None:
        self.assertEqual(parse_positive_int(" 7 "), 7)
        self.assertEqual(parse_positive_int("365", maximum=365), 365)
        for bad in ("0", "-1", "1.5", "", "abc", "٣"):
            with self.subTest(bad=bad), self.assertRaises(InputError):
                parse_positive_int(bad)
        with self.assertRaises(InputError):
            parse_positive_int("366", maximum=365)
        with self.assertRaises(InputError):  # not Python's digit-limit ValueError
            parse_positive_int("9" * 5000)

    def test_amount_is_exact_decimal(self) -> None:
        self.assertEqual(parse_amount("10.125"), Decimal("10.125"))
        self.assertEqual(parse_amount("0"), Decimal("0"))
        for bad in ("-1", "1e3", "1,50", "1_000", "NaN", "Infinity", "", "abc"):
            with self.subTest(bad=bad), self.assertRaises(InputError):
                parse_amount(bad)

    def test_date(self) -> None:
        self.assertEqual(parse_date("2026-01-02"), date(2026, 1, 2))
        for bad in ("2026-02-30", "2026-1-2", "20260102", "9999-12-31", ""):
            with self.subTest(bad=bad), self.assertRaises(InputError):
                parse_date(bad)

    def test_datetime_keeps_offset(self) -> None:
        self.assertEqual(parse_datetime("2026-01-05T10:00:00"), datetime(2026, 1, 5, 10))
        aware = parse_datetime("2026-01-05T10:00:00-03:00")
        self.assertEqual(aware.utcoffset(), timedelta(hours=-3))
        self.assertEqual(parse_datetime("2026-01-05T10:00:00Z").tzinfo, timezone.utc)

    def test_datetime_outside_utc_range(self) -> None:
        for stamp in ("0001-01-01T00:30:00+01:00", "9999-12-31T23:30:00-01:00"):
            with self.subTest(stamp=stamp), self.assertRaises(InputError):
                parse_datetime(stamp)

    def test_parity_with_csv_validator(self) -> None:
        stamps = (
            "2026-01-01T10:00:00",
            "2026-01-01T10:00:00.123456",
            "2026-01-01T10:00:00Z",
            "2026-01-01T10:00:00+05:30",
            "2026-01-01T10:00:00+24:00",
            "2026-01-01T10:00:00+05:60",
            "2026-02-30T10:00:00",
            "2026-01-01 10:00:00",
            "2026-01-01T10:00",
            "2026-01-01",
        )
        for stamp in stamps:
            with self.subTest(stamp=stamp):
                self.assertEqual(
                    _parser_accepts(parse_datetime, stamp),
                    _validator_accepts("date_time", stamp),
                )
        for amount in ("10.50", "+1", ".5", "5.", "-1", "1e2", "1,0", "0"):
            with self.subTest(amount=amount):
                self.assertEqual(
                    _parser_accepts(parse_amount, amount),
                    _validator_accepts("unit_price", amount),
                )

    def test_utc_offset(self) -> None:
        self.assertEqual(parse_utc_offset("-03:00"), timedelta(hours=-3))
        self.assertEqual(parse_utc_offset("+05:30"), timedelta(hours=5, minutes=30))
        for bad in ("03:00", "+3", "+24:00", "+01:60", "UTC"):
            with self.subTest(bad=bad), self.assertRaises(InputError):
                parse_utc_offset(bad)

    def test_yes_no(self) -> None:
        self.assertTrue(parse_yes_no("Y"))
        self.assertTrue(parse_yes_no("yes"))
        self.assertFalse(parse_yes_no(""))
        self.assertFalse(parse_yes_no("n"))
        with self.assertRaises(InputError):
            parse_yes_no("maybe")

    def test_path(self) -> None:
        self.assertEqual(parse_path('"C:\\My Data\\sales.csv"'), Path("C:\\My Data\\sales.csv"))
        self.assertEqual(parse_path("'/tmp/my sales.csv'"), Path("/tmp/my sales.csv"))
        self.assertEqual(
            parse_path("/Users/me/My\\ Sales.csv", posix=True), Path("/Users/me/My Sales.csv")
        )
        self.assertEqual(parse_path("C:\\data\\a.csv", posix=False), Path("C:\\data\\a.csv"))
        with self.assertRaises(InputError):
            parse_path("  ")


if __name__ == "__main__":
    unittest.main()
