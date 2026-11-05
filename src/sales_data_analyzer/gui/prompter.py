"""Every modal interaction of the window, behind one replaceable object.

The window never opens a dialog itself; it asks its Prompter. Production uses
QtPrompter (message boxes, file dialogs and the forms); tests inject a scripted
prompter so no modal window ever blocks a headless run.
"""

from pathlib import Path
from typing import Protocol

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox, QWidget

from sales_data_analyzer.domain.product import Product

from .texts import t
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

    def save_pdf(self, suggested_name: str) -> Path | None:
        """Return the path for a PDF report, or None when cancelled."""

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

    def _box(self, icon: QMessageBox.Icon, title: str, text: str) -> QMessageBox:
        """Return a message box with translated title and text."""
        box = QMessageBox(icon, title, text, parent=self._parent)
        box.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return box

    def inform(self, text: str) -> None:
        """Show an information box."""
        self._box(QMessageBox.Icon.Information, t("app.title"), text).exec()

    def warn(self, text: str) -> None:
        """Show a warning box titled 'Não foi possível concluir'."""
        self._box(QMessageBox.Icon.Warning, t("error.title"), text).exec()

    def confirm(self, question: str) -> bool:
        """Ask Sim/Não with Não as the default button."""
        box = self._box(QMessageBox.Icon.Question, t("app.title"), question)
        yes = box.addButton(t("common.yes"), QMessageBox.ButtonRole.YesRole)
        no = box.addButton(t("common.no"), QMessageBox.ButtonRole.NoRole)
        box.setDefaultButton(no)
        box.setEscapeButton(no)
        box.exec()
        return box.clickedButton() is yes

    def open_csv(self) -> Path | None:
        """Ask for a CSV file."""
        name, _ = QFileDialog.getOpenFileName(
            self._parent, t("form.choose_csv"), "", t("form.csv_filter")
        )
        return Path(name) if name else None

    def choose_folder(self) -> Path | None:
        """Ask for a folder."""
        name = QFileDialog.getExistingDirectory(self._parent, t("form.choose_folder"))
        return Path(name) if name else None

    def save_pdf(self, suggested_name: str) -> Path | None:
        """Ask where to save the PDF report (the dialog itself confirms replacing)."""
        name, _ = QFileDialog.getSaveFileName(
            self._parent, t("form.save_pdf"), suggested_name, t("form.pdf_filter")
        )
        if not name:
            return None
        path = Path(name)
        return path if path.suffix.lower() == ".pdf" else path.with_suffix(".pdf")

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
