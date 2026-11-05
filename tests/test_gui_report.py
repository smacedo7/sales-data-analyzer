"""Desktop window: PDF report built from service results and written with Qt."""

from datetime import date, datetime
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock

from support.qt import WindowTestCase

from sales_data_analyzer.application import SalesSession
from sales_data_analyzer.gui import pdf_report, reports
from sales_data_analyzer.gui.texts import money

from support.sessions import START, daily_session

MOMENT = datetime(2026, 11, 5, 14, 30)


def page_count(path: Path) -> int:
    """Count the page objects of a PDF file."""
    return len(re.findall(rb"/Type\s*/Page\b", path.read_bytes()))


class ContentTests(unittest.TestCase):
    def test_content_uses_the_service_results(self) -> None:
        session = daily_session(21)
        content = pdf_report.report_content(session, MOMENT)
        self.assertEqual((content.company, content.sector), ("Acme", "Retail"))
        self.assertEqual(content.period, "todo o histórico")
        self.assertEqual(content.generated, "05/11/2026 14:30:00")
        self.assertEqual(content.cards, reports.financial_cards(session))
        self.assertEqual(content.top_products, reports.top_products_table(session, limit=10))
        self.assertEqual([kind for kind, _ in content.charts], ["daily", "monthly", "products"])
        for _, png in content.charts:
            self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        self.assertIn("Último valor", content.forecast_note)

    def test_html_has_the_four_sections_and_exact_values(self) -> None:
        session = daily_session(21)
        session.set_period(START, date(2026, 1, 11))
        content = pdf_report.report_content(session, MOMENT)
        html = pdf_report.report_html(content)
        metrics = session.run_financial_analysis().financial
        for text in (
            "Relatório de vendas — Acme",
            "Período: 05/01/2026 a 11/01/2026",
            "Indicadores financeiros",
            money(metrics.revenue),
            "Produtos de destaque",
            "Gráficos",
            'src="chart:daily"',
        ):
            self.assertIn(text, html)
        self.assertIn("Previsão não desenhada", html)  # 7 days: too short for the comparison

    def test_names_are_escaped_in_html(self) -> None:
        session = SalesSession()
        daily_session(3, session=session)
        session.update_company("A <b>&</b>", "Retail")
        html = pdf_report.report_html(pdf_report.report_content(session, MOMENT))
        self.assertIn("A &lt;b&gt;&amp;&lt;/b&gt;", html)

    def test_card_grid_has_two_rows_of_three(self) -> None:
        html = pdf_report.report_html(pdf_report.report_content(daily_session(3), MOMENT))
        cards = html[html.index("Indicadores financeiros") : html.index("Produtos de destaque")]
        self.assertEqual(cards.count('class="card"'), 6)
        self.assertEqual(cards.count("</tr><tr>"), 1)

    def test_pdf_layout_fits_charts_to_the_page_width(self) -> None:
        from PySide6.QtCore import QSizeF

        from support.qt import application

        application()
        content = pdf_report.report_content(daily_session(21), MOMENT)
        doc = pdf_report.document(content, QSizeF(680, 1000))
        self.assertEqual(doc.pageSize(), QSizeF(680, 1000))
        width = int(680 * pdf_report.PDF_CHART_SHARE)
        self.assertEqual(doc.toHtml().count(f'width="{width}"'), 3)
        self.assertIn(f'width="{pdf_report.PREVIEW_IMAGE_WIDTH}"', pdf_report.report_html(content))

    def test_suggested_file_name(self) -> None:
        self.assertEqual(
            pdf_report.suggested_name("Café Aurora (demo)", MOMENT),
            "relatorio-vendas-cafe-aurora-demo-2026-11-05.pdf",
        )
        self.assertEqual(
            pdf_report.suggested_name("***", MOMENT), "relatorio-vendas-empresa-2026-11-05.pdf"
        )


class WriteTests(WindowTestCase):
    def setUp(self) -> None:
        self.app_window = self.window(daily_session(21))
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)

    def test_export_writes_a_multi_page_pdf_and_confirms(self) -> None:
        win = self.app_window
        win.show()
        win.go("report")
        page = win.page("report")
        self.assertIsNotNone(page.content)  # preview built when the page appears
        self.assertIn("Relatório de vendas — Acme", page.preview.toPlainText())
        target = self.folder / "report.pdf"
        self.prompter.queue("save_pdf", target)
        page.export_button.click()
        self.assertTrue(self.prompter.questions[0].startswith("save pdf (relatorio-vendas-acme-"))
        self.assertEqual(target.read_bytes()[:5], b"%PDF-")
        self.assertGreaterEqual(page_count(target), 2)
        self.assertEqual(self.prompter.notices, [f"Relatório salvo em {target}."])
        if os.name == "posix":  # readable like any document, not private like a temp file
            mask = os.umask(0)
            os.umask(mask)
            self.assertEqual(target.stat().st_mode & 0o777, 0o666 & ~mask)
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), ["report.pdf"])

    def test_every_page_is_numbered(self) -> None:
        from PySide6.QtGui import QPainter

        target = self.folder / "report.pdf"
        content = pdf_report.report_content(daily_session(21), MOMENT)
        footers: list[str] = []
        original = QPainter.drawText

        def record(painter, *args):
            if isinstance(args[-1], str):
                footers.append(args[-1])
            return original(painter, *args)

        with mock.patch.object(QPainter, "drawText", record):
            pdf_report.write_pdf(content, target)
        pages = page_count(target)
        self.assertGreaterEqual(pages, 2)
        self.assertEqual(footers, [f"Página {n} de {pages}" for n in range(1, pages + 1)])

    def test_cancel_and_unwritable_folder_leave_no_file(self) -> None:
        win = self.app_window
        page = win.page("report")
        page.build()
        self.prompter.queue("save_pdf", None, self.folder / "missing" / "report.pdf")
        page.export()
        page.export()
        self.assertEqual(
            self.prompter.warnings,
            ["Não foi possível gravar o PDF nesse local. Nenhum arquivo foi criado."],
        )
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_failure_while_printing_keeps_the_previous_file(self) -> None:
        page = self.app_window.page("report")
        page.build()
        target = self.folder / "report.pdf"
        target.write_bytes(b"previous")
        self.prompter.queue("save_pdf", target)
        with mock.patch.object(pdf_report, "document", side_effect=OSError("disk full")):
            page.export()
        self.assertEqual(target.read_bytes(), b"previous")
        self.assertEqual([p.name for p in self.folder.iterdir()], ["report.pdf"])
        self.assertEqual(len(self.prompter.warnings), 1)

    def test_company_without_sales_shows_the_empty_state(self) -> None:
        session = SalesSession()
        session.create_company("Nova", "Varejo")
        win = self.window(session)
        page = win.page("report")
        page.build()
        self.assertFalse(page.export_button.isEnabled())
        self.assertIsNone(page.content)


if __name__ == "__main__":
    unittest.main()
