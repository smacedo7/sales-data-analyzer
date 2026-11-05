"""Modal forms that turn typed text into validated values (no service calls here).

Formats are checked with the terminal's parsers, so a value accepted at the
prompt is accepted here and vice versa. Amounts are parsed from text straight to
Decimal; no spin box or float ever holds a price or cost. Business rules
(duplicate IDs, unknown products, empty sales) stay in the application layer.
"""

from dataclasses import dataclass
from datetime import datetime

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from sales_data_analyzer.application import ItemInput
from sales_data_analyzer.cli.parsing import (
    InputError,
    parse_amount,
    parse_datetime,
    parse_positive_int,
    parse_text,
)
from sales_data_analyzer.domain.product import Product


@dataclass(frozen=True)
class CompanyValues:
    """Name and sector typed in the company form."""

    name: str
    sector: str


@dataclass(frozen=True)
class ProductValues:
    """ID, name and category typed in the product form."""

    product_id: str
    name: str
    category: str


@dataclass(frozen=True)
class SaleValues:
    """Sale ID, date and time and items typed in the sale form."""

    sale_id: str
    date_time: datetime
    items: tuple[ItemInput, ...]


class _Form(QDialog):
    """A dialog whose OK button validates first and shows the problem inline."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.error_label = QLabel()
        self.error_label.setObjectName("formError")
        self.error_label.setStyleSheet("color: #b3261e;")
        self.error_label.setWordWrap(True)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

    def accept(self) -> None:
        """Close with OK only when values() succeeds; otherwise show why."""
        try:
            self.values()
        except InputError as error:
            self.error_label.setText(f"Invalid value: {error}.")
            return
        super().accept()

    def values(self) -> object:
        """Return the validated values or raise InputError."""
        raise NotImplementedError


def _parse(label: str, parser, text: str):
    """Run parser on text, naming the field (never the typed value) in the error."""
    try:
        return parser(text)
    except InputError as error:
        raise InputError(f"{label}: {error}") from None


class CompanyDialog(_Form):
    """Name and sector of a new or edited company."""

    def __init__(self, name: str = "", sector: str = "", parent: QWidget | None = None) -> None:
        """Create the form, optionally filled with the current values."""
        super().__init__("Edit company" if name else "New company", parent)
        self.name_edit = QLineEdit(name)
        self.sector_edit = QLineEdit(sector)
        layout = QFormLayout(self)
        layout.addRow("Name", self.name_edit)
        layout.addRow("Sector", self.sector_edit)
        layout.addRow(self.error_label)
        layout.addRow(self.buttons)

    def values(self) -> CompanyValues:
        """Return trimmed non-empty name and sector or raise InputError."""
        return CompanyValues(
            _parse("Name", parse_text, self.name_edit.text()),
            _parse("Sector", parse_text, self.sector_edit.text()),
        )


class ProductDialog(_Form):
    """ID, name and category of a new product, or name and category of an edited one."""

    def __init__(self, product: Product | None = None, parent: QWidget | None = None) -> None:
        """Create an empty form, or one for editing product (its ID cannot change)."""
        super().__init__("Edit product" if product else "Register product", parent)
        self.id_edit = QLineEdit(product.id if product else "")
        self.id_edit.setReadOnly(product is not None)
        self.name_edit = QLineEdit(product.name if product else "")
        self.category_edit = QLineEdit(product.category if product else "")
        layout = QFormLayout(self)
        layout.addRow("Product ID", self.id_edit)
        layout.addRow("Name", self.name_edit)
        layout.addRow("Category", self.category_edit)
        layout.addRow(self.error_label)
        layout.addRow(self.buttons)

    def values(self) -> ProductValues:
        """Return trimmed non-empty values or raise InputError."""
        return ProductValues(
            _parse("Product ID", parse_text, self.id_edit.text()),
            _parse("Name", parse_text, self.name_edit.text()),
            _parse("Category", parse_text, self.category_edit.text()),
        )


ITEM_COLUMNS = ("Product", "Quantity", "Unit price", "Unit cost")
"""Columns of the sale form's item table."""


class SaleDialog(_Form):
    """A manual sale: ID, date and time (optional offset) and catalog items."""

    def __init__(
        self,
        products: tuple[Product, ...],
        now: datetime | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Create the form for the given catalog, with the date prefilled to now."""
        super().__init__("Record sale", parent)
        self._products = products
        moment = (now or datetime.now()).replace(microsecond=0)
        self.id_edit = QLineEdit()
        self.datetime_edit = QLineEdit(moment.isoformat())
        self.datetime_edit.setPlaceholderText("YYYY-MM-DDTHH:MM:SS, optional Z or +HH:MM")
        self.items = QTableWidget(0, len(ITEM_COLUMNS))
        self.items.setHorizontalHeaderLabels(ITEM_COLUMNS)
        self.items.horizontalHeader().setStretchLastSection(True)
        add = QPushButton("Add item")
        add.clicked.connect(self.add_item)
        remove = QPushButton("Remove item")
        remove.clicked.connect(self.remove_item)
        form = QFormLayout()
        form.addRow("Sale ID", self.id_edit)
        form.addRow("Date and time", self.datetime_edit)
        row = QHBoxLayout()
        row.addWidget(add)
        row.addWidget(remove)
        row.addStretch()
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QLabel("Items (amounts as plain decimals, such as 10.50)"))
        layout.addWidget(self.items)
        layout.addLayout(row)
        layout.addWidget(self.error_label)
        layout.addWidget(self.buttons)
        self.resize(640, 360)
        if products:
            self.add_item()

    def add_item(self) -> int:
        """Append an empty item row (quantity 1) and return its index."""
        row = self.items.rowCount()
        self.items.insertRow(row)
        chooser = QComboBox()
        for product in self._products:
            chooser.addItem(f"{product.id} {product.name}", product.id)
        self.items.setCellWidget(row, 0, chooser)
        for column, text in ((1, "1"), (2, ""), (3, "")):
            self.items.setCellWidget(row, column, QLineEdit(text))
        return row

    def remove_item(self) -> None:
        """Remove the selected item row, or the last one."""
        row = self.items.currentRow()
        if row < 0:
            row = self.items.rowCount() - 1
        if row >= 0:
            self.items.removeRow(row)

    def set_item(self, row: int, product_id: str, quantity: str, price: str, cost: str) -> None:
        """Fill one item row (used by tests and keyboard-free automation)."""
        chooser: QComboBox = self.items.cellWidget(row, 0)
        chooser.setCurrentIndex(chooser.findData(product_id))
        for column, text in ((1, quantity), (2, price), (3, cost)):
            self.items.cellWidget(row, column).setText(text)

    def values(self) -> SaleValues:
        """Return the typed sale or raise InputError naming the field and item."""
        sale_id = _parse("Sale ID", parse_text, self.id_edit.text())
        moment = _parse("Date and time", parse_datetime, self.datetime_edit.text())
        items = []
        for row in range(self.items.rowCount()):
            label = f"Item {row + 1}"
            product_id = self.items.cellWidget(row, 0).currentData()
            if product_id is None:
                raise InputError(f"{label}: choose a product")
            quantity = _parse(f"{label} quantity", parse_positive_int,
                              self.items.cellWidget(row, 1).text())  # fmt: skip
            price = _parse(
                f"{label} unit price", parse_amount, self.items.cellWidget(row, 2).text()
            )
            cost = _parse(f"{label} unit cost", parse_amount, self.items.cellWidget(row, 3).text())
            items.append(ItemInput(product_id, quantity, price, cost))
        return SaleValues(sale_id, moment, tuple(items))
