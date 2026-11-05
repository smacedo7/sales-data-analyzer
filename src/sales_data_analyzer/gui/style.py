"""Colors and the Qt style sheet of the desktop window (one warm, consistent palette).

The chart colors match the level 3 PNG charts (blue history, orange estimate),
so the window, the PNG files and the PDF report look like one product.
"""

SURFACE = "#fbf8f3"
"""Warm off-white page background."""
PANEL = "#ffffff"
INK = "#1f2933"
MUTED = "#5f6b76"
LINE = "#e6e0d6"
SIDEBAR = "#1f3a4d"
SIDEBAR_TEXT = "#e8eef2"
SIDEBAR_ACTIVE = "#f4a259"
ACCENT = "#eb6834"
ACCENT_DARK = "#c2531f"
BLUE = "#2a78d6"

TONES: dict[str, tuple[str, str]] = {
    "blue": ("#e8f1fc", "#1f5fae"),
    "coral": ("#fdece4", "#b8461b"),
    "green": ("#e6f5ec", "#1d7a46"),
    "purple": ("#f0eafb", "#5b3fa6"),
    "amber": ("#fdf3dc", "#8a5a00"),
    "teal": ("#e2f4f3", "#16706b"),
}
"""Card tone -> (background, value color)."""

STYLE_SHEET = f"""
QMainWindow, QWidget#page, QStackedWidget, QScrollArea, QWidget#scrollBody {{
    background: {SURFACE};
}}
QWidget {{ color: {INK}; font-size: 13px; }}
QLabel#pageTitle {{ font-size: 24px; font-weight: 700; color: {INK}; }}
QLabel#pageSubtitle {{ color: {MUTED}; font-size: 13px; }}
QLabel#sectionTitle {{ font-size: 15px; font-weight: 700; margin-top: 8px; }}
QLabel#note {{ color: {MUTED}; }}
QLabel#banner {{
    background: #fff4e5; border: 1px solid #f6d7a7; border-radius: 8px; padding: 8px 12px;
    color: #7a4b00;
}}
QFrame#header {{ background: {PANEL}; border-bottom: 1px solid {LINE}; }}
QLabel#companyName {{ font-size: 16px; font-weight: 700; }}
QLabel#selectionLabel {{ color: {MUTED}; }}
QListWidget#sidebar {{
    background: {SIDEBAR}; color: {SIDEBAR_TEXT}; border: none; padding-top: 8px;
    font-size: 14px; outline: 0;
}}
QListWidget#sidebar::item {{ padding: 10px 16px; border-left: 4px solid transparent; }}
QListWidget#sidebar::item:selected {{
    background: #2b4d64; color: white; border-left: 4px solid {SIDEBAR_ACTIVE};
}}
QListWidget#sidebar::item:disabled {{ color: #7d93a3; }}
QLabel#brand {{
    background: {SIDEBAR}; color: white; font-size: 16px; font-weight: 700; padding: 18px 16px 6px;
}}
QLabel#brandSubtitle {{ background: {SIDEBAR}; color: #a9bccb; padding: 0 16px 12px; }}
QPushButton {{
    background: {PANEL}; border: 1px solid #d5cdc0; border-radius: 8px; padding: 7px 14px;
}}
QPushButton:hover {{ background: #f6f1e9; }}
QPushButton:disabled {{ color: #a7a29a; border-color: {LINE}; }}
QPushButton#primary {{
    background: {ACCENT}; color: white; border: 1px solid {ACCENT_DARK}; font-weight: 600;
}}
QPushButton#primary:hover {{ background: {ACCENT_DARK}; }}
QPushButton#preset {{ border-radius: 14px; padding: 4px 12px; }}
QFrame#card {{ border-radius: 12px; border: 1px solid {LINE}; }}
QLabel#cardLabel {{ color: {MUTED}; font-size: 12px; font-weight: 600; }}
QLabel#cardValue {{ font-size: 22px; font-weight: 700; }}
QFrame#emptyState {{
    background: {PANEL}; border: 1px dashed #d5cdc0; border-radius: 12px;
}}
QLabel#emptyTitle {{ font-size: 17px; font-weight: 700; }}
QFrame#companyCard {{ background: {PANEL}; border: 1px solid {LINE}; border-radius: 12px; }}
QTableWidget {{
    background: {PANEL}; border: 1px solid {LINE}; border-radius: 8px;
    gridline-color: #f0ebe3; alternate-background-color: #fcfaf6;
    selection-background-color: #fde3d6; selection-color: {INK};
}}
QHeaderView {{ background: #f3eee6; border: none; }}
QHeaderView::section {{
    background: #f3eee6; color: {INK}; border: none; border-bottom: 1px solid {LINE};
    padding: 6px 8px; font-weight: 600;
}}
QComboBox, QDateEdit, QSpinBox, QLineEdit {{
    background: {PANEL}; border: 1px solid #d5cdc0; border-radius: 6px; padding: 4px 8px;
}}
QToolBar {{ background: transparent; border: none; }}
QToolBar#chartToolbar {{ background: #f3eee6; border-radius: 8px; padding: 2px; }}
QStatusBar {{ background: {PANEL}; color: {MUTED}; border-top: 1px solid {LINE}; }}
"""
"""Style sheet applied to the main window (and inherited by its dialogs)."""
