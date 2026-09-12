"""Metadata analysis & injection view (ExifTool-backed)."""
from __future__ import annotations

from PySide6.QtWidgets import (QFileDialog, QFormLayout, QFrame, QHBoxLayout,
                               QLineEdit, QPushButton, QVBoxLayout)

from app.gui.views.base import BaseView
from app.gui.widgets import (ConsoleView, SectionHeader, StatusChip, build_table,
                             _fill_table)
from app.modules.metadata import service as metadata


class MetadataView(BaseView):
    title = "Metadata"
    icon = "metadata"

    def __init__(self, mw):
        super().__init__(mw)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 12)
        layout.addWidget(SectionHeader(
            "Metadata", "Inspect, inject and strip metadata using ExifTool. The original "
                        "file is never modified; injections run on copies with before/after "
                        "hashes."))

        row = QHBoxLayout()
        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText("Select a file to inspect")
        browse = QPushButton("Browse")
        browse.clicked.connect(self._browse)
        read = QPushButton("Read metadata")
        read.setProperty("primary", "true")
        read.clicked.connect(self._read)
        self.source_chip = StatusChip("-", "warn")
        row.addWidget(self.file_edit, 1)
        row.addWidget(browse)
        row.addWidget(read)
        row.addWidget(self.source_chip)
        layout.addLayout(row)

        self.table = build_table(["Group", "Tag", "Value"], [])
        layout.addWidget(self.table, 1)

        inject_frame = QFrame()
        inject_frame.setObjectName("panel")
        inject_layout = QVBoxLayout(inject_frame)
        inject_layout.addWidget(_h2("Inject metadata (copy only)"))
        form = QFormLayout()
        self.tag_fields = {}
        for label in ("Comment", "Author", "Title", "Description", "Keywords",
                      "Artist", "Copyright", "Software"):
            field = QLineEdit()
            self.tag_fields[label] = field
            form.addRow(label, field)
        inject_layout.addLayout(form)
        inject_row = QHBoxLayout()
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Output path for the modified copy")
        browse_out = QPushButton("Output...")
        browse_out.clicked.connect(self._browse_out)
        inject = QPushButton("Inject")
        inject.clicked.connect(self._inject)
        strip = QPushButton("Strip all (copy)")
        strip.clicked.connect(self._strip)
        inject_row.addWidget(self.output_edit, 1)
        inject_row.addWidget(browse_out)
        inject_row.addWidget(inject)
        inject_row.addWidget(strip)
        inject_layout.addLayout(inject_row)
        layout.addWidget(inject_frame)

        compare_frame = QFrame()
        compare_frame.setObjectName("panel")
        compare_layout = QVBoxLayout(compare_frame)
        compare_layout.addWidget(_h2("Before / After comparison (tag level)"))
        self.hash_line = QLineEdit()
        self.hash_line.setReadOnly(True)
        self.hash_line.setPlaceholderText("Before/after SHA-256 of the copy")
        compare_layout.addWidget(self.hash_line)
        self.compare_table = build_table(["Change", "Tag", "Value"], [])
        compare_layout.addWidget(self.compare_table)
        layout.addWidget(compare_frame)

    @staticmethod
    def _h2(text):
        from PySide6.QtWidgets import QLabel

        label = QLabel(text)
        label.setObjectName("h2")
        return label

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select file")
        if path:
            self.file_edit.setText(path)

    def _browse_out(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Output copy", "modified.png")
        if path:
            self.output_edit.setText(path)

    def _read(self) -> None:
        path = self.file_edit.text().strip()
        if not path:
            self.notify("Choose a file first", "warn")
            return
        self.run(metadata.read, self._loaded, None, path, self.case_id())

    def _loaded(self, snapshot) -> None:
        self.source_chip.set_text(snapshot.source)
        self.source_chip.set_level("ok" if snapshot.available else "warn")
        _fill_table(self.table, [], [[e.group, e.tag, e.value]
                                   for e in snapshot.entries])
        self.notify(f"{len(snapshot.entries)} metadata tags ({snapshot.source})", "ok")

    def _inject(self) -> None:
        path = self.file_edit.text().strip()
        out = self.output_edit.text().strip()
        tags = {label: field.text().strip() for label, field in self.tag_fields.items()
                if field.text().strip()}
        if not path or not out:
            self.notify("Choose source and output paths", "warn")
            return
        if not tags:
            self.notify("Enter at least one tag value", "warn")
            return
        self.run(metadata.inject, self._injected, None, path, tags, out, self.case_id())

    def _injected(self, result) -> None:
        diff = result["diff"]
        rows = [[ "added", tag, value] for tag, value in diff["added"].items()]
        rows += [["removed", tag, value] for tag, value in diff["removed"].items()]
        rows += [["changed", tag, value] for tag, value in diff["changed"].items()]
        _fill_table(self.compare_table, [], rows or [["unchanged", "-", "-"]])
        self.hash_line.setText(
            f"before {result['original_sha256'][:24]}...  after "
            f"{result['output_sha256'][:24]}...")
        self.notify(f"Metadata injected: {diff['counts']['added']} tag(s) added", "ok")
        self.file_edit.setText(result["output"])
        self._read()

    def _strip(self) -> None:
        path = self.file_edit.text().strip()
        out = self.output_edit.text().strip() or (path + ".stripped")
        if not path:
            self.notify("Choose a source file", "warn")
            return
        self.run(metadata.strip, self._stripped, None, path, out, self.case_id())

    def _stripped(self, result) -> None:
        self.notify(f"All metadata removed -> {result['output']}", "ok")


def _h2(text):
    from PySide6.QtWidgets import QLabel

    label = QLabel(text)
    label.setObjectName("h2")
    return label
