"""Extraction Center: unified log of all hide/extract operations."""
from __future__ import annotations

from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout)

from app.gui.views.base import BaseView
from app.gui.widgets import Card, SectionHeader, build_table, _fill_table
from app.modules.extraction import service as extraction


class ExtractionView(BaseView):
    title = "Extraction Center"
    icon = "extract"

    def __init__(self, mw):
        super().__init__(mw)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 12)
        layout.addWidget(SectionHeader(
            "Extraction Center", "Unified record of every hiding and extraction operation, "
                                 "with technique, engine, hash and verification status."))

        cards = QHBoxLayout()
        self.card_total = Card("Total operations", "0")
        self.card_success = Card("Successful", "0", "badge_ok")
        self.card_verified = Card("Verified", "0", "badge_ok")
        self.card_rate = Card("Success rate", "0%", "kpi")
        for card in (self.card_total, self.card_success, self.card_verified, self.card_rate):
            cards.addWidget(card)
        layout.addLayout(cards)

        controls = QHBoxLayout()
        self.technique = QComboBox()
        self.technique.addItem("All techniques")
        for key, label in extraction.TECHNIQUES.items():
            self.technique.addItem(label, key)
        self.operation = QComboBox()
        self.operation.addItems(["All operations", "hide", "extract", "strip", "send", "receive"])
        self.status = QComboBox()
        self.status.addItems(["All statuses", "SUCCESS", "FAILED", "PARTIAL", "EMPTY"])
        for box in (self.technique, self.operation, self.status):
            box.currentIndexChanged.connect(lambda _: self.refresh())
            controls.addWidget(box)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.table = build_table(
            ["ID", "Technique", "Operation", "Engine", "Status", "Verified",
             "Payload B", "Output", "Time"], [])
        layout.addWidget(self.table, 1)

    def refresh(self) -> None:
        summary = extraction.summary(self.case_id())
        self.card_total.set_value(str(summary["total"]))
        self.card_success.set_value(str(summary["by_status"].get("SUCCESS", 0)))
        self.card_verified.set_value(str(summary["verified"]))
        self.card_rate.set_value(f"{summary['success_rate']:.0%}")

        technique = self.technique.currentData() or ""
        operation = self.operation.currentText()
        operation = "" if operation == "All operations" else operation
        status = self.status.currentText()
        status = "" if status == "All statuses" else status
        rows = extraction.list_operations(self.case_id(), technique=technique,
                                          operation=operation, status=status)
        _fill_table(self.table, [], [
            [r["id"], r["technique_label"], r["operation"], r["engine"], r["status"],
             "yes" if r["verified"] else "no", r["payload_bytes"],
             (r["output_path"] or "-").split("/")[-1], r["created"]]
            for r in rows])
