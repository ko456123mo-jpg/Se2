"""Case management with a full detail tab set."""
from __future__ import annotations

from PySide6.QtWidgets import (QComboBox, QFrame, QHBoxLayout, QHeaderView,
                               QLineEdit, QListWidget, QPushButton, QSplitter,
                               QTabWidget, QTextEdit, QVBoxLayout, QWidget)

from app.gui import dialogs
from app.gui.views.base import BaseView
from app.gui.widgets import SectionHeader, build_table, _fill_table
from app.modules.cases import service as cases
from app.modules.evidence import service as evidence
from app.modules.findings import service as findings
from app.modules.logs import service as logs
from app.modules.reports import service as reports


class CasesView(BaseView):
    title = "Cases"
    icon = "case"

    def __init__(self, mw):
        super().__init__(mw)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 12)
        layout.addWidget(SectionHeader("Cases", "Create, open, edit, close and archive "
                                                 "investigation cases."))

        splitter = QSplitter()
        splitter.addWidget(self._list_panel())
        splitter.addWidget(self._detail_panel())
        splitter.setSizes([380, 780])
        layout.addWidget(splitter, 1)

    # ---------------------------------------------------------------- list side
    def _list_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        controls = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search cases...")
        self.search.textChanged.connect(lambda _: self.refresh())
        self.status_filter = QComboBox()
        self.status_filter.addItems(["All", "Open", "Closed", "Archived"])
        self.status_filter.currentTextChanged.connect(lambda _: self.refresh())
        controls.addWidget(self.search, 1)
        controls.addWidget(self.status_filter)
        layout.addLayout(controls)

        actions = QHBoxLayout()
        new_button = QPushButton("+ New")
        new_button.setProperty("primary", "true")
        new_button.clicked.connect(self._new_case)
        edit_button = QPushButton("Edit")
        edit_button.clicked.connect(self._edit_case)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self._close_case)
        archive_button = QPushButton("Archive")
        archive_button.clicked.connect(self._archive_case)
        delete_button = QPushButton("Delete")
        delete_button.clicked.connect(self._delete_case)
        for button in (new_button, edit_button, close_button, archive_button, delete_button):
            actions.addWidget(button)
        layout.addLayout(actions)

        self.case_list = QListWidget()
        self.case_list.currentRowChanged.connect(self._select_case)
        layout.addWidget(self.case_list, 1)
        return panel

    # --------------------------------------------------------------- detail side
    def _detail_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        self.tabs = QTabWidget()
        self.overview_table = build_table(["Metric", "Value"], [])
        self.evidence_table = build_table(["ID", "Name", "Kind", "Size", "SHA-256"], [])
        self.analysis_table = build_table(["Time", "Analysis", "Tool", "Status", "Summary"], [])
        self.findings_table = build_table(["ID", "Severity", "Category", "Title", "Confidence"], [])
        self.timeline_table = build_table(["Time", "Event", "Module", "Detail"], [])
        self.logs_table = build_table(["Time", "Action", "Tool", "Status", "Result"], [])
        self.reports_table = build_table(["ID", "Format", "Path", "Created"], [])
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Case notes...")
        self.save_notes = QPushButton("Save notes")
        self.save_notes.clicked.connect(self._save_notes)

        self.tabs.addTab(self.overview_table, "Overview")
        self.tabs.addTab(self.evidence_table, "Evidence")
        self.tabs.addTab(self.analysis_table, "Analysis")
        self.tabs.addTab(self.findings_table, "Findings")
        self.tabs.addTab(self.timeline_table, "Timeline")
        self.tabs.addTab(self.logs_table, "Logs")
        self.tabs.addTab(self.reports_table, "Reports")
        notes_widget = QWidget()
        notes_layout = QVBoxLayout(notes_widget)
        notes_layout.addWidget(self.notes_edit)
        notes_layout.addWidget(self.save_notes)
        self.tabs.addTab(notes_widget, "Notes")
        layout.addWidget(self.tabs)
        return panel

    # ------------------------------------------------------------------ actions
    def _new_case(self) -> None:
        dialog = dialogs.CaseDialog(self)
        if dialog.exec():
            data = dialog.values()
            if not data["title"]:
                self.notify("Case title is required", "error")
                return
            case = cases.create(data["title"], data["description"],
                                data["investigator"], data["tags"])
            self.mw._populate_case_selector()
            self.notify(f"Case {case['number']} created", "ok")
            self.refresh()

    def _selected_id(self) -> int | None:
        row = self.case_list.currentRow()
        if row < 0:
            return None
        return self.case_list.item(row).data(32)

    def _edit_case(self) -> None:
        case_id = self._selected_id()
        if case_id is None:
            return
        case = cases.open_case(case_id)
        dialog = dialogs.CaseDialog(self, existing=case)
        if dialog.exec():
            data = dialog.values()
            cases.update(case_id, title=data["title"], description=data["description"],
                         investigator=data["investigator"], tags=data["tags"])
            self.notify("Case updated", "ok")
            self.refresh()

    def _close_case(self) -> None:
        case_id = self._selected_id()
        if case_id and dialogs.confirm(self, "Close case", "Close this case?"):
            cases.close(case_id)
            self.notify("Case closed", "ok")
            self.refresh()

    def _archive_case(self) -> None:
        case_id = self._selected_id()
        if case_id:
            cases.archive(case_id)
            self.notify("Case archived", "ok")
            self.refresh()

    def _delete_case(self) -> None:
        case_id = self._selected_id()
        if case_id and dialogs.confirm(self, "Delete case",
                                       "Delete this case and all its records?"):
            cases.delete(case_id)
            self.notify("Case deleted", "warn")
            self.refresh()

    def _save_notes(self) -> None:
        case_id = self._selected_id()
        if case_id:
            cases.update(case_id, notes=self.notes_edit.toPlainText())
            self.notify("Notes saved", "ok")

    def _select_case(self, row: int) -> None:
        case_id = self._selected_id()
        if case_id is None:
            return
        self.mw.current_case = cases.open_case(case_id)
        self._load_detail(case_id)

    # ------------------------------------------------------------------ refresh
    def refresh(self) -> None:
        status = self.status_filter.currentText()
        status = None if status == "All" else status
        rows = cases.list_cases(status=status, search=self.search.text())
        self.case_list.clear()
        for case in rows:
            from PySide6.QtWidgets import QListWidgetItem

            item = QListWidgetItem(f"{case['number']} - {case['title']} [{case['status']}]")
            item.setData(32, case["id"])
            self.case_list.addItem(item)
        if self.case_list.count():
            self.case_list.setCurrentRow(0)

    def _load_detail(self, case_id: int) -> None:
        overview = cases.overview(case_id)
        _fill_table(self.overview_table, [], [
            ["Case number", overview["case"]["number"]],
            ["Title", overview["case"]["title"]],
            ["Investigator", overview["case"]["investigator"]],
            ["Status", overview["case"]["status"]],
            ["Evidence items", overview["evidence_count"]],
            ["Analyses", overview["analysis_count"]],
            ["Extractions", overview["extraction_count"]],
            ["Successful extractions", overview["successful_extractions"]],
            ["Findings", overview["finding_count"]],
            ["Log entries", overview["log_count"]],
            ["Reports", overview["report_count"]],
        ])
        _fill_table(self.evidence_table, [], [
            [e["id"], e["name"], e["kind"], e["size"], (e["sha256"] or "")[:24]]
            for e in overview["evidence"]])
        from app.storage.database import get_db

        _fill_table(self.analysis_table, [], [
            [a["created"], a["kind"], a["tool"], a["status"], a["summary"][:80]]
            for a in get_db().list_analyses(case_id)])
        _fill_table(self.findings_table, [], [
            [f["id"], f["severity"], f["category"], f["title"], f["confidence"]]
            for f in findings.list_findings(case_id)])
        _fill_table(self.timeline_table, [], [
            [t["time"], t["type"], t["module"], (t["detail"] or "")[:90]]
            for t in overview["timeline"][:60]])
        _fill_table(self.logs_table, [], [
            [l["ts"], l["action"], l["tool"], l["status"], (l["result"] or "")[:70]]
            for l in logs.list_logs(case_id)])
        _fill_table(self.reports_table, [], [
            [r["id"], r["fmt"], r["path"], r["created"]]
            for r in reports.list_reports(case_id)])
        self.notes_edit.setPlainText(overview["case"].get("notes") or "")
