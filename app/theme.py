"""Visual theme of the Cutsheet Generator app: palette, fonts and the application style sheet.

Presentation only. Widgets keep their names, texts and signals; the style sheet picks them up by class, object name
(card, partTitle, primary, ...) and dynamic properties (invalid). Fonts are the ones Windows 11 ships (Bahnschrift for
headings, Segoe UI for body, Cascadia Mono for the log), so nothing is bundled; Qt falls back to the system font elsewhere.
"""
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget

ICON_PATH = Path(__file__).resolve().parent / "assets" / "cutsheet.ico"
APP_ID = "CutsheetRepro.CutsheetGenerator"
CHEVRON = (Path(__file__).resolve().parent / "assets" / "chevron.svg").as_posix()      # the combo box arrow


def app_icon() -> QIcon:
    """The application icon (built by tools/make_icon.py); an empty icon when the file is missing."""
    return QIcon(str(ICON_PATH)) if ICON_PATH.is_file() else QIcon()

# workshop palette: drafting-paper greys, a dark slate rail, one dark warm red for the main action, teal for focus
INK = "#17232B"
SLATE = "#1C2A32"
SLATE_HI = "#26373F"
SLATE_TEXT = "#C9D5D9"
SLATE_MUTED = "#7F939B"
PAPER = "#EDF0EF"
CARD = "#FFFFFF"
LINE = "#D3D9DB"
MUTED = "#5E6E75"
ACCENT = "#A5473D"          # dark, soft warm red: the main action and the selection markers
ACCENT_HI = "#B85A4F"
ACCENT_LO = "#8A372F"
ACCENT_TINT = "#F7ECE9"
ACCENT_INK = "#5A2B26"
TEAL = "#1F7A6D"
ERROR = "#B3261E"

HEAD_FONT = '"Bahnschrift", "Segoe UI Semibold", "Segoe UI"'
BODY_FONT = '"Segoe UI Variable Text", "Segoe UI"'
MONO_FONT = '"Cascadia Mono", "Consolas", monospace'

STYLESHEET = f"""
QWidget {{ font-family: {BODY_FONT}; font-size: 10pt; color: {INK}; }}
QMainWindow, QMainWindow > QWidget {{ background: {PAPER}; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
QToolTip {{ background: {INK}; color: #fff; border: none; padding: 4px 6px; }}

/* ---- tabs: a header strip, selected tab marked by an amber underline ---- */
QTabWidget::pane {{ border: none; border-top: 1px solid {LINE}; background: {PAPER}; }}
QTabWidget::tab-bar {{ left: 8px; }}
QTabBar {{ background: transparent; }}
QTabBar::tab {{ font-family: {HEAD_FONT}; font-size: 11pt; color: {MUTED}; padding: 10px 18px 8px 18px;
               margin-right: 4px; border: none; border-bottom: 3px solid transparent; background: transparent; }}
QTabBar::tab:hover {{ color: {INK}; }}
QTabBar::tab:selected {{ color: {INK}; border-bottom: 3px solid {ACCENT}; }}
QLabel#brand {{ font-family: {HEAD_FONT}; font-size: 13pt; letter-spacing: 1px; color: {INK}; padding: 0 18px 0 16px; }}

/* ---- parts rail ---- */
QListWidget#partRail {{ background: {SLATE}; color: {SLATE_TEXT}; border: none; border-radius: 8px; padding: 8px 6px;
                       outline: 0; }}
QListWidget#partRail::item {{ padding: 8px 12px; margin: 1px 0; border-radius: 5px; border-left: 3px solid transparent; }}
QListWidget#partRail::item:hover {{ background: {SLATE_HI}; }}
QListWidget#partRail::item:selected {{ background: {SLATE_HI}; color: #fff; border-left: 3px solid {ACCENT}; }}

/* ---- cards and titles ---- */
QFrame#card {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 8px; }}
QFrame#card QLabel {{ background: transparent; }}
QLabel#partTitle {{ font-family: {HEAD_FONT}; font-size: 17pt; color: {INK}; }}
QLabel#partGroup {{ color: {MUTED}; font-size: 9.5pt; }}
QFrame#rule {{ background: {LINE}; border: none; max-height: 1px; min-height: 1px; }}
QLabel#hint {{ background: {ACCENT_TINT}; color: {ACCENT_INK}; border: none; border-left: 4px solid {ACCENT};
              border-radius: 3px; padding: 9px 12px; }}
QLabel#fieldError {{ color: {ERROR}; font-size: 9pt; }}
QLabel#formSummary {{ color: {ERROR}; font-size: 9.5pt; }}
QLabel#fieldLabel {{ color: {MUTED}; }}

/* ---- table of pieces (Drawer Blocks) ---- */
QTableWidget#pieceTable {{ background: #fff; border: 1px solid {LINE}; border-radius: 5px; gridline-color: {LINE};
                          selection-background-color: {ACCENT_TINT}; selection-color: {INK}; }}
QTableWidget#pieceTable QHeaderView::section {{ background: {SLATE}; color: {SLATE_TEXT}; border: none; padding: 6px 8px; }}
QLabel#pieceTotal {{ color: {MUTED}; }}

/* ---- inputs ---- */
QLineEdit, QComboBox {{ background: #fff; border: 1px solid #BAC4C8; border-radius: 5px; padding: 5px 8px;
                       min-height: 20px; selection-background-color: {TEAL}; selection-color: #fff; }}
QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: center right; width: 26px; border: none;
                       border-top-right-radius: 5px; border-bottom-right-radius: 5px; background: transparent; }}
QComboBox::drop-down:hover {{ background: #D5DCDF; }}
QComboBox::down-arrow {{ image: url({CHEVRON}); width: 12px; height: 12px; }}
QLineEdit:hover, QComboBox:hover {{ border-color: #8FA0A6; }}
QLineEdit:focus, QComboBox:focus {{ border: 1px solid {TEAL}; background: #FAFFFE; }}
QLineEdit[invalid="true"], QComboBox[invalid="true"] {{ border: 1px solid {ERROR}; background: #FFF8F7; }}
QComboBox QAbstractItemView {{ background: #fff; border: 1px solid {LINE}; selection-background-color: {TEAL};
                              selection-color: #fff; outline: 0; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid #8FA0A6; border-radius: 4px; background: #fff; }}
QCheckBox::indicator:hover {{ border-color: {TEAL}; }}
QCheckBox::indicator:checked {{ background: {TEAL}; border: 1px solid {TEAL}; }}
QCheckBox:focus {{ outline: none; }}

/* ---- collapsible "Advanced" ---- */
QToolButton#sectionToggle {{ border: none; background: transparent; color: {TEAL}; font-family: {HEAD_FONT};
                            font-size: 10.5pt; padding: 4px 2px; }}
QToolButton#sectionToggle:hover {{ color: {INK}; }}

/* ---- buttons ---- */
QPushButton {{ background: #fff; color: {INK}; border: 1px solid #AEBAC0; border-radius: 6px; padding: 7px 16px;
              min-height: 20px; }}
QPushButton:hover {{ background: #F3F6F6; border-color: #7F939B; }}
QPushButton:pressed {{ background: #E4E9EA; }}
QPushButton:disabled {{ color: #9AA8AD; background: #F1F3F3; border-color: {LINE}; }}
QPushButton#primary {{ background: {ACCENT}; color: #fff; border: 1px solid {ACCENT_LO}; font-family: {HEAD_FONT};
                      font-size: 11pt; padding: 8px 30px; }}
QPushButton#primary:hover {{ background: {ACCENT_HI}; }}
QPushButton#primary:pressed {{ background: {ACCENT_LO}; }}
QPushButton#primary:disabled {{ background: #E8DEDB; color: #A89591; border-color: #DACDC9; }}
QPushButton#danger {{ color: {ERROR}; border-color: #D9A5A1; }}
QPushButton#danger:hover {{ background: #FDEDEC; border-color: {ERROR}; }}
QPushButton:focus {{ border: 1px solid {TEAL}; }}
QPushButton#primary:focus {{ border: 2px solid {TEAL}; }}

/* ---- footer ---- */
QStatusBar {{ background: {CARD}; border-top: 1px solid {LINE}; color: {INK}; }}
QStatusBar::item {{ border: none; }}
QStatusBar QLabel {{ color: {MUTED}; padding: 0 6px; }}
QStatusBar QToolButton {{ border: 1px solid transparent; border-radius: 4px; padding: 3px 8px; color: {MUTED}; }}
QStatusBar QToolButton:hover {{ border-color: {LINE}; background: #F3F6F6; color: {INK}; }}
QStatusBar QToolButton:disabled {{ color: #AAB5BA; }}
QStatusBar QPushButton {{ padding: 3px 12px; min-height: 16px; }}

/* ---- menus ---- */
QMenuBar {{ background: {CARD}; border-bottom: 1px solid {LINE}; }}
QMenuBar::item {{ padding: 5px 10px; background: transparent; }}
QMenuBar::item:selected {{ background: {PAPER}; border-radius: 4px; }}
QMenu {{ background: #fff; border: 1px solid {LINE}; padding: 4px; }}
QMenu::item {{ padding: 6px 22px; border-radius: 4px; }}
QMenu::item:selected {{ background: {TEAL}; color: #fff; }}
QMenu::item:disabled {{ color: #9AA8AD; }}

/* ---- log dock ---- */
QDockWidget {{ font-family: {HEAD_FONT}; color: {INK}; }}
QDockWidget::title {{ background: {SLATE}; color: {SLATE_TEXT}; padding: 6px 12px; text-align: left; }}
QPlainTextEdit {{ background: #121D22; color: #BFD0D4; border: none; padding: 6px 10px;
                 font-family: {MONO_FONT}; font-size: 9.5pt; selection-background-color: {TEAL}; }}

/* ---- scrollbars ---- */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #AEBAC0; border-radius: 3px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: #8FA0A6; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #AEBAC0; border-radius: 3px; min-width: 28px; }}
QMessageBox {{ background: {CARD}; }}
"""


def set_invalid(widget: QWidget, invalid: bool) -> None:
    """Mark a field for the red border in the style sheet (dynamic property, re-polished)."""
    if widget.property("invalid") == invalid:
        return
    widget.setProperty("invalid", invalid)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
