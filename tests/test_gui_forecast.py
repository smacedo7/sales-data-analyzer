"""Desktop window, user story 5: linear forecast and forecast method comparison."""

from datetime import timedelta, timezone
import unittest

from support.qt import WindowTestCase

from sales_data_analyzer.application import InsufficientHistoryError
from sales_data_analyzer.cli.formatting import (
    explain_forecast_error,
    format_comparison,
    format_comparison_estimates,
    format_forecast,
)
from sales_data_analyzer.gui.pages import ForecastPage
from sales_data_analyzer.gui.pages.forecast import CANCELLED, ZERO_QUESTION

from support.sessions import daily_session

SCOPE = "Acme - all data"


class ForecastTestCase(WindowTestCase):
    def page_for(self, session) -> ForecastPage:
        self.session = session
        win = self.window(session)
        return next(p for p in win.pages if isinstance(p, ForecastPage))

    def text(self, page: ForecastPage) -> list[str]:
        return page.output.toPlainText().split("\n")


class LinearForecastTests(ForecastTestCase):
    def test_result_matches_the_terminal_formatter(self) -> None:
        page = self.page_for(daily_session(12))
        page.horizon_box.setValue(3)
        page.test_days_box.setValue(4)
        page.run_linear()
        expected = format_forecast(self.session.run_forecast(horizon=3, test_days=4), SCOPE)
        self.assertEqual(self.text(page), expected)
        self.assertEqual(self.prompter.warnings, [])

    def test_short_history_states_available_and_needed_days(self) -> None:
        page = self.page_for(daily_session(4))
        page.run_linear()
        self.assertEqual(self.text(page), [explain_forecast_error(InsufficientHistoryError(4, 7))])

    def test_missing_days_need_confirmation(self) -> None:
        page = self.page_for(daily_session(12, skip=(3,)))
        self.prompter.queue("confirm", False, True)
        page.run_linear()
        self.assertEqual(self.text(page), [CANCELLED])
        self.assertTrue(self.prompter.questions[0].endswith(ZERO_QUESTION))
        page.run_linear()
        expected = format_forecast(self.session.run_forecast(missing_days="zero"), SCOPE)
        self.assertEqual(self.text(page), expected)
        self.assertNoPendingAnswers()

    def test_offset_data_groups_days_by_the_typed_offset(self) -> None:
        page = self.page_for(daily_session(12, zone=timezone.utc))
        self.assertTrue(page.offset_edit.isVisibleTo(page))
        page.offset_edit.setText("-03:00")
        page.run_linear()
        result = self.session.run_forecast(utc_offset=timedelta(hours=-3))
        self.assertEqual(self.text(page), format_forecast(result, SCOPE))
        page.offset_edit.setText("3")
        page.run_linear()
        self.assertEqual(
            self.prompter.warnings, ["Not done: expected a UTC offset such as -03:00 or +00:00."]
        )

    def test_naive_data_hides_the_offset(self) -> None:
        page = self.page_for(daily_session(12))
        self.assertFalse(page.offset_edit.isVisibleTo(page))


class ComparisonTests(ForecastTestCase):
    def test_comparison_matches_the_formatter_and_lists_the_methods(self) -> None:
        page = self.page_for(daily_session(35))
        page.run_comparison()
        result = self.session.compare_forecasts()
        expected = format_comparison(result, SCOPE) + [""] + format_comparison_estimates(result)
        self.assertEqual(self.text(page), expected)
        titles = [page.method_box.itemText(i) for i in range(page.method_box.count())]
        self.assertEqual(titles, [score.title for score in result.scores])
        self.assertEqual(page.method_box.currentData(), result.chosen_key)
        self.assertTrue(page.use_method_button.isEnabled())

    def test_choosing_another_method_shows_its_estimates(self) -> None:
        page = self.page_for(daily_session(35))
        page.run_comparison()
        other = next(
            s for s in self.session.compare_forecasts().scores
            if s.method_key != page.method_box.currentData()
        )  # fmt: skip
        page.method_box.setCurrentIndex(page.method_box.findData(other.method_key))
        page.use_method()
        result = self.session.compare_forecasts(method=other.method_key)
        self.assertEqual(self.text(page)[-len(format_comparison_estimates(result)):],
                         format_comparison_estimates(result))  # fmt: skip
        self.assertIn(f"Estimates ({other.title})", page.output.toPlainText())

    def test_weak_evidence_names_no_better_method(self) -> None:
        page = self.page_for(daily_session(13))
        page.run_comparison()
        text = page.output.toPlainText()
        self.assertIn("Evidence too limited to name a lowest-error method", text)
        self.assertNotIn("beat", text)
        self.assertIn("Estimates (Last value)", text)

    def test_short_history_is_refused_with_the_needed_days(self) -> None:
        page = self.page_for(daily_session(8))
        page.run_comparison()
        self.assertEqual(
            self.text(page), ["Not done: 8 day(s) of history available, at least 12 needed."]
        )
        self.assertFalse(page.use_method_button.isEnabled())

    def test_missing_days_answer_is_kept_for_the_chosen_method(self) -> None:
        page = self.page_for(daily_session(35, skip=(10,)))
        self.prompter.queue("confirm", True)
        page.run_comparison()
        self.assertIn("1 missing day were treated as zero", page.output.toPlainText())
        page.use_method()  # no second question: the answer is reused
        self.assertIn("1 missing day were treated as zero", page.output.toPlainText())
        self.assertNoPendingAnswers()

    def test_use_method_before_a_comparison_is_explained(self) -> None:
        page = self.page_for(daily_session(35))
        page.use_method()
        self.assertEqual(self.prompter.warnings, ["Not done: compare the methods first."])

    def test_changes_forget_the_previous_result(self) -> None:
        page = self.page_for(daily_session(35))
        page.run_comparison()
        page.window_.clear_period()
        self.assertEqual(self.text(page), ["Choose the options and run a forecast."])
        self.assertFalse(page.use_method_button.isEnabled())


if __name__ == "__main__":
    unittest.main()
