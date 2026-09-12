"""Audio steganography view (LSB, phase coding, spread spectrum)."""
from __future__ import annotations

from PySide6.QtWidgets import (QComboBox, QFileDialog, QFrame, QHBoxLayout,
                               QLineEdit, QPushButton, QVBoxLayout)

from app.gui.views.base import BaseView
from app.gui.widgets import (ConsoleView, SectionHeader, StatusChip, build_table,
                             _fill_table)
from app.modules.audio import service as audio


class AudioView(BaseView):
    title = "Audio Steganography"
    icon = "audio"

    def __init__(self, mw):
        super().__init__(mw)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 12)
        layout.addWidget(SectionHeader(
            "Audio Steganography", "Native LSB, phase coding and spread spectrum (PN). "
                                   "CoagulaLight and DeepSound remain external references."))

        tech_frame = QFrame()
        tech_frame.setObjectName("panel")
        tech_layout = QVBoxLayout(tech_frame)
        self.tech_table = build_table(
            ["Technique", "Classification", "Carriers", "Recovery", "Note"], [])
        tech_layout.addWidget(self.tech_table)
        layout.addWidget(tech_frame)

        form = QFrame()
        form.setObjectName("panel")
        form_layout = QVBoxLayout(form)
        row1 = QHBoxLayout()
        self.technique = QComboBox()
        self.technique.addItems(["lsb", "phase", "spread"])
        self.carrier = QLineEdit()
        self.carrier.setPlaceholderText("Carrier audio (wav / flac)")
        browse_carrier = QPushButton("Carrier...")
        browse_carrier.clicked.connect(lambda: self._browse(self.carrier))
        self.secret = QLineEdit()
        self.secret.setPlaceholderText("Secret file")
        browse_secret = QPushButton("Secret...")
        browse_secret.clicked.connect(lambda: self._browse(self.secret))
        row1.addWidget(self.technique)
        row1.addWidget(self.carrier, 1)
        row1.addWidget(browse_carrier)
        row1.addWidget(self.secret, 1)
        row1.addWidget(browse_secret)
        form_layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.key = QLineEdit()
        self.key.setPlaceholderText("Key / password")
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.output = QLineEdit()
        self.output.setPlaceholderText("Output path")
        browse_out = QPushButton("Output...")
        browse_out.clicked.connect(self._browse_out)
        row2.addWidget(self.key, 1)
        row2.addWidget(self.output, 1)
        row2.addWidget(browse_out)
        form_layout.addLayout(row2)

        row3 = QHBoxLayout()
        hide_button = QPushButton("Hide")
        hide_button.setProperty("primary", "true")
        hide_button.clicked.connect(self._hide)
        extract_button = QPushButton("Extract")
        extract_button.clicked.connect(self._extract)
        tools_button = QPushButton("External tools")
        tools_button.clicked.connect(self._tools)
        for button in (hide_button, extract_button, tools_button):
            row3.addWidget(button)
        self.status_chip = StatusChip("idle", "warn")
        row3.addWidget(self.status_chip)
        form_layout.addLayout(row3)
        layout.addWidget(form)

        self.console = ConsoleView()
        layout.addWidget(self.console, 1)

    def _browse(self, edit) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select file")
        if path:
            edit.setText(path)

    def _browse_out(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Output")
        if path:
            self.output.setText(path)

    def _hide(self) -> None:
        carrier, secret, key, out = (self.carrier.text().strip(), self.secret.text().strip(),
                                     self.key.text(), self.output.text().strip())
        if not (carrier and secret and key and out):
            self.notify("Carrier, secret, key and output are required", "warn")
            return
        technique = self.technique.currentText()
        self.status_chip.set_text("running", "warn")
        case_id = self.case_id()
        if technique == "phase":
            self.run(audio.phase_hide, self._hidden, None, carrier, secret, out, key,
                     case_id=case_id)
        elif technique == "spread":
            self.run(audio.spread_hide, self._hidden, None, carrier, secret, key, out,
                     case_id=case_id)
        else:
            self.run(audio.lsb_hide, self._hidden, None, carrier, secret, key, out,
                     case_id=case_id)

    def _hidden(self, result) -> None:
        self.status_chip.set_text(result["status"], "ok")
        self.console.set_text(
            f"Technique : {result['technique']} ({result['status_label']})\n"
            f"Output    : {result['output']}\n"
            f"Payload   : {result['payload_bytes']} bytes\n"
            f"SNR       : {result.get('snr_db')} dB\n"
            f"Verified  : {result.get('verified', 'n/a')}\n"
            f"Warning   : {result.get('warning', '') or '-'}\n"
            f"Output SHA256: {result.get('output_sha256', '')}")
        self.notify(f"Hidden {result['payload_bytes']} bytes "
                    f"(SNR {result.get('snr_db')} dB)", "ok")

    def _extract(self) -> None:
        stego, key, out = (self.carrier.text().strip(), self.key.text(),
                           self.output.text().strip())
        if not (stego and key and out):
            self.notify("Stego audio, key and output are required", "warn")
            return
        technique = self.technique.currentText()
        case_id = self.case_id()
        if technique == "phase":
            self.run(audio.phase_extract, self._extracted, None, stego, out, key,
                     case_id=case_id)
        elif technique == "spread":
            self.run(audio.spread_extract, self._extracted, None, stego, key, out,
                     case_id=case_id)
        else:
            self.run(audio.lsb_extract, self._extracted, None, stego, key, out,
                     case_id=case_id)

    def _extracted(self, result) -> None:
        self.status_chip.set_text(result["status"], "ok")
        self.console.set_text(f"Extracted {result['payload_bytes']} bytes -> "
                              f"{result['output']}\n"
                              f"Output SHA256: {result.get('output_sha256', '')}")
        self.notify(f"Extracted {result['payload_bytes']} bytes", "ok")

    def _tools(self) -> None:
        rows = audio.tools()
        self.console.set_text("\n".join(
            f"{row['name']:14} {row['status']:12} {row['classification']} - "
            f"{row.get('version') or row.get('path', '')}" for row in rows))

    def refresh(self) -> None:
        _fill_table(self.tech_table, [], [
            [t["name"], t["classification"], t["carriers"], t["recovery"], t["note"]]
            for t in audio.techniques()])
