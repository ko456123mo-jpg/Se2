"""Investigation logs view with search, status filter and export."""
from __future__ import annotations

from PySide6.QtWidgets import (QComboBox, QFileDialog, QHBoxLayout, QLineEdit,
                               QPushButton, QVBoxLayout)

from app.gui.views.base import BaseView
from app.gui.widgets import SectionHeader, build_table, _fill_table
from app.modules.logs import service as logs


class LogsView(BaseView):
    title = "Investigation Logs"
    icon = "logs"

    def __init__(self, mw):
        super().__init__(mw)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 12)
        layout.addWidget(SectionHeader(
            "Investigation Logs", "Every sensitive operation is recorded with case, "
                                  "evidence, tool, status and hash."))
        controls = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search logs...")
        self.search.textChanged.connect(lambda _: self.refresh())
        self.status_filter = QComboBox()
        self.status_filter.addItems(["All", "OK", "FAILED", "SIMULATED", "FALLBACK"])
        self.status_filter.currentTextChanged.connect(lambda _: self.refresh())
        export_csv = QPushButton("Export CSV")
        export_csv.clicked.connect(lambda: self._export("csv"))
        export_json = QPushButton("Export application log (JSON)")
        export_json.clicked.connect(lambda: self._export("json"))
        controls.addWidget(self.search, 1)
        controls.addWidget(self.status_filter)
        controls.addWidget(export_csv)
        controls.addWidget(export_json)
        layout.addLayout(controls)

        self.table = build_table(
            ["Time", "User", "Action", "Module", "Tool", "Status", "Result", "Hash"], [])
        layout.addWidget(self.table, 1)

    def _export(self, fmt: str) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export logs", f"stegonexus_logs.{fmt}",
            "Files (*.csv *.json)")
        if not path:
            return
        if fmt == "csv":
            result = logs.export_csv(path, case_id=self.case_id())
        else:
            result = logs.export_application_log(path)
        self.notify(f"Exported {result['rows'] if 'rows' in result else result['lines']} "
                    f"records to {result['path']}", "ok")

    def refresh(self) -> None:
        status = self.status_filter.currentText()
        status = "" if status == "All" else status
        rows = logs.list_logs(self.case_id(), search=self.search.text(), status=status)
        _fill_table(self.table, [], [
            [l["ts"], l["user"], l["action"], l["module"], l["tool"], l["status"],
             (l["result"] or "")[:80], (l["hash"] or "")[:16]]
            for l in rows])
