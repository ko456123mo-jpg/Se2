"""Findings management view."""
from __future__ import annotations

from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLineEdit, QPushButton,
                               QVBoxLayout)

from app.gui import dialogs
from app.gui.views.base import BaseView
from app.gui.widgets import SectionHeader, build_table, _fill_table
from app.modules.findings import service as findings


class FindingsView(BaseView):
    title = "Findings"
    icon = "findings"

    def __init__(self, mw):
        super().__init__(mw)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 12)
        layout.addWidget(SectionHeader(
            "Findings", "Record conclusions with severity, confidence and evidence "
                        "references. Every finding cites its supporting indicator."))

        controls = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search findings...")
        self.search.textChanged.connect(lambda _: self.refresh())
        self.severity_filter = QComboBox()
        self.severity_filter.addItems(["All", "Informational", "Low", "Medium",
                                       "High", "Critical"])
        self.severity_filter.currentTextChanged.connect(lambda _: self.refresh())
        new_button = QPushButton("+ New finding")
        new_button.setProperty("primary", "true")
        new_button.clicked.connect(self._new_finding)
        delete_button = QPushButton("Delete")
        delete_button.clicked.connect(self._delete_finding)
        controls.addWidget(self.search, 1)
        controls.addWidget(self.severity_filter)
        controls.addWidget(new_button)
        controls.addWidget(delete_button)
        layout.addLayout(controls)

        self.table = build_table(
            ["ID", "Severity", "Category", "Title", "Confidence", "Investigator",
             "Created"], [])
        layout.addWidget(self.table, 1)

    def _new_finding(self) -> None:
        if not self.case_id():
            self.notify("Select or create a case first", "warn")
            return
        dialog = dialogs.FindingDialog(self)
        if dialog.exec():
            data = dialog.values()
            if not data["title"]:
                self.notify("Finding title is required", "error")
                return
            finding = findings.create(
                self.case_id(), data["category"], data["severity"], data["title"],
                data["description"], data["indicator"], data["evidence_ref"],
                data["confidence"])
            self.notify(f"Finding #{finding['id']} recorded [{finding['severity']}]",
                        "ok")
            self.refresh()

    def _delete_finding(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        finding_id = int(self.table.item(row, 0).text())
        if dialogs.confirm(self, "Delete finding", "Delete this finding?"):
            findings.delete(finding_id)
            self.notify("Finding deleted", "warn")
            self.refresh()

    def refresh(self) -> None:
        severity = self.severity_filter.currentText()
        severity = "" if severity == "All" else severity
        rows = findings.list_findings(self.case_id(), severity=severity,
                                      search=self.search.text())
        _fill_table(self.table, [], [
            [f["id"], f["severity"], f["category"], f["title"], f["confidence"],
             f["investigator"], f["created"]]
            for f in rows])
