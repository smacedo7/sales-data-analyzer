"""Desktop window: explorable charts (type, period, zoom/pan, hover, resizing) and PNG export."""

from datetime import date
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from support.qt import WindowTestCase

from sales_data_analyzer.charts.images import DAILY_FILE, MONTHLY_FILE, PRODUCTS_FILE
from sales_data_analyzer.gui.pages.charts import InteractiveChart, hover_points
from sales_data_analyzer.gui.widgets import EmptyState

from support.sessions import START, daily_session

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
NO_FILE = "Nenhum arquivo foi gravado."
FOLDER_ERROR = "Não foi possível gravar nessa pasta. Nenhum arquivo foi criado."


class ChartsTestCase(WindowTestCase):
    def page_for(self, session):
        self.session = session
        self.win = self.window(session)
        self.win.resize(1100, 760)
        self.win.show()
        self.win.go("charts")
        self.pump()
        return self.win.page("charts")

    def pump(self) -> None:
        for _ in range(4):
            self.app.processEvents()

    def folder(self) -> Path:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        return Path(folder.name)

    def hover(self, chart: InteractiveChart, x: float, y: float) -> None:
        """Send a mouse move at data coordinates (x, y) to the chart."""
        from matplotlib.backend_bases import MouseEvent

        chart.canvas.draw()  # positions are final only after a draw (constrained layout)
        px, py = chart.axes.transData.transform((x, y))
        event = MouseEvent("motion_notify_event", chart.canvas, px, py)
        chart.canvas.callbacks.process("motion_notify_event", event)


class DrawTests(ChartsTestCase):
    def test_opening_the_page_draws_the_daily_chart_with_the_estimate(self) -> None:
        page = self.page_for(daily_session(21))
        chart = page.chart
        self.assertIsInstance(chart, InteractiveChart)
        axes = chart.axes
        self.assertEqual(axes.get_title(loc="left"), "Faturamento diário e previsão")
        self.assertEqual(len(axes.lines), 2)  # revenue and estimate
        data = self.session.chart_data()
        self.assertEqual(list(axes.lines[0].get_ydata()), [float(v) for _, v in data.daily])
        self.assertIn(
            "Linha tracejada: estimativas do método “Último valor”", page.note_label.text()
        )
        self.assertEqual(
            [t.get_text() for t in axes.get_legend().get_texts()],
            ["Faturamento", "Estimativa (Último valor)"],
        )
        self.assertIn("todo o histórico", axes.texts[0].get_text())

    def test_each_chart_type_can_be_chosen(self) -> None:
        page = self.page_for(daily_session(21))
        titles = {
            "monthly": "Faturamento mensal",
            "products": "Os 2 produtos com maior faturamento",
            "weekday": "Média por dia da semana",
            "daily": "Faturamento diário e previsão",
        }
        for kind, title in titles.items():
            with self.subTest(kind=kind):
                page.choose(kind)
                self.assertEqual(page.chart.kind, kind)
                self.assertEqual(page.chart.axes.get_title(loc="left"), title)
        weekday_bars = [bar.get_height() for bar in page.chart.axes.patches] or None
        self.assertIsNone(weekday_bars)  # daily chart is a line chart

    def test_the_chart_follows_the_period_of_the_header(self) -> None:
        page = self.page_for(daily_session(21))
        self.session.set_period(START, date(2026, 1, 9))
        self.win.refresh()
        self.pump()
        self.assertEqual(len(page.chart.axes.lines[0].get_xdata()), 5)
        self.assertIn("05/01/2026 a 09/01/2026", page.chart.axes.texts[0].get_text())

    def test_short_history_draws_no_estimate_and_says_why(self) -> None:
        page = self.page_for(daily_session(5))
        self.assertEqual(len(page.chart.axes.lines), 1)
        self.assertTrue(page.note_label.text().startswith("Previsão não desenhada: "))
        self.assertIn("pelo menos 12 dias", page.note_label.text())

    def test_empty_period_shows_the_empty_state(self) -> None:
        page = self.page_for(daily_session(5))
        self.session.set_period(date(2025, 1, 1), date(2025, 1, 2))
        self.win.refresh()
        self.pump()
        self.assertIsNone(page.chart)
        self.assertEqual(
            [e.title.text() for e in page.findChildren(EmptyState) if e.isVisibleTo(page)],
            ["Nenhuma venda neste período"],
        )
        self.assertFalse(page.save_button.isEnabled())

    def test_chart_is_computed_only_when_the_page_is_shown(self) -> None:
        session = daily_session(21)
        win = self.window(session)
        win.show()
        page = win.page("charts")
        with mock.patch.object(session, "chart_data", wraps=session.chart_data) as chart_data:
            win.refresh()
            self.assertEqual(chart_data.call_count, 0)
            win.go("charts")
            self.pump()
            self.assertEqual(chart_data.call_count, 1)
            page.choose("monthly")  # switching type reuses the values
            self.assertEqual(chart_data.call_count, 1)


class InteractionTests(ChartsTestCase):
    def test_hover_shows_the_exact_value_of_the_nearest_point(self) -> None:
        page = self.page_for(daily_session(21))
        chart = page.chart
        when, value = self.session.chart_data().daily[3]
        from matplotlib.dates import date2num

        self.hover(chart, date2num(when), float(value))
        self.assertTrue(chart.annotation.get_visible())
        self.assertEqual(chart.annotation.get_text(), "08/01/2026\nFaturamento: 13,00")

    def test_hover_on_bars_and_away_from_the_data(self) -> None:
        page = self.page_for(daily_session(21))
        page.choose("products")
        chart = page.chart
        self.hover(chart, 5, 1)  # top bar row (largest revenue) is the last row index
        self.assertEqual(chart.annotation.get_text(), "P1 Pen\n" + "420,00")
        self.hover(chart, 5, -10)
        self.assertFalse(chart.annotation.get_visible())

    def test_hover_ignores_points_zoomed_out_of_view_and_leaving_the_axes(self) -> None:
        from matplotlib.backend_bases import MouseEvent
        from matplotlib.dates import date2num

        page = self.page_for(daily_session(21))
        chart = page.chart
        first_day, first_value = self.session.chart_data().daily[0]
        x = date2num(first_day)
        chart.axes.set_xlim(x + 5, x + 15)  # zoom to days 5..15
        self.hover(chart, x, float(first_value))
        self.assertFalse(chart.annotation.get_visible())
        when, value = self.session.chart_data().daily[8]
        self.hover(chart, date2num(when), float(value))
        self.assertTrue(chart.annotation.get_visible())
        outside = MouseEvent("motion_notify_event", chart.canvas, 1, 1)  # bottom-left corner
        chart.canvas.callbacks.process("motion_notify_event", outside)
        self.assertFalse(chart.annotation.get_visible())

    def test_hover_between_bar_rows_shows_nothing(self) -> None:
        page = self.page_for(daily_session(21))
        page.choose("products")
        self.hover(page.chart, 5, 0.5)  # halfway between the two bars
        self.assertFalse(page.chart.annotation.get_visible())

    def test_hover_texts_use_the_exact_decimals(self) -> None:
        data = daily_session(3).chart_data()
        points = hover_points("monthly", data)
        self.assertEqual(points[0].text, "2026-01\n46,00")  # P1 10+11+12, P2 2 x 2 x 3.25
        weekday = hover_points("weekday", data)
        self.assertEqual(weekday[0].text, "Segunda\n16,50")  # 10 + 2 x 3.25
        self.assertEqual(weekday[3].text, "Quinta\n—")  # no sales on Thursdays

    def test_zoom_and_pan_toolbar_is_translated(self) -> None:
        page = self.page_for(daily_session(21))
        tips = [a.toolTip() for a in page.chart.toolbar.actions() if a.toolTip()]
        self.assertEqual(
            tips[:5],
            [
                "Voltar à visão inicial",
                "Visão anterior",
                "Próxima visão",
                "Arrastar: clique e arraste para deslocar; botão direito dá zoom",
                "Zoom: desenhe um retângulo sobre a área",
            ],
        )
        axes = page.chart.axes
        before = axes.get_xlim()
        page.chart.toolbar.push_current()  # what the zoom tool does before changing limits
        axes.set_xlim(before[0] + 2, before[1] - 2)
        page.chart.toolbar.home()
        self.assertEqual(axes.get_xlim(), before)

    def test_canvas_follows_the_window_size(self) -> None:
        page = self.page_for(daily_session(21))
        self.win.resize(1500, 900)
        self.pump()
        wide = page.chart.canvas.width()
        self.win.resize(950, 650)
        self.pump()
        narrow = page.chart.canvas.width()
        self.assertGreater(wide, narrow + 300)
        self.assertGreaterEqual(page.chart.canvas.height(), 300)


class SaveTests(ChartsTestCase):
    def test_saves_the_three_png_files(self) -> None:
        page = self.page_for(daily_session(21))
        folder = self.folder()
        self.prompter.queue("choose_folder", folder)
        page.save_button.click()
        names = sorted(p.name for p in folder.iterdir())
        self.assertEqual(names, sorted([DAILY_FILE, MONTHLY_FILE, PRODUCTS_FILE]))
        for name in names:
            content = (folder / name).read_bytes()
            self.assertEqual(content[:8], PNG_SIGNATURE)
            self.assertGreater(len(content), 1000)
        self.assertTrue(self.prompter.notices[0].startswith("Arquivos salvos:"))
        self.assertEqual(self.prompter.notices[0].count(".png"), 3)

    def test_existing_files_are_kept_or_replaced_as_answered(self) -> None:
        page = self.page_for(daily_session(5))
        folder = self.folder()
        for name in (DAILY_FILE, MONTHLY_FILE, PRODUCTS_FILE):
            (folder / name).write_bytes(b"old")
        self.prompter.queue("choose_folder", folder, folder)
        self.prompter.queue("confirm", False, False, False, False, True, False)
        page.save()
        self.assertEqual(
            self.prompter.questions[:3],
            [
                f"O arquivo {n} já existe. Substituir?"
                for n in (DAILY_FILE, MONTHLY_FILE, PRODUCTS_FILE)
            ],
        )
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

    def test_png_files_keep_the_english_level_three_labels(self) -> None:
        from sales_data_analyzer.charts.images import ChartInputs, build_figure

        inputs = ChartInputs.from_data(daily_session(5).chart_data())
        self.assertEqual(
            build_figure("daily", inputs).axes[0].get_title(loc="left"), "Daily revenue"
        )
        self.assertEqual(inputs.weekday[0], ("Mon", Decimal("16.50")))  # 10 + 2 x 3.25

    def test_cancelled_folder_dialog_does_nothing(self) -> None:
        page = self.page_for(daily_session(5))
        self.prompter.queue("choose_folder", None)
        page.save()
        self.assertEqual((self.prompter.notices, self.prompter.warnings), ([], []))


if __name__ == "__main__":
    unittest.main()
