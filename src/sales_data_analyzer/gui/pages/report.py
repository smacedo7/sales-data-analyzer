"""Report page: a preview of the PDF report and the export button."""

from PySide6.QtWidgets import QHBoxLayout, QTextBrowser, QVBoxLayout

from .. import pdf_report
from ..main_window import MainWindow, Page
from ..texts import t
from ..widgets import button, clear_layout, label, page_header


class ReportPage(Page):
    """Shows what the PDF will contain and writes it where the user chooses."""

    key = "report"

    def __init__(self, window: MainWindow) -> None:
        """Build the export button, the preview and the empty-state area."""
        super().__init__(window)
        self.export_button = button(t("report.export"), self.export, primary=True)
        self.preview = QTextBrowser()
        self.preview.setOpenLinks(False)
        self.content: pdf_report.ReportContent | None = None
        self._stale = True
        actions = QHBoxLayout()
        actions.addWidget(self.export_button)
        actions.addStretch()
        self.empty_area = QVBoxLayout()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 16)
        layout.setSpacing(10)
        layout.addLayout(page_header(t("report.title"), t("report.subtitle")))
        layout.addLayout(actions)
        layout.addLayout(self.empty_area)
        layout.addWidget(label(t("report.preview"), "sectionTitle"))
        layout.addWidget(self.preview, 1)

    def refresh(self) -> None:
        """Forget the previous content; rebuild it only when the page is on screen."""
        self._stale = True
        self.content = None
        if self.isVisible():
            self.build()

    def showEvent(self, event) -> None:  # noqa: N802 - Qt naming
        """Build a pending preview when the page appears (it renders three charts)."""
        super().showEvent(event)
        if self._stale:
            self.build()

    def build(self) -> None:
        """Collect the report of the current selection and show its preview."""
        self._stale = False
        clear_layout(self.empty_area)
        self.preview.clear()
        self.content = None
        if self.session.current is None:
            return
        empty = self.window_.empty_state()
        self.export_button.setEnabled(empty is None)
        self.preview.setVisible(empty is None)
        if empty is not None:
            self.empty_area.addWidget(empty)
            return
        try:  # also runs from refresh, so failures are shown inline
            self.content = pdf_report.report_content(self.session)
        except Exception as error:
            from ..messages import describe_failure

            self.empty_area.addWidget(label(describe_failure(error), "banner"))
            return
        self.preview.setDocument(pdf_report.document(self.content))

    def export(self) -> None:
        """Ask where to save the PDF and write it, all or nothing."""
        if self.content is None:
            self.build()
        if self.content is None:
            return
        path = self.window_.prompter.save_pdf(pdf_report.suggested_name(self.content.company))
        if path is None:
            return
        content = self.content
        written = self.window_.attempt(lambda: pdf_report.write_pdf(content, path))
        if written is not None:
            self.window_.prompter.inform(t("report.saved", path=written))
