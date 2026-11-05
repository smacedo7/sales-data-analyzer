"""Every modal interaction of the window, behind one replaceable object.

The window never opens a dialog itself; it asks its Prompter. Production uses
QtPrompter (message boxes, file dialogs and the forms); tests inject a scripted
prompter so no modal window ever blocks a headless run.
"""

from pathlib import Path
from typing import Protocol

from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox, QWidget

from sales_data_analyzer.domain.product import Product

from .forms import (
    CompanyDialog,
    CompanyValues,
    ProductDialog,
    ProductValues,
    SaleDialog,
    SaleValues,
)


class Prompter(Protocol):
    """Questions and notices the window needs from the person using it."""

    def inform(self, text: str) -> None:
        """Show a neutral notice."""

    def warn(self, text: str) -> None:
        """Show a refusal or failure; nothing was changed."""

    def confirm(self, question: str) -> bool:
        """Ask a yes/no question whose safe default is No."""

    def open_csv(self) -> Path | None:
        """Return a CSV file to import, or None when cancelled."""

    def choose_folder(self) -> Path | None:
        """Return a folder for chart images, or None when cancelled."""

    def company_form(self, name: str = "", sector: str = "") -> CompanyValues | None:
        """Return the typed company values, or None when cancelled."""

    def product_form(self, product: Product | None = None) -> ProductValues | None:
        """Return the typed product values, or None when cancelled."""

    def sale_form(self, products: tuple[Product, ...]) -> SaleValues | None:
        """Return the typed sale, or None when cancelled."""


class QtPrompter:
    """Prompter backed by Qt dialogs parented to a window."""

    def __init__(self, parent: QWidget) -> None:
        """Remember the window that owns every dialog."""
        self._parent = parent

    def inform(self, text: str) -> None:
        """Show an information box."""
        QMessageBox.information(self._parent, "Sales Data Analyzer", text)

    def warn(self, text: str) -> None:
        """Show a warning box."""
        QMessageBox.warning(self._parent, "Sales Data Analyzer", text)

    def confirm(self, question: str) -> bool:
        """Ask Yes/No with No as the default button."""
        answer = QMessageBox.question(
            self._parent,
            "Sales Data Analyzer",
            question,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def open_csv(self) -> Path | None:
        """Ask for a CSV file."""
        name, _ = QFileDialog.getOpenFileName(
            self._parent, "Import CSV", "", "CSV files (*.csv);;All files (*)"
        )
        return Path(name) if name else None

    def choose_folder(self) -> Path | None:
        """Ask for a folder."""
        name = QFileDialog.getExistingDirectory(self._parent, "Save charts in")
        return Path(name) if name else None

    def company_form(self, name: str = "", sector: str = "") -> CompanyValues | None:
        """Run the company form."""
        dialog = CompanyDialog(name, sector, self._parent)
        return dialog.values() if dialog.exec() == QDialog.DialogCode.Accepted else None

    def product_form(self, product: Product | None = None) -> ProductValues | None:
        """Run the product form."""
        dialog = ProductDialog(product, self._parent)
        return dialog.values() if dialog.exec() == QDialog.DialogCode.Accepted else None

    def sale_form(self, products: tuple[Product, ...]) -> SaleValues | None:
        """Run the sale form."""
        dialog = SaleDialog(products, parent=self._parent)
        return dialog.values() if dialog.exec() == QDialog.DialogCode.Accepted else None
