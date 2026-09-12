"""Tool Health Center: live detection of every dependency."""
from __future__ import annotations

from PySide6.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QVBoxLayout)

from app.gui.views.base import BaseView
from app.gui.widgets import Card, SectionHeader, StatusChip, build_table, _fill_table
from app.services.tool_health import health


class ToolHealthView(BaseView):
    title = "Tool Health"
    icon = "health"

    def __init__(self, mw):
        super().__init__(mw)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 12)
        layout.addWidget(SectionHeader(
            "Tool Health", "Live availability probe for every external dependency and "
                           "Python library. Statuses are measured, never hard-coded."))

        cards = QHBoxLayout()
        self.card_total = Card("Tools tracked", "0")
        self.card_available = Card("Available", "0", "badge_ok")
        self.card_missing = Card("Missing required", "0", "badge_warn")
        for card in (self.card_total, self.card_available, self.card_missing):
            cards.addWidget(card)
        cards.addStretch(1)
        refresh = QPushButton("Re-scan")
        refresh.clicked.connect(lambda: self.refresh(force=True))
        cards.addWidget(refresh)
        layout.addLayout(cards)

        self.table = build_table(
            ["Tool", "Status", "Kind", "Version", "Path", "Used by", "Install"], [])
        layout.addWidget(self.table, 1)
        self.note = QLabel("Run a re-scan after installing or removing tools.")
        self.note.setObjectName("muted")
        layout.addWidget(self.note)

    def refresh(self, force: bool = False) -> None:
        summary = health.summary() if force else health.summary()
        if force:
            health.check_all(refresh=True)
            summary = health.summary()
        self.card_total.set_value(str(summary["total"]))
        self.card_available.set_value(str(summary["available"]))
        self.card_missing.set_value(str(len(summary["missing_required"])))
        _fill_table(self.table, [], [
            [r["name"],
             "AVAILABLE" if r["available"] else
             ("REFERENCE" if r["classification"] == "REFERENCE" else "UNAVAILABLE"),
             r["kind"], r["version"][:30], r["path"], ", ".join(r["modules"]),
             r["install"]]
            for r in summary["rows"]])
