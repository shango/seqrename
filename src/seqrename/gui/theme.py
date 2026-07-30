"""Design tokens and stylesheet.

One dark theme, tuned for Windows 11: deep neutral surfaces, a single blue
accent, 8px geometry, and Segoe UI Variable where it exists.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

ASSETS = Path(__file__).parent / "assets"
CHECK_ICON = (ASSETS / "check.svg").as_posix()
CHEVRON_ICON = (ASSETS / "chevron-down.svg").as_posix()
CARET_UP_ICON = (ASSETS / "caret-up.svg").as_posix()
CARET_DOWN_ICON = (ASSETS / "caret-down.svg").as_posix()
RADIO_DOT_ICON = (ASSETS / "radio-dot.svg").as_posix()

# -- tokens --------------------------------------------------------------

BG = "#0e1014"
SURFACE = "#15181e"
SURFACE_2 = "#1b1f27"
SURFACE_3 = "#222732"
STROKE = "#272c37"
STROKE_STRONG = "#333a48"

TEXT = "#e9ecf3"
TEXT_DIM = "#98a1b3"
TEXT_FAINT = "#6a7386"

ACCENT = "#4c8dff"
ACCENT_HOVER = "#5f9aff"
ACCENT_PRESS = "#3f7ae6"
ACCENT_SOFT = "#1c2c4d"

OK = "#3ecf8e"
WARN = "#f0b429"
DANGER = "#ff6b6b"
DANGER_SOFT = "#3a1f22"

RADIUS = 8

UI_FONTS = ["Segoe UI Variable Text", "Segoe UI", "Inter", "Ubuntu", "DejaVu Sans"]
MONO_FONTS = ["Cascadia Mono", "Consolas", "JetBrains Mono", "DejaVu Sans Mono", "monospace"]


def _first_available(candidates: list[str], fallback: str) -> str:
    families = set(QFontDatabase.families())
    for name in candidates:
        if name in families:
            return name
    return fallback


def ui_font(size: int = 10, bold: bool = False) -> QFont:
    f = QFont(_first_available(UI_FONTS, "Sans Serif"), size)
    f.setBold(bold)
    return f


def mono_font(size: int = 10) -> QFont:
    return QFont(_first_available(MONO_FONTS, "Monospace"), size)


def color(hex_str: str, alpha: int | None = None) -> QColor:
    c = QColor(hex_str)
    if alpha is not None:
        c.setAlpha(alpha)
    return c


def apply(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setFont(ui_font(10))

    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(BG))
    pal.setColor(QPalette.WindowText, QColor(TEXT))
    pal.setColor(QPalette.Base, QColor(SURFACE))
    pal.setColor(QPalette.AlternateBase, QColor(SURFACE_2))
    pal.setColor(QPalette.Text, QColor(TEXT))
    pal.setColor(QPalette.Button, QColor(SURFACE_2))
    pal.setColor(QPalette.ButtonText, QColor(TEXT))
    pal.setColor(QPalette.Highlight, QColor(ACCENT))
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ToolTipBase, QColor(SURFACE_3))
    pal.setColor(QPalette.ToolTipText, QColor(TEXT))
    pal.setColor(QPalette.PlaceholderText, QColor(TEXT_FAINT))
    pal.setColor(QPalette.Disabled, QPalette.Text, QColor(TEXT_FAINT))
    pal.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(TEXT_FAINT))
    app.setPalette(pal)
    app.setStyleSheet(STYLESHEET)


STYLESHEET = f"""
QWidget {{
    color: {TEXT};
    background: transparent;
}}
QMainWindow, #Root {{ background: {BG}; }}

QToolTip {{
    background: {SURFACE_3};
    color: {TEXT};
    border: 1px solid {STROKE_STRONG};
    border-radius: 6px;
    padding: 5px 8px;
}}

/* -- structure -- */
#Header {{
    background: {SURFACE};
    border-bottom: 1px solid {STROKE};
}}
#Footer {{
    background: {SURFACE};
    border-top: 1px solid {STROKE};
}}
#Panel {{
    background: {SURFACE};
    border: 1px solid {STROKE};
    border-radius: {RADIUS}px;
}}
#Card {{
    background: {SURFACE_2};
    border: 1px solid {STROKE};
    border-radius: {RADIUS}px;
}}
#PanelTitle {{
    color: {TEXT_FAINT};
    font-size: 10px;
    font-weight: 700;
}}
#CardTitle {{
    color: {TEXT_DIM};
    font-weight: 600;
}}
#AppName {{ font-size: 14px; font-weight: 700; letter-spacing: 0.3px; }}
#Hint {{ color: {TEXT_FAINT}; }}
#Dim {{ color: {TEXT_DIM}; }}

/* -- buttons -- */
QPushButton {{
    background: {SURFACE_2};
    border: 1px solid {STROKE_STRONG};
    border-radius: {RADIUS}px;
    padding: 7px 14px;
    color: {TEXT};
}}
QPushButton:hover {{ background: {SURFACE_3}; border-color: #3d4454; }}
QPushButton:pressed {{ background: {SURFACE}; }}
QPushButton:disabled {{ color: {TEXT_FAINT}; border-color: {STROKE}; background: {SURFACE}; }}

QPushButton#Primary {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    color: #ffffff;
    font-weight: 600;
    padding: 8px 20px;
}}
QPushButton#Primary:hover {{ background: {ACCENT_HOVER}; border-color: {ACCENT_HOVER}; }}
QPushButton#Primary:pressed {{ background: {ACCENT_PRESS}; }}
QPushButton#Primary:disabled {{ background: {SURFACE_2}; border-color: {STROKE}; color: {TEXT_FAINT}; }}

QPushButton#Ghost {{
    background: transparent;
    border: 1px solid transparent;
    padding: 6px 10px;
    color: {TEXT_DIM};
}}
QPushButton#Ghost:hover {{ background: {SURFACE_2}; color: {TEXT}; }}

/* Compact ghost, for the buttons that sit inside a panel header. */
QPushButton#GhostSmall {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 3px 7px;
    color: {TEXT_FAINT};
    font-size: 11px;
}}
QPushButton#GhostSmall:hover {{ background: {SURFACE_2}; color: {TEXT}; }}
QPushButton#GhostSmall:disabled {{ color: {STROKE_STRONG}; background: transparent; }}

/* -- inputs -- */
QLineEdit, QSpinBox, QComboBox {{
    background: {SURFACE};
    border: 1px solid {STROKE_STRONG};
    border-radius: 6px;
    padding: 6px 8px;
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {ACCENT}; }}
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{
    color: {TEXT_FAINT};
    background: {SURFACE};
    border-color: {STROKE};
}}
QLineEdit#PathField {{
    background: {SURFACE_2};
    padding: 7px 10px;
}}
QLineEdit[invalid="true"] {{ border-color: {DANGER}; }}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    border: none;
    width: 22px;
}}
QComboBox::down-arrow {{
    image: url("{CHEVRON_ICON}");
    width: 12px; height: 12px;
    margin-right: 6px;
}}
QComboBox QAbstractItemView {{
    background: {SURFACE_2};
    border: 1px solid {STROKE_STRONG};
    border-radius: 6px;
    padding: 4px;
    outline: none;
    selection-background-color: {ACCENT_SOFT};
}}
QSpinBox {{ padding-right: 20px; }}
QSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    background: {SURFACE_2};
    border: none;
    border-top-right-radius: 6px;
    width: 18px;
    margin: 1px 1px 0 0;
}}
QSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    background: {SURFACE_2};
    border: none;
    border-bottom-right-radius: 6px;
    width: 18px;
    margin: 0 1px 1px 0;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{ background: {SURFACE_3}; }}
QSpinBox::up-arrow {{ image: url("{CARET_UP_ICON}"); width: 8px; height: 6px; }}
QSpinBox::down-arrow {{ image: url("{CARET_DOWN_ICON}"); width: 8px; height: 6px; }}

QCheckBox {{ spacing: 8px; color: {TEXT_DIM}; }}
QCheckBox:hover {{ color: {TEXT}; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {STROKE_STRONG};
    border-radius: 4px;
    background: {SURFACE};
}}
QCheckBox::indicator:hover {{ border-color: {ACCENT}; }}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
    image: url("{CHECK_ICON}");
}}
QCheckBox::indicator:disabled {{ border-color: {STROKE}; background: {SURFACE}; }}

QRadioButton {{ spacing: 8px; color: {TEXT_DIM}; }}
QRadioButton:hover {{ color: {TEXT}; }}
QRadioButton::indicator {{
    width: 15px; height: 15px;
    border: 1px solid {STROKE_STRONG};
    border-radius: 8px;
    background: {SURFACE};
}}
QRadioButton::indicator:checked {{
    border-color: {ACCENT};
    background: {ACCENT};
    image: url("{RADIO_DOT_ICON}");
}}

/* -- lists and tables -- */
QListView, QTableView {{
    background: transparent;
    border: none;
    outline: none;
}}
QTableView {{
    gridline-color: transparent;
    selection-background-color: {ACCENT_SOFT};
    selection-color: {TEXT};
}}
QHeaderView::section {{
    background: {SURFACE};
    color: {TEXT_FAINT};
    border: none;
    border-bottom: 1px solid {STROKE};
    padding: 7px 10px;
    font-weight: 600;
}}
QTableCornerButton::section {{ background: {SURFACE}; border: none; }}

/* -- scrollbars -- */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {STROKE_STRONG};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: #444c5e; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {STROKE_STRONG};
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QScrollArea {{ border: none; background: transparent; }}

/* -- misc -- */
QSplitter::handle {{ background: transparent; }}
QSplitter::handle:hover {{ background: {STROKE}; }}

QProgressBar {{
    background: {SURFACE_2};
    border: none;
    border-radius: 3px;
    height: 6px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}

QMenu {{
    background: {SURFACE_2};
    border: 1px solid {STROKE_STRONG};
    border-radius: 8px;
    padding: 5px;
}}
QMenu::item {{ padding: 6px 22px 6px 12px; border-radius: 5px; }}
QMenu::item:selected {{ background: {ACCENT_SOFT}; }}
QMenu::separator {{ height: 1px; background: {STROKE}; margin: 4px 8px; }}

QDialog {{ background: {BG}; }}
QTextEdit {{
    background: {SURFACE};
    border: 1px solid {STROKE};
    border-radius: 6px;
}}
"""
