"""Desktop window: overview cards, period selection and analyses built from service results."""

from datetime import date, timedelta
import unittest

from support.qt import WindowTestCase

from sales_data_analyzer.application import SalesSession, Selection
from sales_data_analyzer.gui import reports
from sales_data_analyzer.gui.main_window import to_qdate
from sales_data_analyzer.gui.texts import integer, money, percent
from sales_data_analyzer.gui.widgets import CardWidget, EmptyState

from support.sessions import START, daily_session


class AnalysesTestCase(WindowTestCase):
    def setUp(self) -> None:
        self.session = daily_session(10, skip=(3,))
        self.win = self.window(self.session)
        self.page = self.win.page("analyses")

    def shown(self, view: str, *, zero: bool = False) -> reports.Table:
        self.page.zero_box.setChecked(zero)
        self.page.choose(view)
        self.page.show_analysis()
        return self.page.shown


class OverviewTests(WindowTestCase):
    def test_cards_show_the_financial_analysis_formatted_in_portuguese(self) -> None:
        session = daily_session(10)
        win = self.window(session)
        page = win.page("overview")
        metrics = session.run_financial_analysis().financial
        self.assertEqual(
            [(c.label, c.value) for c in page.cards],
            [
                ("Faturamento", money(metrics.revenue)),
                ("Custo", money(metrics.cost)),
                ("Lucro bruto", money(metrics.gross_profit)),
                ("Margem bruta", percent(metrics.gross_margin)),
                ("Ticket médio", money(metrics.average_order_value)),
                ("Vendas", "10"),
            ],
        )
        self.assertEqual(page.cards[0].value, "177,50")  # P1 10+...+19 = 145; P2 5 x 2 x 3.25
        self.assertEqual(len(page.findChildren(CardWidget)), 6)
        top = page.top
        self.assertEqual(
            top.rows,
            tuple(
                (str(i), r.product_id, r.name, money(r.revenue))
                for i, r in enumerate(session.top_products(5), start=1)
            ),
        )

    def test_company_without_sales_gets_next_steps(self) -> None:
        session = SalesSession()
        session.create_company("Nova", "Varejo")
        win = self.window(session)
        page = win.page("overview")
        empty = page.findChildren(EmptyState)
        self.assertEqual(len(empty), 1)
        self.assertEqual(empty[0].title.text(), "Ainda não há vendas")
        self.assertEqual([b.text() for b in empty[0].buttons], ["Importar CSV", "Registrar venda"])
        self.prompter.queue("open_csv", None)
        empty[0].buttons[0].click()  # goes to Sales and opens the import
        self.assertIs(win.current_page, win.page("sales"))
        self.assertNoPendingAnswers()


class ParityTests(AnalysesTestCase):
    """Every figure shown comes from a service result, only formatted for display."""

    def test_financial_and_category_views(self) -> None:
        metrics = self.session.run_financial_analysis().financial
        self.assertEqual(self.shown("financial").rows[0], ("Faturamento", money(metrics.revenue)))
        categories = self.session.category_totals()
        self.assertEqual(
            self.shown("category").rows,
            tuple(
                (c.category, integer(c.quantity), money(c.revenue), money(c.cost),
                 money(c.gross_profit))
                for c in categories
            ),
        )  # fmt: skip

    def test_temporal_view_total_row_comes_from_the_financial_analysis(self) -> None:
        table = self.shown("month")
        summary = self.session.sales_over_time("month")
        metrics = self.session.run_financial_analysis().financial
        self.assertEqual(table.rows[0][0], summary.rows[0].label)
        self.assertEqual(table.rows[0][1], money(summary.rows[0].revenue))
        self.assertEqual(
            table.rows[-1],
            ("Total", money(metrics.revenue), money(metrics.cost), money(metrics.gross_profit),
             integer(metrics.sale_count)),
        )  # fmt: skip
        self.assertTrue(table.total_row)

    def test_products_view_keeps_the_service_rankings(self) -> None:
        table = self.shown("products")
        result = self.session.run_product_analysis()
        self.assertEqual([row[0] for row in table.rows], [p.product_id for p in result.products])
        self.assertIn(", ".join(result.revenue_ranking), table.notes[1])

    def test_missing_days_are_explained_and_can_count_as_zero(self) -> None:
        self.assertTrue(self.page.zero_box.isEnabled())
        self.assertEqual(
            self.page.missing_label.text(),
            "1 dia entre a primeira e a última venda não tem vendas.",
        )
        zero = self.shown("day", zero=True)
        reject = self.shown("day")
        self.assertEqual(len(zero.rows), len(reject.rows) + 1)
        self.assertIn("Dias sem vendas aparecem como zero.", zero.notes)
        weekday = self.shown("weekday", zero=True)
        profile = self.session.weekday_profile(missing_days="zero")
        self.assertEqual(weekday.rows[0], ("Segunda", "2", money(profile[0].total_revenue),
                                           money(profile[0].average_revenue)))  # fmt: skip

    def test_complete_history_disables_the_zero_option(self) -> None:
        win = self.window(daily_session(4))
        page = win.page("analyses")
        self.assertFalse(page.zero_box.isEnabled())
        self.assertFalse(page.missing_label.isVisibleTo(page))

    def test_unknown_view_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            reports.analysis_table(self.session, "pie")  # type: ignore[arg-type]


class PeriodTests(AnalysesTestCase):
    def apply(self, start: date, end: date) -> None:
        self.win.start_edit.setDate(to_qdate(start))
        self.win.end_edit.setDate(to_qdate(end))
        self.win.apply_period_button.click()

    def test_applied_period_filters_and_updates_the_header(self) -> None:
        self.apply(START, START + timedelta(days=1))
        self.assertEqual(self.session.selection, Selection(START, START + timedelta(days=1)))
        self.assertEqual(self.win.selection_label.text(), "05/01/2026 a 06/01/2026 · 2 vendas")
        self.win.all_data_button.click()
        self.assertTrue(self.session.selection.is_all)
        self.assertEqual(self.win.selection_label.text(), "Todo o histórico · 9 vendas")

    def test_presets_select_the_last_30_days_and_the_last_month_with_sales(self) -> None:
        session = daily_session(40)
        win = self.window(session)
        last = START + timedelta(days=39)
        win.last_30_button.click()
        self.assertEqual(session.selection, Selection(last - timedelta(days=29), last))
        win.month_button.click()
        self.assertEqual(session.selection, Selection(date(2026, 2, 1), date(2026, 2, 28)))

    def test_all_data_offers_the_span_of_the_sales_as_dates(self) -> None:
        last = START + timedelta(days=9)
        self.assertEqual(
            (self.win.start_edit.date(), self.win.end_edit.date()),
            (to_qdate(START), to_qdate(last)),
        )
        self.assertEqual(self.page.first_start.date(), to_qdate(START))
        self.assertEqual(self.page.second_end.date(), to_qdate(last))

    def test_reversed_period_is_refused_and_keeps_the_selection(self) -> None:
        self.apply(START, START)
        self.apply(START + timedelta(days=2), START)
        self.assertEqual(self.prompter.warnings, ["A data final é anterior à data inicial."])
        self.assertEqual(self.session.selection, Selection(START, START))
        self.assertEqual(self.win.start_edit.date(), to_qdate(START))

    def test_empty_selection_shows_a_helpful_empty_state(self) -> None:
        self.apply(date(2025, 1, 1), date(2025, 1, 2))
        self.page.choose("financial")
        empty = self.page.findChildren(EmptyState)
        self.assertEqual([e.title.text() for e in empty], ["Nenhuma venda neste período"])
        self.assertIsNone(self.page.shown)
        empty[0].buttons[0].click()  # "Ver tudo"
        self.assertTrue(self.session.selection.is_all)

    def test_selecting_another_company_resets_to_all_data(self) -> None:
        session = SalesSession()
        daily_session(3, session=session)
        session.create_company("Bolt", "Tools")
        win = self.window(session)
        win.select_company(1)
        win.start_edit.setDate(to_qdate(START))
        win.end_edit.setDate(to_qdate(START))
        win.apply_period()
        win.select_company(2)
        win.select_company(1)
        self.assertTrue(session.selection.is_all)
        self.assertEqual(win.selection_label.text(), "Todo o histórico · 3 vendas")

    def test_period_comparison_shows_the_service_changes(self) -> None:
        first = (START, START + timedelta(days=1))
        second = (START + timedelta(days=7), START + timedelta(days=9))
        self.page.choose("compare")
        self.assertTrue(self.page.periods.isVisibleTo(self.page))
        self.page.set_periods(first, second)
        self.page.compare_button.click()
        comparison = self.session.compare_periods(Selection(*first), Selection(*second))
        table = self.page.shown
        self.assertEqual(table.rows[0][1:3], (money(comparison.first.revenue),
                                              money(comparison.second.revenue)))  # fmt: skip
        self.assertEqual(table.rows[0][3], "+" + money(comparison.revenue_change))
        self.assertTrue(self.session.selection.is_all)

    def test_reversed_comparison_period_is_refused(self) -> None:
        self.page.choose("compare")
        self.page.set_periods((START + timedelta(days=1), START), (START, START))
        self.page.compare_periods()
        self.assertEqual(self.prompter.warnings, ["A data final é anterior à data inicial."])


if __name__ == "__main__":
    unittest.main()
