"""Hashing & integrity view with before/after comparison workflow."""
from __future__ import annotations

from PySide6.QtWidgets import (QFileDialog, QFrame, QHBoxLayout, QLineEdit,
                               QPushButton, QVBoxLayout)

from app.gui.views.base import BaseView
from app.gui.widgets import SectionHeader, build_table, _fill_table
from app.modules.hashing import service as hashing


class HashingView(BaseView):
    title = "Hashing & Integrity"
    icon = "hash"

    def __init__(self, mw):
        super().__init__(mw)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 12)
        layout.addWidget(SectionHeader(
            "Hashing & Integrity", "MD5 / SHA-1 / SHA-256 / SHA-512 with SHA-256 as the "
                                   "primary integrity reference and full before/after "
                                   "comparison."))

        row = QHBoxLayout()
        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText("Select a file to hash")
        browse = QPushButton("Browse")
        browse.clicked.connect(self._browse)
        compute = QPushButton("Compute hashes")
        compute.setProperty("primary", "true")
        compute.clicked.connect(self._compute)
        row.addWidget(self.file_edit, 1)
        row.addWidget(browse)
        row.addWidget(compute)
        layout.addLayout(row)

        self.table = build_table(["Algorithm", "Digest"], [])
        layout.addWidget(self.table)

        compare_row = QHBoxLayout()
        self.file_a = QLineEdit()
        self.file_a.setPlaceholderText("File A (original)")
        self.file_b = QLineEdit()
        self.file_b.setPlaceholderText("File B (output)")
        browse_a = QPushButton("A")
        browse_a.clicked.connect(lambda: self._browse_into(self.file_a))
        browse_b = QPushButton("B")
        browse_b.clicked.connect(lambda: self._browse_into(self.file_b))
        compare = QPushButton("Compare")
        compare.clicked.connect(self._compare)
        for widget in (self.file_a, browse_a, self.file_b, browse_b, compare):
            compare_row.addWidget(widget)
        layout.addLayout(compare_row)

        self.compare_result = QLineEdit()
        self.compare_result.setReadOnly(True)
        self.compare_result.setPlaceholderText("Comparison result (MATCH / MISMATCH)")
        layout.addWidget(self.compare_result)
        layout.addStretch(1)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select file")
        if path:
            self.file_edit.setText(path)

    def _browse_into(self, edit) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select file")
        if path:
            edit.setText(path)

    def _compute(self) -> None:
        path = self.file_edit.text().strip()
        if not path:
            self.notify("Choose a file first", "warn")
            return
        self.run(hashing.hash_file, self._computed, None, path,
                 ("md5", "sha1", "sha256", "sha512"), self.case_id())

    def _computed(self, result) -> None:
        _fill_table(self.table, [], [
            [name.upper(), result.hashes.get(name, "")]
            for name in ("md5", "sha1", "sha256", "sha512")])
        self.notify(f"SHA-256 {result.sha256[:16]}...", "ok")

    def _compare(self) -> None:
        a = self.file_a.text().strip()
        b = self.file_b.text().strip()
        if not a or not b:
            self.notify("Choose both files", "warn")
            return
        self.run(hashing.compare, self._compared, None, a, b)

    def _compared(self, result) -> None:
        verdict = "MATCH" if result["identical"] else "MISMATCH"
        self.compare_result.setText(
            f"{verdict} - size delta {result['size_delta']} bytes - "
            f"{result['conclusion'][:120]}")
        self.notify(f"Comparison: {verdict}", "ok" if result["identical"] else "warn")
