"""Sales tab: the selection's sales, manual sales, CSV import and deleting a sale."""

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from sales_data_analyzer.application import CatalogConflictError, DuplicateSaleError
from sales_data_analyzer.cli.formatting import (
    describe_import_refusal,
    format_import_summary,
    format_money,
    plural,
)

from ..main_window import MainWindow, Page
from ..tables import fill, read_only_table, selected_key

SALES_COLUMNS = ("Sale ID", "Date and time", "Items", "Total")
"""Same columns as the terminal's sales list."""


class SalesPage(Page):
    """Sales of the active selection in insertion order."""

    title = "Sales"

    def __init__(self, window: MainWindow) -> None:
        """Build the table and its buttons."""
        super().__init__(window)
        self.table = read_only_table(SALES_COLUMNS)
        self.count_label = QLabel()
        self.record_button = QPushButton("Record sale…")
        self.record_button.clicked.connect(self.record_sale)
        self.import_button = QPushButton("Import CSV…")
        self.import_button.clicked.connect(self.import_csv)
        self.delete_button = QPushButton("Delete sale")
        self.delete_button.clicked.connect(self.delete_sale)
        buttons = QHBoxLayout()
        for button in (self.record_button, self.import_button, self.delete_button):
            buttons.addWidget(button)
        buttons.addStretch()
        buttons.addWidget(self.count_label)
        layout = QVBoxLayout(self)
        layout.addLayout(buttons)
        layout.addWidget(self.table)

    def refresh(self) -> None:
        """Show the selected sales with their exact totals rounded for display."""
        workspace = self.session.current
        sales = workspace.list_sales(self.session.selected_sales()) if workspace else ()
        fill(
            self.table,
            [
                (
                    s.id,
                    s.date_time.isoformat(),
                    str(len(s.items)),
                    format_money(s.calculate_total()),
                )
                for s in sales
            ],
            right=(2, 3),
        )
        self.count_label.setText(plural(len(sales), "sale"))

    def select(self, sale_id: str) -> None:
        """Select the row of a sale ID, when it is shown."""
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).text() == sale_id:
                self.table.selectRow(row)
                return

    def record_sale(self) -> None:
        """Ask for a sale with catalog items and store it, all or nothing."""
        workspace = self.session.require_current()
        if not workspace.products:
            self.window_.prompter.warn(
                "Not done: the catalog is empty; register or import products first."
            )
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
        self.window_.statusBar().showMessage(
            f"Sale {sale.id} recorded: {plural(len(sale.items), 'item')}, "
            f"total {format_money(sale.calculate_total())}.",
            8000,
        )

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
            self.window_.prompter.inform(format_import_summary(summary))

    def delete_sale(self) -> None:
        """Delete the selected sale and its items after confirmation (default No)."""
        workspace = self.session.require_current()
        sale_id = selected_key(self.table)
        sale = None if sale_id is None else workspace.find_sale(sale_id)
        if sale is None:
            self.window_.prompter.warn("Not done: select a sale in the table first.")
            return
        question = (
            f"Delete sale {sale.id} ({plural(len(sale.items), 'item')}, "
            f"total {format_money(sale.calculate_total())})?"
        )
        if not self.window_.prompter.confirm(question):
            return
        if self.window_.perform(lambda: workspace.delete_sale(sale.id)):
            self.window_.refresh()
