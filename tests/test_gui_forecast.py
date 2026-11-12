"""Desktop window: linear forecast and forecast method comparison, in Portuguese."""

from datetime import timedelta, timezone
import unittest

from support.qt import WindowTestCase

from sales_data_analyzer.gui.texts import decimal_number, day, method_title

from support.sessions import daily_session


class ForecastTestCase(WindowTestCase):
    def page_for(self, session):
        self.session = session
        win = self.window(session)
        return win.page("forecast")

    def notes(self, page) -> str:
        return "\n".join(page.shown.notes)


class LinearForecastTests(ForecastTestCase):
    def test_tables_show_the_service_result(self) -> None:
        page = self.page_for(daily_session(12))
        page.horizon_box.setValue(3)
        page.test_days_box.setValue(4)
        page.linear_button.click()
        result = self.session.run_forecast(horizon=3, test_days=4)
        errors, estimates = page.shown.tables
        self.assertEqual(
            errors.rows[0],
            ("Reta (modelo)", decimal_number(result.model_errors.mae),
             decimal_number(result.model_errors.rmse)),
        )  # fmt: skip
        self.assertEqual(errors.notes, ("Dias de treino: 8 · dias de teste: 4",))
        self.assertEqual(
            estimates.rows, tuple((day(p.day), decimal_number(p.revenue)) for p in result.future)
        )
        self.assertIn("Limitações:", self.notes(page))
        self.assertEqual(self.prompter.warnings, [])

    def test_short_history_states_available_and_needed_days(self) -> None:
        page = self.page_for(daily_session(4))
        page.run_linear()
        self.assertEqual(
            page.message,
            "Histórico insuficiente: 4 dias disponíveis, são necessários pelo menos 7 dias. "
            "Importe ou registre mais dias.",
        )

    def test_missing_days_need_confirmation(self) -> None:
        page = self.page_for(daily_session(12, skip=(3,)))
        self.prompter.queue("confirm", False, True)
        page.run_linear()
        self.assertEqual(page.message, "Previsão cancelada.")
        self.assertTrue(self.prompter.questions[0].startswith("Há dias sem vendas"))
        self.assertIn(
            "Responda sim só se os registros estiverem completos", self.prompter.questions[0]
        )
        page.run_linear()
        result = self.session.run_forecast(missing_days="zero")
        self.assertEqual(page.shown.tables[1].rows[0][1], decimal_number(result.future[0].revenue))
        self.assertNoPendingAnswers()

    def test_offset_data_groups_days_by_the_typed_offset(self) -> None:
        page = self.page_for(daily_session(12, zone=timezone.utc))
        self.assertTrue(page.offset_edit.isVisibleTo(page))
        page.offset_edit.setText("-03:00")
        page.run_linear()
        result = self.session.run_forecast(utc_offset=timedelta(hours=-3))
        self.assertEqual(page.shown.tables[1].rows[0][0], day(result.future[0].day))
        page.offset_edit.setText("3")
        page.run_linear()
        self.assertEqual(
            page.message,
            "Fuso UTC (+HH:MM ou -HH:MM): use um deslocamento como -03:00 ou +00:00",
        )

    def test_naive_data_hides_the_offset(self) -> None:
        page = self.page_for(daily_session(12))
        self.assertFalse(page.offset_edit.isVisibleTo(page))


class ComparisonTests(ForecastTestCase):
    def test_comparison_lists_the_methods_in_portuguese(self) -> None:
        page = self.page_for(daily_session(35))
        page.compare_button.click()
        result = self.session.compare_forecasts()
        scores = page.shown.tables[0]
        self.assertEqual(
            [row[0] for row in scores.rows],
            [method_title(s.method_key, s.title) for s in result.scores],
        )
        self.assertEqual(scores.rows[0][2], decimal_number(result.scores[0].mae))
        titles = [page.method_box.itemText(i) for i in range(page.method_box.count())]
        self.assertEqual(titles, [row[0] for row in scores.rows])
        self.assertEqual(page.method_box.currentData(), result.chosen_key)
        self.assertTrue(page.use_method_button.isEnabled())
        self.assertIn("não há intervalo de confiança", self.notes(page))

    def test_choosing_another_method_shows_its_estimates(self) -> None:
        page = self.page_for(daily_session(35))
        page.run_comparison()
        other = next(
            s for s in self.session.compare_forecasts().scores
            if s.method_key != page.method_box.currentData()
        )  # fmt: skip
        page.method_box.setCurrentIndex(page.method_box.findData(other.method_key))
        page.use_method_button.click()
        result = self.session.compare_forecasts(method=other.method_key)
        estimates = page.shown.tables[1]
        self.assertTrue(
            estimates.title.startswith(f"Estimativas ({method_title(other.method_key, '')})")
        )
        self.assertEqual(
            estimates.rows[0][1].split(" ")[0], decimal_number(result.future[0].revenue)
        )

    def test_weak_evidence_names_no_better_method(self) -> None:
        page = self.page_for(daily_session(13))
        page.run_comparison()
        notes = self.notes(page)
        self.assertIn("Evidência limitada", notes)
        self.assertNotIn("superou", notes)
        self.assertTrue(page.shown.tables[1].title.startswith("Estimativas (Último valor)"))

    def test_short_history_is_refused_with_the_needed_days(self) -> None:
        page = self.page_for(daily_session(8))
        page.run_comparison()
        self.assertEqual(
            page.message,
            "Histórico insuficiente: 8 dias disponíveis, são necessários pelo menos 12 dias. "
            "Importe ou registre mais dias.",
        )
        self.assertFalse(page.use_method_button.isEnabled())

    def test_missing_days_answer_is_kept_for_the_chosen_method(self) -> None:
        page = self.page_for(daily_session(35, skip=(10,)))
        self.prompter.queue("confirm", True)
        page.run_comparison()
        self.assertIn("1 dia sem vendas foi contado como zero", self.notes(page))
        page.use_method()  # no second question: the answer is reused
        self.assertIn("1 dia sem vendas foi contado como zero", self.notes(page))
        self.assertNoPendingAnswers()

    def test_use_method_before_a_comparison_is_explained(self) -> None:
        page = self.page_for(daily_session(35))
        page.use_method()
        self.assertEqual(self.prompter.warnings, ["Compare os métodos primeiro."])

    def test_changes_forget_the_previous_result(self) -> None:
        page = self.page_for(daily_session(35))
        page.run_comparison()
        page.window_.clear_period()
        self.assertIsNone(page.shown)
        self.assertTrue(page.message.startswith("Escolha as opções"))
        self.assertFalse(page.use_method_button.isEnabled())


if __name__ == "__main__":
    unittest.main()
