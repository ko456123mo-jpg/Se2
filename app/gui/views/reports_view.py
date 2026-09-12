"""Report generation and listing view."""
from __future__ import annotations

from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (QCheckBox, QComboBox, QHBoxLayout, QPushButton,
                               QVBoxLayout)

from app.gui.views.base import BaseView
from app.gui.widgets import SectionHeader, build_table, _fill_table
from app.modules.reports import service as reports


class ReportsView(BaseView):
    title = "Reports"
    icon = "reports"

    def __init__(self, mw):
        super().__init__(mw)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 12)
        layout.addWidget(SectionHeader(
            "Reports", "Branded investigation reports in PDF, HTML and JSON. Each report "
                       "is hashed and registered against the case."))

        controls = QHBoxLayout()
        self.fmt_pdf = QCheckBox("PDF")
        self.fmt_pdf.setChecked(True)
        self.fmt_html = QCheckBox("HTML")
        self.fmt_html.setChecked(True)
        self.fmt_json = QCheckBox("JSON")
        self.fmt_json.setChecked(True)
        self.theme_box = QComboBox()
        self.theme_box.addItems(["light", "dark"])
        generate = QPushButton("Generate report")
        generate.setProperty("primary", "true")
        generate.clicked.connect(self._generate)
        open_button = QPushButton("Open file")
        open_button.clicked.connect(self._open)
        controls.addWidget(self.fmt_pdf)
        controls.addWidget(self.fmt_html)
        controls.addWidget(self.fmt_json)
        controls.addWidget(self.theme_box)
        controls.addStretch(1)
        controls.addWidget(generate)
        controls.addWidget(open_button)
        layout.addLayout(controls)

        self.table = build_table(["ID", "Format", "Bytes", "SHA-256", "Path", "Created"], [])
        layout.addWidget(self.table, 1)

    def _generate(self) -> None:
        if not self.case_id():
            self.notify("Select or create a case first", "warn")
            return
        formats = []
        if self.fmt_pdf.isChecked():
            formats.append("pdf")
        if self.fmt_html.isChecked():
            formats.append("html")
        if self.fmt_json.isChecked():
            formats.append("json")
        if not formats:
            self.notify("Choose at least one format", "warn")
            return
        theme = self.theme_box.currentText()
        self.run(reports.generate, self._generated, None, self.case_id(),
                 tuple(formats), "", theme)

    def _generated(self, outputs) -> None:
        for record in outputs:
            self.notify(f"{record['format'].upper()} report written: "
                        f"{record['path'].split('/')[-1]}", "ok")
        self.refresh()

    def _open(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        path = self.table.item(row, 4).text()
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def refresh(self) -> None:
        rows = reports.list_reports(self.case_id())
        import os

        _fill_table(self.table, [], [
            [r["id"], r["fmt"], os.path.getsize(r["path"])
             if os.path.exists(r["path"]) else "?", (r["sha256"] or "")[:16],
             r["path"], r["created"]]
            for r in rows])
