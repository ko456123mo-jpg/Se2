"""Dashboard: real metrics, distributions, recent activity, tool health."""
from __future__ import annotations

from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QSplitter, QVBoxLayout, QWidget)

from app.modules.dashboard import service as dashboard
from app.gui.views.base import BaseView
from app.gui.widgets import Card, SectionHeader, build_table


class DashboardView(BaseView):
    title = "Dashboard"
    icon = "dashboard"

    def __init__(self, mw):
        super().__init__(mw)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 12)
        layout.addWidget(SectionHeader(
            "Dashboard", "Live overview of the investigation database. Every figure "
                         "below is computed from stored records - nothing is hard-coded."))

        cards = QGridLayout()
        cards.setSpacing(10)
        self.cards = {}
        labels = ["cases", "cases_open", "evidence", "files_analyzed", "findings",
                  "critical", "reports", "hidden_data_detected", "hash_verifications",
                  "tool_executions"]
        for index, key in enumerate(labels):
            card = Card(self._card_label(key), "0")
            self.cards[key] = card
            cards.addWidget(card, index // 5, index % 5)
        layout.addLayout(cards)

        splitter = QSplitter()
        left = self._recent_widget()
        right = self._distribution_widget()
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([680, 480])
        layout.addWidget(splitter, 1)

    @staticmethod
    def _card_label(key: str) -> str:
        return {
            "cases": "Cases", "cases_open": "Open Cases", "evidence": "Evidence Items",
            "files_analyzed": "Files Analyzed", "findings": "Findings",
            "critical": "Critical Findings", "reports": "Reports",
            "hidden_data_detected": "Hidden Data Detected",
            "hash_verifications": "Hash Verifications",
            "tool_executions": "Tool Executions",
        }[key]

    def _recent_widget(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 8, 0)
        self.recent_cases = build_table(["#", "Number", "Title", "Status", "Evidence"], [])
        self.recent_findings = build_table(["ID", "Severity", "Category", "Title"], [])
        self.recent_activity = build_table(["Time", "Action", "Module", "Status"], [])
        for label, table in (("Recent cases", self.recent_cases),
                             ("Recent findings", self.recent_findings),
                             ("Recent activity", self.recent_activity)):
            heading = QLabel(label)
            heading.setObjectName("h2")
            layout.addWidget(heading)
            layout.addWidget(table)
        return widget

    def _distribution_widget(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 0, 0, 0)
        heading = QLabel("Severity distribution")
        heading.setObjectName("h2")
        layout.addWidget(heading)
        self.severity_table = build_table(["Severity", "Count"], [])
        layout.addWidget(self.severity_table)
        heading2 = QLabel("Analysis distribution")
        heading2.setObjectName("h2")
        layout.addWidget(heading2)
        self.analysis_table = build_table(["Analysis type", "Count"], [])
        layout.addWidget(self.analysis_table)
        heading3 = QLabel("Tool health")
        heading3.setObjectName("h2")
        layout.addWidget(heading3)
        self.tools_table = build_table(["Tool", "Status"], [])
        layout.addWidget(self.tools_table)
        layout.addStretch(1)
        return widget

    def refresh(self) -> None:
        data = dashboard.dashboard()
        critical = sum(1 for f in data["findings_by_severity"]
                       for name, count in [(f, data["findings_by_severity"][f])]
                       if name in ("Critical",)) or data["findings_by_severity"].get("Critical", 0)
        values = {
            "cases": data["cases"], "cases_open": data["cases_open"],
            "evidence": data["evidence"], "files_analyzed": data["files_analyzed"],
            "findings": data["findings"],
            "critical": data["findings_by_severity"].get("Critical", 0),
            "reports": data["reports"],
            "hidden_data_detected": data["hidden_data_detected"],
            "hash_verifications": data["hash_verifications"],
            "tool_executions": data["tool_executions"],
        }
        for key, card in self.cards.items():
            card.set_value(str(values[key]))

        from app.gui.widgets import _fill_table

        _fill_table(self.recent_cases, [], [
            [c["id"], c["number"], c["title"], c["status"], c["evidence_count"]]
            for c in data["recent"]["cases"]])
        _fill_table(self.recent_findings, [], [
            [f["id"], f["severity"], f["category"], f["title"]]
            for f in data["recent"]["findings"]])
        _fill_table(self.recent_activity, [], [
            [l["ts"], l["action"], l["module"], l["status"]]
            for l in data["recent"]["logs"][:8]])
        _fill_table(self.severity_table, [], [
            [name, count] for name, count in
            sorted(data["findings_by_severity"].items())])
        _fill_table(self.analysis_table, [], [
            [name, count] for name, count in
            sorted(data["analyses_by_kind"].items())])
        _fill_table(self.tools_table, [], [
            [r["name"], "AVAILABLE" if r["available"] else "UNAVAILABLE"]
            for r in data["tools"]["rows"]])
