"""Dark palette matching kevctl's terminal aesthetic (desaturated accents, no pure-white fills)."""
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

BG = "#1b1d21"
PANEL = "#232630"
PANEL_ALT = "#292c38"
BORDER = "#3a3f4d"
TEXT = "#e4e6ec"
DIM = "#8b90a0"
ACCENT = "#3fc7d6"
HEAD = "#4fa8f0"
OK = "#4fbf6c"
WARN = "#dcae4b"
BAD = "#e2635c"

STYLESHEET = f"""
* {{ font-size: 13px; }}
QWidget {{ background-color: {BG}; color: {TEXT}; }}
QMainWindow, QDialog {{ background-color: {BG}; }}

QTabWidget::pane {{ border: 1px solid {BORDER}; background: {PANEL}; border-radius: 6px; top: -1px; }}
QTabBar::tab {{
    background: {BG}; color: {DIM}; padding: 8px 16px; border: 1px solid {BORDER};
    border-bottom: none; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px;
}}
QTabBar::tab:selected {{ background: {PANEL}; color: {TEXT}; border-color: {ACCENT}; }}
QTabBar::tab:hover {{ color: {TEXT}; }}

QGroupBox {{
    border: 1px solid {BORDER}; border-radius: 6px; margin-top: 10px; padding-top: 10px;
    color: {HEAD}; font-weight: 600;
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}

QPushButton {{
    background: {PANEL_ALT}; border: 1px solid {BORDER}; border-radius: 5px; padding: 6px 14px; color: {TEXT};
}}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:pressed {{ background: {BG}; }}
QPushButton:disabled {{ color: {DIM}; border-color: {BORDER}; }}
QPushButton#primary {{ background: {ACCENT}; color: #08202a; font-weight: 600; border: none; }}
QPushButton#primary:hover {{ background: #57d4e1; }}
QPushButton#danger {{ background: {BAD}; color: #2a0a08; font-weight: 600; border: none; }}
QPushButton#danger:hover {{ background: #ea8580; }}

QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {BG}; border: 1px solid {BORDER}; border-radius: 4px; padding: 4px 6px; color: {TEXT};
    selection-background-color: {ACCENT}; selection-color: #08202a;
}}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; }}

QPlainTextEdit#console {{
    background: #101115; font-family: "JetBrains Mono", "DejaVu Sans Mono", monospace;
    color: #c7ccd6; border: 1px solid {BORDER};
}}

QTreeView, QTableView, QListWidget {{
    background: {BG}; alternate-background-color: {PANEL}; border: 1px solid {BORDER};
    border-radius: 4px; gridline-color: {BORDER};
}}
QTreeView::item:selected, QTableView::item:selected, QListWidget::item:selected {{ background: {ACCENT}; color: #08202a; }}
QHeaderView::section {{
    background: {PANEL_ALT}; color: {HEAD}; padding: 5px; border: none; border-bottom: 1px solid {BORDER};
}}

QLabel[role="dim"] {{ color: {DIM}; }}
QLabel[role="ok"] {{ color: {OK}; font-weight: 600; }}
QLabel[role="warn"] {{ color: {WARN}; font-weight: 600; }}
QLabel[role="bad"] {{ color: {BAD}; font-weight: 600; }}
QLabel[role="accent"] {{ color: {ACCENT}; font-weight: 600; }}

QScrollBar:vertical {{ background: {BG}; width: 12px; }}
QScrollBar::handle:vertical {{ background: {PANEL_ALT}; border-radius: 5px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: {BORDER}; }}
QScrollBar:horizontal {{ background: {BG}; height: 12px; }}
QScrollBar::handle:horizontal {{ background: {PANEL_ALT}; border-radius: 5px; min-width: 24px; }}

QSplitter::handle {{ background: {BORDER}; }}
QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid {BORDER}; border-radius: 3px; background: {BG}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; }}
"""


def apply(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(BG))
    palette.setColor(QPalette.WindowText, QColor(TEXT))
    palette.setColor(QPalette.Base, QColor(BG))
    palette.setColor(QPalette.AlternateBase, QColor(PANEL))
    palette.setColor(QPalette.Text, QColor(TEXT))
    palette.setColor(QPalette.Button, QColor(PANEL_ALT))
    palette.setColor(QPalette.ButtonText, QColor(TEXT))
    palette.setColor(QPalette.Highlight, QColor(ACCENT))
    palette.setColor(QPalette.HighlightedText, QColor("#08202a"))
    palette.setColor(QPalette.ToolTipBase, QColor(PANEL))
    palette.setColor(QPalette.ToolTipText, QColor(TEXT))
    palette.setColor(QPalette.PlaceholderText, QColor(DIM))
    app.setPalette(palette)
    app.setStyleSheet(STYLESHEET)
