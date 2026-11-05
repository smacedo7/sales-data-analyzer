"""Sales page: the selection's sales, manual sales, CSV import and deleting a sale."""

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout

from sales_data_analyzer.application import CatalogConflictError, DuplicateSaleError

from ..main_window import MainWindow, Page
from ..messages import describe_import_refusal
from ..texts import integer, moment, money, t
from ..widgets import button, clear_layout, fill, label, page_header, read_only_table, selected_key

SALES_COLUMN_KEYS = ("sales.col.id", "sales.col.date", "sales.col.items", "sales.col.total")


class SalesPage(Page):
    """Sales of the active selection in insertion order."""

    key = "sales"

    def __init__(self, window: MainWindow) -> None:
        """Build the actions, the table and the empty-state area."""
        super().__init__(window)
        self.table = read_only_table([t(key) for key in SALES_COLUMN_KEYS])
        self.count_label = label("", "note", wrap=False)
        self.record_button = button(t("sales.record"), self.record_sale, primary=True)
        self.import_button = button(t("sales.import"), self.import_csv)
        self.delete_button = button(t("sales.delete"), self.delete_sale)
        buttons = QHBoxLayout()
        for widget in (self.record_button, self.import_button, self.delete_button):
            buttons.addWidget(widget)
        buttons.addStretch()
        buttons.addWidget(self.count_label)
        self.empty_area = QVBoxLayout()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)
        layout.addLayout(page_header(t("sales.title"), t("sales.subtitle")))
        layout.addLayout(buttons)
        layout.addLayout(self.empty_area)
        layout.addWidget(self.table, 1)

    def refresh(self) -> None:
        """Show the selected sales with exact totals rounded for display, or an empty state."""
        workspace = self.session.current
        sales = workspace.list_sales(self.session.selected_sales()) if workspace else ()
        fill(
            self.table,
            [
                (s.id, moment(s.date_time), integer(len(s.items)), money(s.calculate_total()))
                for s in sales
            ],
            numeric=(2, 3),
        )
        self.count_label.setText(t("common.sales", count=len(sales)))
        clear_layout(self.empty_area)
        empty = self.window_.empty_state() if workspace is not None else None
        if empty is not None:
            self.empty_area.addWidget(empty)
        self.table.setVisible(empty is None)
        self.delete_button.setEnabled(bool(sales))

    def select(self, sale_id: str) -> None:
        """Select the row of a sale code, when it is shown."""
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).text() == sale_id:
                self.table.selectRow(row)
                return

    def record_sale(self) -> None:
        """Ask for a sale with catalog items and store it, all or nothing."""
        workspace = self.session.require_current()
        if not workspace.products:
            self.window_.prompter.warn(t("sales.empty_catalog"))
            return
        values = self.window_.prompter.sale_form(workspace.products)
        if values is None:
            return
        sale = self.window_.attempt(
            lambda: workspace.record_sale(values.sale_id, values.date_time, values.items)
        )
        if sale is None:
            return
        self.window_.refresh()
        self.select(sale.id)
        self.window_.notify(t(
            "sales.recorded",
            id=sale.id,
            items=t("common.items", count=len(sale.items)),
            total=money(sale.calculate_total()),
        ))  # fmt: skip

    def import_csv(self) -> None:
        """Ask for a CSV file and import it into the selected company, all or nothing."""
        workspace = self.session.require_current()
        path = self.window_.prompter.open_csv()
        if path is None:
            return

        def load():  # -> ImportSummary | None
            try:
                return workspace.import_sales(path)
            except (DuplicateSaleError, CatalogConflictError) as error:
                self.window_.prompter.warn(describe_import_refusal(error))
                return None

        summary = self.window_.attempt(load)
        if summary is not None:
            self.window_.refresh()
            self.window_.prompter.inform(t(
                "sales.imported",
                sales=t("common.sales", count=summary.sales_added),
                items=t("common.items", count=summary.items_added),
                new=summary.new_products,
                reused=summary.reused_products,
            ))  # fmt: skip

    def delete_sale(self) -> None:
        """Delete the selected sale and its items after confirmation (default No)."""
        workspace = self.session.require_current()
        sale_id = selected_key(self.table)
        sale = None if sale_id is None else workspace.find_sale(sale_id)
        if sale is None:
            self.window_.prompter.warn(t("sales.select_first"))
            return
        question = t(
            "sales.confirm_delete",
            id=sale.id,
            items=t("common.items", count=len(sale.items)),
            total=money(sale.calculate_total()),
        )
        if not self.window_.prompter.confirm(question):
            return
        if self.window_.perform(lambda: workspace.delete_sale(sale.id)):
            self.window_.refresh()
            self.window_.notify(t("sales.deleted", id=sale.id))
