"""Forensics & analysis view: run each tool and view raw + parsed output."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLineEdit, QPushButton,
                               QSplitter, QVBoxLayout, QWidget)

from app.core.config import get_config
from app.gui.views.base import BaseView
from app.gui.widgets import ConsoleView, SectionHeader, StatusChip, build_table, _fill_table
from app.modules.forensics import service as forensics


class ForensicsView(BaseView):
    title = "Forensics"
    icon = "forensics"

    def __init__(self, mw):
        super().__init__(mw)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 12)
        layout.addWidget(SectionHeader(
            "Forensics & Analysis", "file, strings, exiftool, binwalk, steghide info, "
                                    "foremost, zsteg and Shannon entropy. Unavailable tools "
                                    "are reported honestly."))

        row = QHBoxLayout()
        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText("Select target file")
        browse = QPushButton("Browse")
        browse.clicked.connect(self._browse)
        triage = QPushButton("Run full triage")
        triage.setProperty("primary", "true")
        triage.clicked.connect(self._triage)
        row.addWidget(self.file_edit, 1)
        row.addWidget(browse)
        row.addWidget(triage)
        layout.addLayout(row)

        buttons = QHBoxLayout()
        self.tool_buttons = {}
        for key, label in (("file_type", "file"), ("strings", "strings"),
                           ("entropy", "entropy"), ("binwalk", "binwalk"),
                           ("steghide_info", "steghide info"), ("foremost", "foremost"),
                           ("zsteg", "zsteg"), ("ffprobe", "ffprobe")):
            button = QPushButton(label)
            button.clicked.connect(lambda _=False, k=key: self._run_tool(k))
            self.tool_buttons[key] = button
            buttons.addWidget(button)
        buttons.addStretch(1)
        self.status_chip = StatusChip("idle", "warn")
        buttons.addWidget(self.status_chip)
        layout.addLayout(buttons)

        splitter = QSplitter()
        self.table = build_table(["Field", "Value"], [])
        self.console = ConsoleView()
        splitter.addWidget(self.table)
        splitter.addWidget(self.console)
        splitter.setSizes([520, 620])
        layout.addWidget(splitter, 1)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select target")
        if path:
            self.file_edit.setText(path)

    def _path(self) -> str:
        return self.file_edit.text().strip()

    def _run_tool(self, key: str) -> None:
        path = self._path()
        if not path:
            self.notify("Choose a target file first", "warn")
            return
        func = getattr(forensics, key)
        self.status_chip.set_text("running", "warn")
        if key == "foremost":
            # Carving always writes into a derived work directory - never into evidence.
            work = get_config().data_dir / "work" / f"foremost_{Path(path).stem}"
            work.mkdir(parents=True, exist_ok=True)
            self.run(func, self._done, None, path, work, "all", self.case_id())
        else:
            self.run(func, self._done, None, path, self.case_id())

    def _triage(self) -> None:
        path = self._path()
        if not path:
            self.notify("Choose a target file first", "warn")
            return
        self.status_chip.set_text("running triage", "warn")
        self.run(forensics.triage, self._triage_done, None, path, None, False,
                 self.case_id())

    def _done(self, result) -> None:
        self.status_chip.set_text(result.get("status", "OK"),
                                  "ok" if result.get("status") == "OK" else "warn")
        self._render(result)

    def _triage_done(self, result) -> None:
        self.status_chip.set_text("triage done", "ok")
        indicators = result.get("indicators", [])
        lines = [f"== {key} [{value.get('status', '')}] {value.get('summary', '')}"
                 for key, value in result.get("results", {}).items()]
        lines.append("")
        lines.append("Indicators:")
        lines += [f"  - {i}" for i in indicators] or ["  none"]
        lines.append("")
        lines.append(result.get("assessment", ""))
        self.console.set_text("\n".join(lines))
        _fill_table(self.table, [], [["indicator count", len(indicators)],
                                     ["assessment", result.get("assessment", "")]])
        self.notify(f"Triage complete: {len(indicators)} indicator(s)", "ok")

    def _render(self, result) -> None:
        rows = []
        for key in ("tool", "status", "summary"):
            if key in result:
                rows.append([key, str(result[key])])
        for key, value in result.items():
            if key in ("tool", "status", "summary"):
                continue
            if isinstance(value, (str, int, float, bool)):
                rows.append([key, str(value)])
        _fill_table(self.table, [], rows)
        raw = result.get("raw") or result.get("output") or result.get("sample")
        if isinstance(raw, list):
            raw = "\n".join(str(item) for item in raw)
        self.console.set_text(str(raw or "") or "(no raw output)")
