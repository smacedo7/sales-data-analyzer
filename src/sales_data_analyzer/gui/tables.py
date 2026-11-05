"""Read-only tables filled with already formatted text."""

from collections.abc import Sequence

from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem


def read_only_table(headers: Sequence[str]) -> QTableWidget:
    """Return a row-selecting, non-editable table with the given column headers."""
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(list(headers))
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    table.horizontalHeader().setStretchLastSection(True)
    return table


def fill(table: QTableWidget, rows: Sequence[Sequence[str]], *, right: Sequence[int] = ()) -> None:
    """Replace the table's rows; columns listed in right are right-aligned (numbers)."""
    from PySide6.QtCore import Qt

    table.setRowCount(0)
    table.setRowCount(len(rows))
    for row, cells in enumerate(rows):
        for column, text in enumerate(cells):
            item = QTableWidgetItem(text)
            if column in right:
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            table.setItem(row, column, item)


def selected_key(table: QTableWidget) -> str | None:
    """Return the first-column text of the selected row, or None."""
    rows = table.selectionModel().selectedRows()
    if not rows:
        return None
    item = table.item(rows[0].row(), 0)
    return None if item is None else item.text()


def cells(table: QTableWidget) -> list[list[str]]:
    """Return the table's text, row by row (for tests and copying)."""
    return [
        [table.item(row, column).text() for column in range(table.columnCount())]
        for row in range(table.rowCount())
    ]
