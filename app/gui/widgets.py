"""Reusable professional widgets shared by every view."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QProgressBar,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from app.gui.themes import palette


class Card(QFrame):
    """A dashboard metric card."""

    def __init__(self, label: str, value: str = "0", tone: str = "kpi", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        self.value = QLabel(value)
        self.value.setObjectName(tone)
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        self.value.setFont(font)
        self.label = QLabel(label)
        self.label.setObjectName("muted")
        layout.addWidget(self.value)
        layout.addWidget(self.label)

    def set_value(self, value: str) -> None:
        self.value.setText(value)


class SectionHeader(QWidget):
    """Title + subtitle row for a view."""

    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        heading = QLabel(title)
        heading.setObjectName("h1")
        layout.addWidget(heading)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("muted")
            sub.setWordWrap(True)
            layout.addWidget(sub)


class StatusChip(QLabel):
    def __init__(self, text: str, level: str = "ok", parent=None):
        super().__init__(text, parent)
        self.set_level(level)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumWidth(90)

    def set_text(self, text: str, level: str | None = None) -> None:
        self.setText(str(text))
        if level:
            self.set_level(level)

    def set_level(self, level: str) -> None:
        if level in ("ok", "OK", "SUCCESS", "AVAILABLE", "IMPLEMENTED", "INTEGRATED"):
            self.setObjectName("badge_ok")
        elif level in ("warn", "PARTIAL", "SIMULATED", "REFERENCE", "OPTIONAL",
                       "UNAVAILABLE", "EXTERNAL"):
            self.setObjectName("badge_warn")
        else:
            self.setObjectName("badge_err")
        self.style().unpolish(self)
        self.style().polish(self)


def build_table(headers: list[str], rows: list[list], parent=None) -> QTableWidget:
    table = QTableWidget(parent)
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setAlternatingRowColors(True)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.verticalHeader().setVisible(False)
    table.setWordWrap(False)
    table.setShowGrid(False)
    _fill_table(table, headers, rows)
    return table


def _fill_table(table: QTableWidget, headers: list[str], rows: list[list]) -> None:
    table.setRowCount(len(rows))
    for row_index, row in enumerate(rows):
        for col_index, value in enumerate(row):
            item = QTableWidgetItem(str(value))
            item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter
                                  | Qt.AlignmentFlag.AlignLeft)
            table.setItem(row_index, col_index, item)
    for col_index in range(len(headers)):
        table.resizeColumnToContents(col_index)
        if table.columnWidth(col_index) > 340:
            table.setColumnWidth(col_index, 340)


class LabeledField(QWidget):
    """A label stacked above an arbitrary widget (forms)."""

    def __init__(self, label: str, widget: QWidget, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 6)
        layout.setSpacing(4)
        caption = QLabel(label)
        caption.setObjectName("muted")
        layout.addWidget(caption)
        layout.addWidget(widget)
        self.field = widget


class ProgressBox(QFrame):
    """Indeterminate / determinate progress with a status line."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("subpanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        self.status = QLabel("Idle")
        self.status.setObjectName("muted")
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        layout.addWidget(self.status)
        layout.addWidget(self.bar)
        self.setVisible(False)

    def start(self, message: str) -> None:
        self.status.setText(message)
        self.bar.setRange(0, 0)
        self.setVisible(True)

    def done(self, message: str) -> None:
        self.status.setText(message)
        self.bar.setRange(0, 1)
        self.bar.setValue(1)

    def hide_after(self) -> None:
        self.setVisible(False)


class ConsoleView(QFrame):
    """Monospace, read-only console used to show raw tool output."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("subpanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        from PySide6.QtWidgets import QPlainTextEdit

        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        font = QFont("DejaVu Sans Mono", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.text.setFont(font)
        layout.addWidget(self.text)

    def set_text(self, text: str) -> None:
        self.text.setPlainText(text or "")
