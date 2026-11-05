"""Small reusable widgets: page header, indicator cards, empty states and tables."""

from collections.abc import Callable, Sequence

from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .reports import Card, Table
from .style import TONES


def label(text: str, name: str | None = None, *, wrap: bool = True) -> QLabel:
    """Return a label with an optional style name (pageTitle, note, …)."""
    widget = QLabel(text)
    if name:
        widget.setObjectName(name)
    widget.setWordWrap(wrap)
    widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return widget


def button(
    text: str, handler: Callable[[], object], *, primary: bool = False, name: str | None = None
) -> QPushButton:
    """Return a push button calling handler with no arguments (never `checked`).

    `primary` uses the accent color; `name` sets another style name (such as preset).
    """
    widget = QPushButton(text)
    if primary or name:
        widget.setObjectName("primary" if primary else name)
    widget.clicked.connect(lambda: handler())
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    return widget


def page_header(title: str, subtitle: str) -> QVBoxLayout:
    """Return the title and subtitle block that opens every page."""
    layout = QVBoxLayout()
    layout.setSpacing(2)
    layout.addWidget(label(title, "pageTitle"))
    layout.addWidget(label(subtitle, "pageSubtitle"))
    return layout


class CardWidget(QFrame):
    """One colored indicator card."""

    def __init__(self, card: Card) -> None:
        """Show card.label above card.value in the card's tone."""
        super().__init__()
        self.setObjectName("card")
        background, ink = TONES.get(card.tone, TONES["blue"])
        self.setStyleSheet(f"QFrame#card {{ background: {background}; }}")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        self.label = label(card.label, "cardLabel")
        self.value = label(card.value, "cardValue", wrap=False)
        self.value.setStyleSheet(f"color: {ink};")
        layout.addWidget(self.label)
        layout.addWidget(self.value)


def card_grid(cards: Sequence[Card], columns: int = 3) -> QWidget:
    """Return the cards laid out in a grid."""
    widget = QWidget()
    grid = QGridLayout(widget)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setSpacing(12)
    for index, card in enumerate(cards):
        grid.addWidget(CardWidget(card), index // columns, index % columns)
    return widget


class EmptyState(QFrame):
    """A friendly message for a screen without data, with up to two next-step buttons."""

    def __init__(
        self,
        title: str,
        body: str,
        actions: Sequence[tuple[str, Callable[[], object]]] = (),
    ) -> None:
        """Show title, body and one button per (text, handler) action."""
        super().__init__()
        self.setObjectName("emptyState")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        self.title = label(title, "emptyTitle")
        self.body = label(body, "note")
        layout.addWidget(self.title)
        layout.addWidget(self.body)
        row = QHBoxLayout()
        self.buttons = [
            button(text, handler, primary=index == 0)
            for index, (text, handler) in enumerate(actions)
        ]
        for widget in self.buttons:
            row.addWidget(widget)
        row.addStretch()
        layout.addLayout(row)


def read_only_table(headers: Sequence[str], *, stretch: int | None = None) -> QTableWidget:
    """Return a row-selecting, non-editable table with alternating row colors.

    The `stretch` column takes the free width (default: the last column).
    """
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(list(headers))
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setAlternatingRowColors(True)
    table.verticalHeader().setVisible(False)
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    if stretch is None:
        header.setStretchLastSection(True)
    else:
        header.setSectionResizeMode(stretch, QHeaderView.ResizeMode.Stretch)
    return table


class FitTable(QTableWidget):
    """A read-only table whose size hint is its content: no inner vertical scrolling
    (the page scrolls) and no empty stretched columns; narrower windows get a
    horizontal scroll bar instead of cut-off numbers."""

    def __init__(self, columns: int) -> None:
        """Create an empty table with the read-only, row-selecting behavior."""
        super().__init__(0, columns)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

    def _content_size(self) -> QSize:
        """Return the size that shows every row and column (after styling)."""
        self.ensurePolished()
        self.resizeColumnsToContents()
        self.resizeRowsToContents()
        frame = 2 * self.frameWidth()
        width = sum(self.columnWidth(c) for c in range(self.columnCount())) + frame
        height = self.horizontalHeader().sizeHint().height() + frame
        height += sum(self.rowHeight(r) for r in range(self.rowCount()))
        return QSize(width + 2, height + 2)

    def sizeHint(self) -> QSize:
        """Return the content size."""
        return self._content_size()

    def event(self, event) -> bool:
        """Ask the layout for a new size once styling has changed the row heights."""
        if event.type() in (QEvent.Type.Polish, QEvent.Type.StyleChange, QEvent.Type.Show):
            QTimer.singleShot(0, self, self.updateGeometry)  # skipped if deleted first
        return super().event(event)

    def minimumSizeHint(self) -> QSize:
        """Allow shrinking horizontally (with a scroll bar), never vertically."""
        size = self._content_size()
        return QSize(
            min(size.width(), 240), size.height() + self.horizontalScrollBar().sizeHint().height()
        )


def fill(
    table: QTableWidget,
    rows: Sequence[Sequence[str]],
    *,
    numeric: Sequence[int] = (),
    bold_last: bool = False,
) -> None:
    """Replace the table's rows; numeric columns are right-aligned, a total row is bold."""
    table.setRowCount(0)
    table.setRowCount(len(rows))
    for row, cells in enumerate(rows):
        for column, text in enumerate(cells):
            item = QTableWidgetItem(text)
            if column in numeric:
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if bold_last and row == len(rows) - 1:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            table.setItem(row, column, item)


def table_widget(data: Table) -> QWidget:
    """Return a titled table with its notes below, sized to its rows."""
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    if data.title:
        layout.addWidget(label(data.title, "sectionTitle"))
    table = FitTable(len(data.headers))
    table.setHorizontalHeaderLabels(list(data.headers))
    table.setObjectName("dataTable")
    fill(table, data.rows, numeric=data.numeric, bold_last=data.total_row)
    layout.addWidget(table, 0, Qt.AlignmentFlag.AlignLeft)
    for note in data.notes:
        layout.addWidget(label(note, "note"))
    return widget


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


def clear_layout(layout) -> None:
    """Remove and delete every widget and nested layout of a layout."""
    while layout.count():
        item = layout.takeAt(0)
        if item.widget() is not None:
            widget = item.widget()
            widget.hide()  # deleteLater is deferred; never leave it drawn under the new content
            widget.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())
