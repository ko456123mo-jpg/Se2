"""Modal dialogs: case creation, finding creation, safe confirmations."""
from __future__ import annotations

from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                               QLineEdit, QMessageBox, QPlainTextEdit, QVBoxLayout)

from app.core.constants import Severity


class CaseDialog(QDialog):
    def __init__(self, parent=None, existing: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("New Investigation Case")
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.title = QLineEdit()
        self.description = QPlainTextEdit()
        self.description.setMaximumHeight(90)
        self.investigator = QLineEdit()
        self.tags = QLineEdit()
        if existing:
            self.title.setText(existing.get("title", ""))
            self.description.setPlainText(existing.get("description", ""))
            self.investigator.setText(existing.get("investigator", ""))
            self.tags.setText(existing.get("tags", ""))
        form.addRow("Title *", self.title)
        form.addRow("Description", self.description)
        form.addRow("Investigator", self.investigator)
        form.addRow("Tags", self.tags)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> dict:
        return {"title": self.title.text().strip(),
                "description": self.description.toPlainText().strip(),
                "investigator": self.investigator.text().strip(),
                "tags": self.tags.text().strip()}


class FindingDialog(QDialog):
    def __init__(self, parent=None, evidence_ref: str = ""):
        super().__init__(parent)
        self.setWindowTitle("New Finding")
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.title = QLineEdit()
        self.category = QLineEdit()
        self.severity = QComboBox()
        self.severity.addItems(Severity.ALL)
        self.severity.setCurrentText(Severity.MEDIUM)
        self.confidence = QComboBox()
        self.confidence.addItems(["Low", "Medium", "High"])
        self.indicator = QLineEdit()
        self.evidence_ref = QLineEdit(evidence_ref)
        self.description = QPlainTextEdit()
        self.description.setMaximumHeight(110)
        form.addRow("Title *", self.title)
        form.addRow("Category", self.category)
        form.addRow("Severity", self.severity)
        form.addRow("Confidence", self.confidence)
        form.addRow("Indicator", self.indicator)
        form.addRow("Evidence ref", self.evidence_ref)
        form.addRow("Description", self.description)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> dict:
        return {"title": self.title.text().strip(),
                "category": self.category.text().strip() or "Forensics",
                "severity": self.severity.currentText(),
                "confidence": self.confidence.currentText(),
                "indicator": self.indicator.text().strip(),
                "evidence_ref": self.evidence_ref.text().strip(),
                "description": self.description.toPlainText().strip()}


def confirm(parent, title: str, message: str) -> bool:
    result = QMessageBox.question(parent, title, message,
                                  QMessageBox.StandardButton.Yes
                                  | QMessageBox.StandardButton.No)
    return result == QMessageBox.StandardButton.Yes


def error(parent, title: str, message: str) -> None:
    QMessageBox.critical(parent, title, message)


def info(parent, title: str, message: str) -> None:
    QMessageBox.information(parent, title, message)
