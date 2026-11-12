"""Products page: register, edit and delete (unsold) products of the selected company."""

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout

from sales_data_analyzer.application import ProductInUseError

from ..main_window import MainWindow, Page
from ..texts import t
from ..widgets import EmptyState, button, fill, page_header, read_only_table, selected_key

CATALOG_COLUMN_KEYS = ("catalog.col.id", "catalog.col.name", "catalog.col.category")


class CatalogPage(Page):
    """The selected company's products ordered by code."""

    key = "catalog"

    def __init__(self, window: MainWindow) -> None:
        """Build the actions, the table and the empty state."""
        super().__init__(window)
        self.table = read_only_table([t(key) for key in CATALOG_COLUMN_KEYS])
        self.register_button = button(t("catalog.register"), self.register_product, primary=True)
        self.edit_button = button(t("catalog.edit"), self.edit_product)
        self.delete_button = button(t("catalog.delete"), self.delete_product)
        self.empty = EmptyState(
            t("empty.no_products.title"),
            t("empty.no_products.body"),
            [(t("empty.go_product"), self.register_product),
             (t("empty.go_import"), self._import)],
        )  # fmt: skip
        buttons = QHBoxLayout()
        for widget in (self.register_button, self.edit_button, self.delete_button):
            buttons.addWidget(widget)
        buttons.addStretch()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)
        layout.addLayout(page_header(t("catalog.title"), t("catalog.subtitle")))
        layout.addLayout(buttons)
        layout.addWidget(self.empty)
        layout.addWidget(self.table, 1)

    def _import(self) -> None:
        """Open the CSV import of the sales page."""
        self.window_.go("sales")
        self.window_.page("sales").import_csv()

    def refresh(self) -> None:
        """Show the catalog of the selected company, or the empty state."""
        workspace = self.session.current
        products = workspace.products if workspace is not None else ()
        fill(self.table, [(p.id, p.name, p.category) for p in products])
        self.empty.setVisible(not products)
        self.table.setVisible(bool(products))
        for widget in (self.edit_button, self.delete_button):
            widget.setEnabled(bool(products))

    def select(self, product_id: str) -> None:
        """Select the row of a product code (used after changes and by tests)."""
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
            self.window_.prompter.warn(t("catalog.select_first"))
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
            self.window_.notify(t("catalog.registered", id=product.id))

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
            self.window_.notify(t("catalog.updated", id=product.id))

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
            self.window_.prompter.warn(t("catalog.in_use", count=in_use))
            return
        if not self.window_.prompter.confirm(
            t("catalog.confirm_delete", id=product.id, name=product.name)
        ):
            return

        def delete() -> bool:
            try:
                workspace.delete_product(product.id)
            except ProductInUseError as error:  # sold in the meantime
                self.window_.prompter.warn(t("catalog.in_use", count=error.sale_count))
                return False
            return True

        if self.window_.attempt(delete) is True:
            self.window_.refresh()
            self.window_.notify(t("catalog.deleted", id=product.id))
