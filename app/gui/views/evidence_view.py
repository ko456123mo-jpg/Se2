"""Evidence management: import, list, verify integrity, working copies."""
from __future__ import annotations

from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLineEdit, QPushButton,
                               QVBoxLayout)

from app.gui.views.base import BaseView
from app.gui.widgets import SectionHeader, build_table, _fill_table
from app.modules.evidence import service as evidence


class EvidenceView(BaseView):
    title = "Evidence"
    icon = "evidence"

    def __init__(self, mw):
        super().__init__(mw)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 12)
        layout.addWidget(SectionHeader(
            "Evidence", "Original evidence is copied in and treated as immutable; all "
                        "operations run on working/derived copies and are hash-verified."))

        controls = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search evidence...")
        self.search.textChanged.connect(lambda _: self.refresh())
        import_button = QPushButton("Import evidence")
        import_button.setProperty("primary", "true")
        import_button.clicked.connect(self._import)
        verify_button = QPushButton("Verify integrity")
        verify_button.clicked.connect(self._verify)
        copy_button = QPushButton("Working copy")
        copy_button.clicked.connect(self._working_copy)
        controls.addWidget(self.search, 1)
        for button in (import_button, verify_button, copy_button):
            controls.addWidget(button)
        layout.addLayout(controls)

        self.table = build_table(
            ["ID", "Case", "Name", "Kind", "Size", "MIME", "SHA-256", "Status", "Imported"], [])
        layout.addWidget(self.table, 1)
        self.detail = QLineEdit()
        self.detail.setReadOnly(True)
        self.detail.setPlaceholderText("Select a row to see the full path")
        layout.addWidget(self.detail)
        self.table.itemSelectionChanged.connect(self._show_path)

    def _show_path(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.detail.setText(self.table.item(row, 10).text() if \
                                self.table.columnCount() > 10 else "")

    def _import(self) -> None:
        if not self.case_id():
            self.notify("Select or create a case first", "warn")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Select evidence file")
        if not path:
            return
        self.run(evidence.import_file, self._imported,
                 None, self.case_id(), path)

    def _imported(self, record) -> None:
        self.notify(f"Imported '{record['name']}' sha256={record['sha256'][:12]}...", "ok")
        self.refresh()

    def _selected_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        return int(self.table.item(row, 0).text())

    def _verify(self) -> None:
        evidence_id = self._selected_id()
        if evidence_id is None:
            return
        self.run(evidence.verify_integrity, self._verified, None, evidence_id)

    def _verified(self, result) -> None:
        level = "ok" if result["match"] else "error"
        self.notify(result["assessment"], level)
        self.refresh()

    def _working_copy(self) -> None:
        evidence_id = self._selected_id()
        if evidence_id is None:
            return
        self.run(evidence.working_copy, self._copied, None, evidence_id)

    def _copied(self, result) -> None:
        self.notify(f"Working copy created at {result['path']}", "ok")
        self.refresh()

    def refresh(self) -> None:
        rows = evidence.list_evidence(self.case_id(), search=self.search.text())
        data_rows = []
        for e in rows:
            data_rows.append([e["id"], e["case_id"], e["name"], e["kind"], e["size"],
                              e["mime"], (e["sha256"] or "")[:20] + "...", e["status"],
                              e["created"]])
        self.table.setRowCount(0)
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Case", "Name", "Kind", "Size", "MIME", "SHA-256", "Status",
             "Imported", "Path"])
        _fill_table(self.table, [], [])
        self.table.setRowCount(len(data_rows))
        for row_index, e in enumerate(rows):
            values = [e["id"], e["case_id"], e["name"], e["kind"], e["size"], e["mime"],
                      (e["sha256"] or "")[:20] + "...", e["status"], e["created"], e["path"]]
            for col_index, value in enumerate(values):
                from PySide6.QtWidgets import QTableWidgetItem

                self.table.setItem(row_index, col_index, QTableWidgetItem(str(value)))
