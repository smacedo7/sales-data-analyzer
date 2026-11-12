"""Home page: welcome, company cards, new company and the demo data shortcut."""

from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

from .. import demo
from ..main_window import MainWindow, Page, scrolling
from ..texts import t
from ..widgets import button, clear_layout, label, page_header


class HomePage(Page):
    """The first screen: choose a company or start with demonstration data."""

    key = "home"
    needs_company = False

    def __init__(self, window: MainWindow) -> None:
        """Build the welcome text, the action row and the company grid."""
        super().__init__(window)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)
        layout.addLayout(page_header(t("home.welcome"), t("home.intro")))
        self.new_button = button(t("home.new_company"), window.new_company, primary=True)
        self.demo_button = button(t("home.demo"), self.load_demo)
        actions = QHBoxLayout()
        actions.addWidget(self.new_button)
        actions.addWidget(self.demo_button)
        actions.addStretch()
        layout.addLayout(actions)
        layout.addWidget(label(t("home.demo_hint", name=demo.DEMO_COMPANY), "note"))
        layout.addWidget(label(t("home.companies"), "sectionTitle"))
        self.empty_label = label(t("home.no_companies"), "note")
        layout.addWidget(self.empty_label)
        self.grid = QGridLayout()
        self.grid.setSpacing(12)
        layout.addLayout(self.grid)
        layout.addStretch()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scrolling(content))
        self.open_buttons: list = []

    def refresh(self) -> None:
        """Show one card per company, with its sector and counts."""
        clear_layout(self.grid)
        self.open_buttons = []
        workspaces = self.session.workspaces
        self.empty_label.setVisible(not workspaces)
        for index, workspace in enumerate(workspaces):
            company = workspace.company
            card = QFrame()
            card.setObjectName("companyCard")
            box = QVBoxLayout(card)
            box.setContentsMargins(16, 14, 16, 14)
            box.addWidget(label(company.name, "sectionTitle"))
            box.addWidget(label(t(
                "home.card",
                sector=company.sector,
                products=t("common.products", count=len(workspace.products)),
                sales=t("common.sales", count=len(workspace.sales.sales)),
            ), "note"))  # fmt: skip
            number = index + 1
            open_button = button(t("home.open"), lambda n=number: self.window_.select_company(n),
                                 primary=workspace is self.session.current)  # fmt: skip
            self.open_buttons.append(open_button)
            box.addWidget(open_button)
            self.grid.addWidget(card, index // 3, index % 3)

    def load_demo(self) -> None:
        """Create the demo company (or select it when it already exists) and open it."""
        existing = demo.find_demo(self.session)
        if existing is not None and self.session.workspaces[existing - 1].sales.sales:
            self.window_.select_company(existing)
            self.window_.notify(t("home.demo_exists"))
            return

        loaded = self.window_.attempt(lambda: demo.load_demo(self.session))
        self.window_.refresh()
        if loaded is None:
            return
        workspace, summary = loaded
        self.window_.go("overview")
        self.window_.prompter.inform(t(
            "home.demo_done",
            name=workspace.company.name,
            sales=t("common.sales", count=summary.sales_added),
            products=t("common.products", count=summary.new_products),
        ))  # fmt: skip
