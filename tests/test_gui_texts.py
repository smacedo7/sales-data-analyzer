"""Text catalog, display formats and demonstration data of the desktop window."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import re
import unittest

from sales_data_analyzer.application import DuplicateCompanyError, SalesSession
from sales_data_analyzer.gui import demo, texts
from sales_data_analyzer.gui.texts import money, percent, t


class CatalogTests(unittest.TestCase):
    def tearDown(self) -> None:
        texts.set_language(texts.DEFAULT_LANGUAGE)

    def test_every_language_has_the_same_keys_and_placeholders(self) -> None:
        reference = texts.CATALOGS["pt_BR"]
        for language, catalog in texts.CATALOGS.items():
            with self.subTest(language=language):
                self.assertEqual(set(catalog), set(reference))
                for key, text in catalog.items():
                    self.assertEqual(
                        set(re.findall(r"{(\w+)}", text)),
                        set(re.findall(r"{(\w+)}", reference[key])),
                        key,
                    )

    def test_plural_forms_and_unknown_keys(self) -> None:
        self.assertEqual(t("common.sales", count=1), "1 venda")
        self.assertEqual(t("common.sales", count=3), "3 vendas")
        with self.assertRaises(KeyError):
            t("no.such.key")

    def test_switching_language_translates_texts_and_number_formats(self) -> None:
        self.assertEqual(t("nav.sales"), "Vendas")
        self.assertEqual(money(Decimal("1310")), "1.310,00")
        texts.set_language("en")
        self.assertEqual(t("nav.sales"), "Sales")
        self.assertEqual(money(Decimal("1310")), "1,310.00")
        with self.assertRaises(ValueError):
            texts.set_language("xx")


class FormatTests(unittest.TestCase):
    def test_money_rounds_half_up_only_for_display(self) -> None:
        amount = Decimal("1234567.005")
        self.assertEqual(money(amount), "1.234.567,01")
        self.assertEqual(amount, Decimal("1234567.005"))
        self.assertEqual(money(None), "—")
        self.assertEqual(texts.signed_money(Decimal("-2.5")), "-2,50")
        self.assertEqual(texts.signed_money(Decimal("0")), "+0,00")

    def test_percent_dates_and_numbers(self) -> None:
        self.assertEqual(percent(Decimal("0.8444")), "84,4%")
        self.assertEqual(percent(Decimal("0.05"), signed=True), "+5,0%")
        self.assertEqual(percent(None), "—")
        self.assertEqual(texts.day(date(2026, 1, 5)), "05/01/2026")
        moment = datetime(2026, 1, 5, 9, 30, tzinfo=timezone(timedelta(hours=-3)))
        self.assertEqual(texts.moment(moment), "05/01/2026 09:30:00 UTC-03:00")
        self.assertEqual(texts.decimal_number(-0.001, signed=True), "+0,00")
        self.assertEqual(texts.integer(12345), "12.345")
        self.assertEqual(texts.weekday(6), "Domingo")
        self.assertEqual(texts.method_title("moving_average_7", "x"), "Média de 7 dias")
        self.assertEqual(texts.method_title("unknown", "Fallback"), "Fallback")
        self.assertEqual(texts.id_list(("a", "b", "c"), limit=2), "a, b, …")


class DemoTests(unittest.TestCase):
    def test_demo_company_is_imported_in_one_transaction(self) -> None:
        session = SalesSession()
        workspace, summary = demo.load_demo(session, last_day=date(2026, 3, 31))
        self.assertIs(session.current, workspace)
        self.assertEqual(workspace.company.name, demo.DEMO_COMPANY)
        self.assertEqual(summary.new_products, 6)
        self.assertEqual(summary.sales_added, len(workspace.sales.sales))
        days = {sale.date_time.date() for sale in workspace.sales.sales}
        self.assertEqual(len(days), demo.DEMO_DAYS)
        self.assertEqual(max(days), date(2026, 3, 31))
        self.assertEqual(demo.find_demo(session), 1)
        with self.assertRaises(DuplicateCompanyError):
            demo.load_demo(session)

    def test_rows_are_deterministic(self) -> None:
        self.assertEqual(demo.demo_rows(date(2026, 3, 31)), demo.demo_rows(date(2026, 3, 31)))


if __name__ == "__main__":
    unittest.main()
