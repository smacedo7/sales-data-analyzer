"""Desktop window, user story 4: period selection and analyses equal the terminal's text."""

from datetime import date, timedelta
import unittest

from support.qt import WindowTestCase

from sales_data_analyzer.application import SalesSession, Selection
from sales_data_analyzer.cli.formatting import (
    format_categories,
    format_financial,
    format_period_comparison,
    format_products,
    format_scope,
    format_temporal,
    format_weekdays,
)
from sales_data_analyzer.gui import reports
from sales_data_analyzer.gui.main_window import to_qdate
from sales_data_analyzer.gui.pages import AnalysesPage

from support.sessions import START, daily_session


class AnalysesTestCase(WindowTestCase):
    def setUp(self) -> None:
        self.session = daily_session(10, skip=(3,))
        self.win = self.window(self.session)
        self.page = next(p for p in self.win.pages if isinstance(p, AnalysesPage))

    def shown(self, view: str, *, zero: bool = False) -> list[str]:
        self.page.choose(view)
        self.page.zero_box.setChecked(zero)
        self.page.show_analysis()
        return self.page.output.toPlainText().split("\n")

    def scope(self) -> str:
        count = len(self.session.selected_sales().sales)
        return format_scope("Acme", self.session.selection.describe(), count)


class ParityTests(AnalysesTestCase):
    """Every figure shown comes from the service result and the terminal formatter."""

    def test_each_view_matches_the_terminal_formatter(self) -> None:
        s = self.session
        names = {p.id: p.name for p in s.require_current().products}
        expected = {
            "financial": format_financial(s.run_financial_analysis(), self.scope()),
            "products": format_products(s.run_product_analysis(), self.scope(), names),
            "day": format_temporal(s.sales_over_time("day"), self.scope()),
            "week": format_temporal(s.sales_over_time("week"), self.scope()),
            "month": format_temporal(s.sales_over_time("month"), self.scope()),
            "weekday": format_weekdays(
                s.weekday_profile(), self.scope(), zero_filled=False, days_are_utc=False
            ),
            "category": format_categories(s.category_totals(), self.scope()),
        }
        for view, lines in expected.items():
            with self.subTest(view=view):
                self.assertEqual(self.shown(view), lines)
        self.assertEqual(self.prompter.warnings, [])

    def test_missing_days_are_explained_and_can_count_as_zero(self) -> None:
        self.assertTrue(self.page.zero_box.isEnabled())
        self.assertEqual(
            self.page.missing_label.text(), "1 day between the first and last sale have no sales."
        )
        zero = format_temporal(
            self.session.sales_over_time("day", missing_days="zero"), self.scope()
        )
        self.assertEqual(self.shown("day", zero=True), zero)
        self.assertNotEqual(self.shown("day"), zero)
        weekday = format_weekdays(
            self.session.weekday_profile(missing_days="zero"),
            self.scope(),
            zero_filled=True,
            days_are_utc=False,
        )
        self.assertEqual(self.shown("weekday", zero=True), weekday)

    def test_complete_history_disables_the_zero_option(self) -> None:
        win = self.window(daily_session(4))
        page = next(p for p in win.pages if isinstance(p, AnalysesPage))
        self.assertFalse(page.zero_box.isEnabled())
        self.assertEqual(page.missing_label.text(), "")

    def test_unknown_view_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            reports.analysis_lines(self.session, "pie")  # type: ignore[arg-type]


class PeriodTests(AnalysesTestCase):
    def apply(self, start: date, end: date) -> None:
        self.win.start_edit.setDate(to_qdate(start))
        self.win.end_edit.setDate(to_qdate(end))
        self.win.apply_period()

    def test_applied_period_filters_every_view_and_the_label(self) -> None:
        self.apply(START, START + timedelta(days=1))
        self.assertEqual(self.session.selection, Selection(START, START + timedelta(days=1)))
        self.assertEqual(
            self.win.selection_label.text(), "Selection: Acme - 2026-01-05 to 2026-01-06 (2 sales)"
        )
        self.assertEqual(
            self.shown("financial"),
            format_financial(self.session.run_financial_analysis(), self.scope()),
        )
        self.win.clear_period()
        self.assertTrue(self.session.selection.is_all)

    def test_all_data_offers_the_span_of_the_sales_as_dates(self) -> None:
        last = START + timedelta(days=9)
        self.assertEqual(
            (self.win.start_edit.date(), self.win.end_edit.date()),
            (to_qdate(START), to_qdate(last)),
        )
        self.assertEqual(self.page.first_start.date(), to_qdate(START))
        self.assertEqual(self.page.second_end.date(), to_qdate(last))

    def test_report_panel_uses_a_fixed_pitch_font(self) -> None:
        from PySide6.QtGui import QFontInfo

        self.assertTrue(QFontInfo(self.page.output.font()).fixedPitch())

    def test_reversed_period_is_refused_and_keeps_the_selection(self) -> None:
        self.apply(START, START)
        self.apply(START + timedelta(days=2), START)
        self.assertEqual(
            self.prompter.warnings, ["Not done: the end date is before the start date."]
        )
        self.assertEqual(self.session.selection, Selection(START, START))
        self.assertEqual(self.win.start_edit.date(), to_qdate(START))

    def test_empty_selection_says_so_instead_of_zeros(self) -> None:
        self.apply(date(2025, 1, 1), date(2025, 1, 2))
        self.assertEqual(self.shown("financial"), ["No sales in the current selection."])
        self.assertFalse(self.page.zero_box.isEnabled())

    def test_new_result_prompt_after_every_change(self) -> None:
        self.shown("financial")
        self.apply(START, START)
        self.assertEqual(self.page.output.toPlainText(), "Choose an analysis and press Show.")

    def test_selecting_another_company_resets_to_all_data(self) -> None:
        session = SalesSession()
        daily_session(3, session=session)
        session.create_company("Bolt", "Tools")
        win = self.window(session)
        win.company_box.activated.emit(1)
        win.start_edit.setDate(to_qdate(START))
        win.end_edit.setDate(to_qdate(START))
        win.apply_period()
        win.company_box.activated.emit(2)
        win.company_box.activated.emit(1)
        self.assertTrue(session.selection.is_all)
        self.assertEqual(win.selection_label.text(), "Selection: Acme - all data (3 sales)")

    def test_period_comparison_matches_the_formatter_and_keeps_the_selection(self) -> None:
        first = (START, START + timedelta(days=1))
        second = (START + timedelta(days=7), START + timedelta(days=9))
        self.page.set_periods(first, second)
        self.page.compare_periods()
        a, b = Selection(*first), Selection(*second)
        expected = format_period_comparison(
            self.session.compare_periods(a, b), a.describe(), b.describe()
        )
        self.assertEqual(self.page.output.toPlainText().split("\n"), expected)
        self.assertTrue(self.session.selection.is_all)

    def test_reversed_comparison_period_is_refused(self) -> None:
        self.page.set_periods((START + timedelta(days=1), START), (START, START))
        self.page.compare_periods()
        self.assertEqual(
            self.prompter.warnings, ["Not done: the end date is before the start date."]
        )


if __name__ == "__main__":
    unittest.main()
