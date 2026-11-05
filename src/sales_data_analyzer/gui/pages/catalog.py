"""Catalog tab: register, edit and delete (unsold) products of the selected company."""

from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout

from sales_data_analyzer.application import ProductInUseError
from sales_data_analyzer.cli.formatting import describe_product_in_use

from ..main_window import MainWindow, Page
from ..tables import fill, read_only_table, selected_key

CATALOG_COLUMNS = ("Product ID", "Name", "Category")


class CatalogPage(Page):
    """The selected company's products ordered by ID."""

    title = "Catalog"

    def __init__(self, window: MainWindow) -> None:
        """Build the table and its buttons."""
        super().__init__(window)
        self.table = read_only_table(CATALOG_COLUMNS)
        self.register_button = QPushButton("Register product…")
        self.register_button.clicked.connect(self.register_product)
        self.edit_button = QPushButton("Edit product…")
        self.edit_button.clicked.connect(self.edit_product)
        self.delete_button = QPushButton("Delete product")
        self.delete_button.clicked.connect(self.delete_product)
        buttons = QHBoxLayout()
        for button in (self.register_button, self.edit_button, self.delete_button):
            buttons.addWidget(button)
        buttons.addStretch()
        layout = QVBoxLayout(self)
        layout.addLayout(buttons)
        layout.addWidget(self.table)

    def refresh(self) -> None:
        """Show the catalog of the selected company (empty without one)."""
        workspace = self.session.current
        products = workspace.products if workspace is not None else ()
        fill(self.table, [(p.id, p.name, p.category) for p in products])

    def select(self, product_id: str) -> None:
        """Select the row of a product ID (used after changes and by tests)."""
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).text() == product_id:
                self.table.selectRow(row)
                return

    def _selected_product(self):  # -> Product | None
        """Return the selected catalog product, explaining when there is none."""
        product_id = selected_key(self.table)
        workspace = self.session.require_current()
        product = None if product_id is None else workspace.find_product(product_id)
        if product is None:
            self.window_.prompter.warn("Not done: select a product in the table first.")
        return product

    def register_product(self) -> None:
        """Ask for a product and add it to the catalog."""
        values = self.window_.prompter.product_form()
        if values is None:
            return
        workspace = self.session.require_current()
        product = self.window_.attempt(
            lambda: workspace.register_product(values.product_id, values.name, values.category)
        )
        if product is not None:
            self.window_.refresh()
            self.select(product.id)

    def edit_product(self) -> None:
        """Ask for the selected product's new name and category and store both."""
        product = self._selected_product()
        if product is None:
            return
        values = self.window_.prompter.product_form(product)
        if values is None:
            return
        workspace = self.session.require_current()
        if self.window_.perform(
            lambda: workspace.update_product(product.id, values.name, values.category)
        ):
            self.window_.refresh()
            self.select(product.id)

    def delete_product(self) -> None:
        """Delete the selected product after confirmation, unless sales use it."""
        product = self._selected_product()
        if product is None:
            return
        workspace = self.session.require_current()
        in_use = self.window_.attempt(lambda: workspace.sales_with_product(product.id))
        if in_use is None:
            return
        if in_use:
            self.window_.prompter.warn(describe_product_in_use(in_use))
            return
        if not self.window_.prompter.confirm(f"Delete product {product.id} {product.name}?"):
            return

        def delete() -> bool:
            try:
                workspace.delete_product(product.id)
            except ProductInUseError as error:  # sold in the meantime
                self.window_.prompter.warn(describe_product_in_use(error.sale_count))
                return False
            return True

        if self.window_.attempt(delete) is True:
            self.window_.refresh()
