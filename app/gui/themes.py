"""Dark / light QSS themes for the StegoNexus GUI."""
from __future__ import annotations

DARK = {
    "window": "#0b1220", "panel": "#101a2e", "panel2": "#14213a", "border": "#233450",
    "text": "#e6f0fb", "muted": "#8fa6c2", "accent": "#22d3ee", "accent2": "#3b82f6",
    "ok": "#34d399", "warn": "#fbbf24", "err": "#f87171",
    "input": "#0d1727", "hover": "#1a2b47", "header": "#0d1626",
}
LIGHT = {
    "window": "#f2f6fb", "panel": "#ffffff", "panel2": "#eef3f9", "border": "#d7e1ee",
    "text": "#122234", "muted": "#5b748f", "accent": "#0891b2", "accent2": "#2563eb",
    "ok": "#059669", "warn": "#b45309", "err": "#dc2626",
    "input": "#ffffff", "hover": "#e6eef7", "header": "#fbfdff",
}


def palette(theme: str = "dark") -> dict:
    return dict(DARK if theme == "dark" else LIGHT)


def qt_palette(theme: str = "dark"):
    """A real QPalette built from the same colours as the stylesheet.

    Native widgets that the QSS does not style (menus, tooltips, disabled labels) pick
    their colours from here, so both themes stay readable.
    """
    from PySide6.QtGui import QColor, QPalette

    colours = palette(theme)
    qp = QPalette()
    qp.setColor(QPalette.ColorRole.Window, QColor(colours["window"]))
    qp.setColor(QPalette.ColorRole.WindowText, QColor(colours["text"]))
    qp.setColor(QPalette.ColorRole.Base, QColor(colours["input"]))
    qp.setColor(QPalette.ColorRole.AlternateBase, QColor(colours["panel2"]))
    qp.setColor(QPalette.ColorRole.Text, QColor(colours["text"]))
    qp.setColor(QPalette.ColorRole.Button, QColor(colours["panel"]))
    qp.setColor(QPalette.ColorRole.ButtonText, QColor(colours["text"]))
    qp.setColor(QPalette.ColorRole.Highlight, QColor(colours["accent2"]))
    qp.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    qp.setColor(QPalette.ColorRole.ToolTipBase, QColor(colours["panel2"]))
    qp.setColor(QPalette.ColorRole.ToolTipText, QColor(colours["text"]))
    qp.setColor(QPalette.ColorRole.PlaceholderText, QColor(colours["muted"]))
    qp.setColor(QPalette.ColorRole.Link, QColor(colours["accent"]))
    qp.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text,
                QColor(colours["muted"]))
    qp.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText,
                QColor(colours["muted"]))
    return qp


def stylesheet(theme: str = "dark") -> str:
    p = palette(theme)
    return f"""
    QWidget {{ background:{p['window']}; color:{p['text']};
        font-family:'DejaVu Sans','Liberation Sans',Arial,sans-serif; font-size:13px; }}
    QMainWindow, QDialog {{ background:{p['window']}; }}
    QLabel {{ background:transparent; }}
    QFrame#card, QFrame#panel {{ background:{p['panel']}; border:1px solid {p['border']};
        border-radius:10px; }}
    QFrame#subpanel {{ background:{p['panel2']}; border:1px solid {p['border']};
        border-radius:8px; }}
    QFrame#header {{ background:{p['header']}; border-bottom:1px solid {p['border']}; }}
    QFrame#sidebar {{ background:{p['panel']}; border-right:1px solid {p['border']}; }}
    QPushButton {{ background:{p['panel2']}; border:1px solid {p['border']};
        border-radius:7px; padding:6px 12px; }}
    QPushButton:hover {{ background:{p['hover']}; border-color:{p['accent']}; }}
    QPushButton:pressed {{ background:{p['accent2']}; }}
    QPushButton[primary="true"] {{ background:{p['accent2']}; color:#ffffff;
        border:none; font-weight:600; }}
    QPushButton[primary="true"]:hover {{ background:{p['accent']}; }}
    QPushButton[nav="true"] {{ background:transparent; border:none; border-radius:8px;
        text-align:left; padding:8px 12px; font-size:13px; }}
    QPushButton[nav="true"]:hover {{ background:{p['hover']}; }}
    QPushButton[nav="true"][active="true"] {{ background:{p['panel2']};
        border-left:3px solid {p['accent']}; color:{p['accent']}; font-weight:600; }}
    QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background:{p['input']}; border:1px solid {p['border']}; border-radius:7px;
        padding:5px 8px; selection-background-color:{p['accent2']}; }}
    QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{ border-color:{p['accent']}; }}
    QTableWidget, QTreeWidget, QListWidget {{ background:{p['panel']};
        alternate-background-color:{p['panel2']}; border:1px solid {p['border']};
        border-radius:8px; gridline-color:{p['border']}; }}
    QTableWidget::item:selected, QListWidget::item:selected {{
        background:{p['accent2']}; color:#ffffff; }}
    QHeaderView::section {{ background:{p['panel2']}; color:{p['muted']};
        padding:6px; border:none; border-bottom:1px solid {p['border']};
        font-weight:600; text-transform:uppercase; font-size:11px; }}
    QTabWidget::pane {{ border:1px solid {p['border']}; border-radius:8px;
        background:{p['panel']}; }}
    QTabBar::tab {{ background:{p['panel2']}; padding:7px 14px; border:none;
        border-top-left-radius:8px; border-top-right-radius:8px; margin-right:2px; }}
    QTabBar::tab:selected {{ background:{p['accent2']}; color:#ffffff; font-weight:600; }}
    QProgressBar {{ background:{p['panel2']}; border:1px solid {p['border']};
        border-radius:6px; text-align:center; }}
    QProgressBar::chunk {{ background:{p['accent']}; border-radius:5px; }}
    QScrollBar:vertical {{ background:{p['panel']}; width:10px; }}
    QScrollBar::handle:vertical {{ background:{p['border']}; border-radius:5px; }}
    QScrollBar:horizontal {{ background:{p['panel']}; height:10px; }}
    QScrollBar::handle:horizontal {{ background:{p['border']}; border-radius:5px; }}
    QStatusBar {{ background:{p['header']}; color:{p['muted']};
        border-top:1px solid {p['border']}; }}
    QGroupBox {{ border:1px solid {p['border']}; border-radius:8px; margin-top:10px;
        font-weight:600; }}
    QGroupBox::title {{ subcontrol-origin:margin; left:10px; padding:0 4px; }}
    QMenu {{ background:{p['panel']}; border:1px solid {p['border']}; }}
    QMenu::item:selected {{ background:{p['accent2']}; color:#ffffff; }}
    QLabel#h1 {{ font-size:20px; font-weight:700; }}
    QLabel#h2 {{ font-size:15px; font-weight:600; }}
    QLabel#muted {{ color:{p['muted']}; font-size:12px; }}
    QLabel#kpi {{ font-size:24px; font-weight:700; color:{p['accent']}; }}
    QLabel#badge_ok {{ color:{p['ok']}; font-weight:600; }}
    QLabel#badge_warn {{ color:{p['warn']}; font-weight:600; }}
    QLabel#badge_err {{ color:{p['err']}; font-weight:600; }}
    QSplitter::handle {{ background:{p['border']}; }}
    """
