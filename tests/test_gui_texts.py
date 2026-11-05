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

    def test_empty_demo_company_left_by_a_failed_import_is_filled_on_retry(self) -> None:
        from unittest import mock

        from sales_data_analyzer.application import CompanyWorkspace, PersistenceError

        session = SalesSession()
        with mock.patch.object(CompanyWorkspace, "import_sales", side_effect=PersistenceError()):
            with self.assertRaises(PersistenceError):
                demo.load_demo(session, last_day=date(2026, 3, 31))
        self.assertEqual(len(session.workspaces[0].sales.sales), 0)
        workspace, summary = demo.load_demo(session, last_day=date(2026, 3, 31))
        self.assertEqual(len(session.workspaces), 1)
        self.assertEqual(summary.sales_added, len(workspace.sales.sales))

    def test_rows_are_deterministic(self) -> None:
        self.assertEqual(demo.demo_rows(date(2026, 3, 31)), demo.demo_rows(date(2026, 3, 31)))


if __name__ == "__main__":
    unittest.main()


class FailureWordingTests(unittest.TestCase):
    """Refusals are chosen by error type and data, never by English message text."""

    def test_period_refusals_by_kind(self) -> None:
        from sales_data_analyzer.application import InvalidPeriodError
        from sales_data_analyzer.gui.messages import describe_failure

        self.assertEqual(
            describe_failure(InvalidPeriodError("any text", "reversed")),
            "A data final é anterior à data inicial.",
        )
        self.assertEqual(
            describe_failure(InvalidPeriodError("any text", "out_of_range")),
            "A data final precisa ser no máximo 30/12/9999.",
        )
        self.assertEqual(
            describe_failure(InvalidPeriodError("any text", "incomplete")),
            "Informe a data inicial e a data final do período.",
        )

    def test_forecast_refusals_by_reason(self) -> None:
        from sales_data_analyzer.forecasting import ForecastRefusal
        from sales_data_analyzer.gui.messages import describe_failure

        for reason in ("missing_days", "constant_revenue", "calendar_range", "not_finite",
                       "test_days", "short_history"):  # fmt: skip
            with self.subTest(reason=reason):
                text = describe_failure(ForecastRefusal("English text", reason))
                self.assertNotIn("English", text)
                self.assertEqual(text, t(f"forecast.refusal.{reason}"))

    def test_other_value_errors_never_show_their_english_message(self) -> None:
        from sales_data_analyzer.gui.messages import describe_failure

        for error in (ValueError("name cannot be empty"), TypeError(" name must be a string")):
            text = describe_failure(error)
            self.assertNotIn("name", text)
            self.assertTrue(text.startswith("Algum valor informado não foi aceito"))

    def test_constant_revenue_forecast_is_explained_in_portuguese(self) -> None:
        from datetime import datetime, timedelta

        from sales_data_analyzer.application import ItemInput
        from sales_data_analyzer.gui.reports import explain_forecast_refusal

        session = SalesSession()
        workspace = session.create_company("Flat", "Retail")
        workspace.register_product("P", "Pen", "Office")
        for day in range(9):
            workspace.record_sale(f"S{day}", datetime(2026, 1, 5) + timedelta(days=day),
                                  [ItemInput("P", 1, Decimal(5), Decimal(1))])  # fmt: skip
        with self.assertRaises(ValueError) as caught:
            session.run_forecast()
        self.assertEqual(
            explain_forecast_refusal(caught.exception),
            "O faturamento de treino é constante, então não há tendência para aprender.",
        )
