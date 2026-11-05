"""Desktop window, user story 6: the level 3 charts drawn in the window and saved as PNG."""

from datetime import date
from itertools import pairwise
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from support.qt import WindowTestCase

from sales_data_analyzer.charts.images import DAILY_FILE, MONTHLY_FILE, PRODUCTS_FILE
from sales_data_analyzer.gui.pages import ChartsPage
from sales_data_analyzer.gui.pages.charts import PROMPT

from support.sessions import daily_session

NO_FILE = "Nenhum arquivo foi gravado."

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
FOLDER_ERROR = "Não foi possível gravar nessa pasta. Nenhum arquivo foi criado."


class ChartsTestCase(WindowTestCase):
    def page_for(self, session) -> ChartsPage:
        self.session = session
        self.win = self.window(session)
        return next(p for p in self.win.pages if isinstance(p, ChartsPage))

    def folder(self) -> Path:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        return Path(folder.name)


class DrawTests(ChartsTestCase):
    def test_three_charts_with_the_estimate_line(self) -> None:
        page = self.page_for(daily_session(21))
        self.assertEqual(page.note_label.text(), PROMPT)
        page.draw()
        self.assertEqual(len(page.canvases), 3)
        titles = [c.figure.axes[0].get_title(loc="left") for c in page.canvases]
        self.assertEqual(titles, ["Daily revenue", "Monthly revenue", "Top 2 products by revenue"])
        daily = page.canvases[0].figure.axes[0]
        self.assertEqual(len(daily.lines), 2)  # revenue and estimate
        data = self.session.chart_data()
        self.assertEqual(
            list(daily.lines[0].get_ydata()), [float(value) for _, value in data.daily]
        )
        self.assertEqual(
            page.note_label.text(),
            f"Linha tracejada: estimativas do método “{data.forecast_title}” (veja os erros na área Previsões).",
        )

    def test_charts_keep_their_height_and_stack_without_overlapping(self) -> None:
        from sales_data_analyzer.gui.pages.charts import CHART_PIXELS_PER_INCH

        page = self.page_for(daily_session(21))
        self.win.show()
        self.win.go("charts")
        self.app.processEvents()
        page.draw()
        self.app.processEvents()
        bottoms = []
        for canvas in page.canvases:
            self.assertEqual(canvas.height(), canvas.maximumHeight())  # fixed, not squeezed
            self.assertGreaterEqual(canvas.height(), 2 * CHART_PIXELS_PER_INCH)
            bottoms.append((canvas.y(), canvas.y() + canvas.height()))
        for (_, end), (start, _) in pairwise(bottoms):
            self.assertLessEqual(end, start)

    def test_short_history_draws_no_estimate_and_says_why(self) -> None:
        page = self.page_for(daily_session(5))
        page.draw()
        self.assertEqual(len(page.canvases[0].figure.axes[0].lines), 1)
        self.assertTrue(page.note_label.text().startswith("Previsão não desenhada: "))
        self.assertIn("pelo menos 12 dias", page.note_label.text())

    def test_empty_selection_is_refused_and_charts_are_cleared_on_changes(self) -> None:
        page = self.page_for(daily_session(5))
        page.draw()
        self.win.session.set_period(date(2025, 1, 1), date(2025, 1, 2))
        self.win.refresh()
        self.assertEqual((page.canvases, page.note_label.text()), ([], PROMPT))
        page.draw()
        self.assertEqual(self.prompter.warnings, ["Não há vendas no período selecionado."])
        self.assertEqual(page.canvases, [])


class SaveTests(ChartsTestCase):
    def test_saves_the_three_png_files(self) -> None:
        page = self.page_for(daily_session(21))
        folder = self.folder()
        self.prompter.queue("choose_folder", folder)
        page.save()
        names = sorted(p.name for p in folder.iterdir())
        self.assertEqual(names, sorted([DAILY_FILE, MONTHLY_FILE, PRODUCTS_FILE]))
        for name in names:
            self.assertEqual((folder / name).read_bytes()[:8], PNG_SIGNATURE)
        self.assertEqual(len(self.prompter.notices), 1)
        self.assertEqual(self.prompter.notices[0].count(".png"), 3)

    def test_existing_files_are_kept_or_replaced_as_answered(self) -> None:
        page = self.page_for(daily_session(5))
        folder = self.folder()
        for name in (DAILY_FILE, MONTHLY_FILE, PRODUCTS_FILE):
            (folder / name).write_bytes(b"old")
        self.prompter.queue("choose_folder", folder, folder)
        self.prompter.queue("confirm", False, False, False, False, True, False)
        page.save()
        self.assertEqual(self.prompter.questions[:3], [f"O arquivo {n} já existe. Substituir?" for n in
                         (DAILY_FILE, MONTHLY_FILE, PRODUCTS_FILE)])  # fmt: skip
        notice = self.prompter.notices[0].split("\n")
        self.assertTrue(notice[0].startswith("Previsão não desenhada: "))
        self.assertEqual(notice[-1], NO_FILE)
        page.save()
        self.assertEqual((folder / DAILY_FILE).read_bytes(), b"old")
        self.assertEqual((folder / MONTHLY_FILE).read_bytes()[:8], PNG_SIGNATURE)
        self.assertEqual((folder / PRODUCTS_FILE).read_bytes(), b"old")
        self.assertNoPendingAnswers()

    def test_unwritable_folder_creates_no_file(self) -> None:
        page = self.page_for(daily_session(5))
        folder = self.folder()
        blocker = folder / "file"
        blocker.write_bytes(b"x")
        self.prompter.queue("choose_folder", blocker / "charts")
        page.save()
        self.assertEqual(self.prompter.warnings, [FOLDER_ERROR])
        self.assertEqual([p.name for p in folder.iterdir()], ["file"])

    def test_rendering_failure_is_reported_and_no_file_is_left(self) -> None:
        page = self.page_for(daily_session(5))
        folder = self.folder()
        self.prompter.queue("choose_folder", folder)
        with mock.patch(
            "sales_data_analyzer.charts.images._render", side_effect=OSError("disk full")
        ):
            page.save()
        self.assertEqual(self.prompter.warnings, [FOLDER_ERROR])
        self.assertEqual(list(folder.iterdir()), [])

    def test_cancelled_folder_dialog_does_nothing(self) -> None:
        page = self.page_for(daily_session(5))
        self.prompter.queue("choose_folder", None)
        page.save()
        self.assertEqual((self.prompter.notices, self.prompter.warnings), ([], []))


if __name__ == "__main__":
    unittest.main()
