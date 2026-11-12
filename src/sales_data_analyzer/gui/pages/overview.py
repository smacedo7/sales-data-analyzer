"""Overview page: headline indicator cards and the top products of the selection."""

from PySide6.QtWidgets import QVBoxLayout, QWidget

from .. import reports
from ..main_window import MainWindow, Page, scrolling
from ..texts import t
from ..widgets import card_grid, clear_layout, label, page_header, table_widget


class OverviewPage(Page):
    """What a company owner wants first: revenue, profit, margin and best sellers."""

    key = "overview"

    def __init__(self, window: MainWindow) -> None:
        """Build the header and an area redrawn on every refresh."""
        super().__init__(window)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)
        layout.addLayout(page_header(t("overview.title"), t("overview.subtitle")))
        self.body = QVBoxLayout()
        self.body.setSpacing(16)
        layout.addLayout(self.body)
        layout.addStretch()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scrolling(content))
        self.cards: tuple[reports.Card, ...] = ()
        self.top: reports.Table | None = None

    def refresh(self) -> None:
        """Show the cards and top products, or the empty state with next steps."""
        clear_layout(self.body)
        self.cards, self.top = (), None
        if self.session.current is None:
            return
        empty = self.window_.empty_state()
        if empty is not None:
            self.body.addWidget(empty)
            return
        self.cards = reports.financial_cards(self.session)
        self.top = reports.top_products_table(self.session)
        self.body.addWidget(card_grid(self.cards))
        self.body.addWidget(table_widget(self.top))
        self.body.addWidget(label(t("overview.next_steps"), "banner"))
