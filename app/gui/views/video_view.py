"""Video steganography view (FFV1 LSB, custom academic container, spread spectrum)."""
from __future__ import annotations

from PySide6.QtWidgets import (QComboBox, QFileDialog, QFrame, QHBoxLayout,
                               QLineEdit, QPushButton, QVBoxLayout)

from app.gui.views.base import BaseView
from app.gui.widgets import (ConsoleView, SectionHeader, StatusChip, build_table,
                             _fill_table)
from app.modules.video import service as video


class VideoView(BaseView):
    title = "Video Steganography"
    icon = "video"

    def __init__(self, mw):
        super().__init__(mw)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 12)
        layout.addWidget(SectionHeader(
            "Video Steganography", "FFV1 frame LSB, custom academic EOF container (separated "
                                   "from any third-party format) and spread spectrum. "
                                   "OpenPuff remains external/reference."))

        container_frame = QFrame()
        container_frame.setObjectName("panel")
        container_layout = QVBoxLayout(container_frame)
        self.container_table = build_table(
            ["Field", "Value"], [])
        container_layout.addWidget(self.container_table)
        layout.addWidget(container_frame)

        form = QFrame()
        form.setObjectName("panel")
        form_layout = QVBoxLayout(form)
        row1 = QHBoxLayout()
        self.technique = QComboBox()
        self.technique.addItems(["lsb", "container", "spread"])
        self.carrier = QLineEdit()
        self.carrier.setPlaceholderText("Carrier video (mp4)")
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
        detect_button = QPushButton("Detect container")
        detect_button.clicked.connect(self._detect)
        probe_button = QPushButton("ffprobe")
        probe_button.clicked.connect(self._probe)
        for button in (hide_button, extract_button, detect_button, probe_button):
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
        if technique == "container":
            self.run(video.container_hide, self._hidden, None, carrier, secret, key, out,
                     case_id=case_id)
        elif technique == "spread":
            self.run(video.spread_hide, self._hidden, None, carrier, secret, key, out,
                     case_id=case_id)
        else:
            self.run(video.lsb_hide, self._hidden, None, carrier, secret, key, out,
                     case_id=case_id)

    def _hidden(self, result) -> None:
        self.status_chip.set_text(result["status"], "ok")
        lines = [
            f"Technique : {result['technique']}",
            f"Status    : {result['status']} ({result['status_label']})",
            f"Output    : {result['output']}",
            f"Payload   : {result['payload_bytes']} bytes",
            f"Verified  : {result.get('verified', 'n/a')}",
        ]
        if "frames_used" in result:
            lines.append(f"Frames    : {result['frames_used']}")
        if "chips_per_bit" in result:
            lines.append(f"Chips/bit : {result['chips_per_bit']} (alpha "
                         f"{result.get('alpha')}, PG {result.get('process_gain_db')} dB)")
        if "blob_bytes" in result:
            lines.append(f"Blob      : {result['blob_bytes']} bytes appended "
                         f"(carrier {result.get('output_bytes')} bytes)")
            lines.append(f"Note      : {result.get('note', '')}")
        lines.append(f"Output SHA256: {result.get('output_sha256', '')}")
        self.console.set_text("\n".join(lines))
        self.notify(f"Hidden {result['payload_bytes']} bytes "
                    f"({result['technique']})", "ok")

    def _extract(self) -> None:
        stego, key, out = (self.carrier.text().strip(), self.key.text(),
                           self.output.text().strip())
        if not (stego and key and out):
            self.notify("Stego video, key and output are required", "warn")
            return
        technique = self.technique.currentText()
        case_id = self.case_id()
        if technique == "container":
            # The container extractor recovers the original file name, so it writes into
            # a directory rather than a fixed path.
            self.run(video.container_extract, self._extracted, None, stego, key,
                     str(Path(out).parent), case_id=case_id)
        elif technique == "spread":
            self.run(video.spread_extract, self._extracted, None, stego, key, out,
                     case_id=case_id)
        else:
            self.run(video.lsb_extract, self._extracted, None, stego, key, out,
                     case_id=case_id)

    def _extracted(self, result) -> None:
        self.status_chip.set_text(result["status"], "ok")
        self.console.set_text(f"Extracted {result['payload_bytes']} bytes -> "
                              f"{result['output']}\n"
                              f"Output SHA256: {result.get('output_sha256', '')}")
        self.notify(f"Extracted {result['payload_bytes']} bytes", "ok")

    def _detect(self) -> None:
        path = self.carrier.text().strip()
        if not path:
            self.notify("Choose a video first", "warn")
            return
        self.run(video.container_detect, self._detected, None, path)

    def _detected(self, result) -> None:
        self.console.set_text(
            f"Container present : {result['has_container']}\n"
            f"Status            : {result['status_label']}\n"
            f"Assessment        : {result['assessment']}")

    def _probe(self) -> None:
        path = self.carrier.text().strip()
        if not path:
            self.notify("Choose a video first", "warn")
            return
        self.run(video.probe, self._probed, None, path)

    def _probed(self, result) -> None:
        _fill_table(self.container_table, [], [
            ["available", result["available"]],
            ["codec", result["codec"]],
            ["width x height", f"{result['width']} x {result['height']}"],
            ["pix_fmt", result["pix_fmt"]],
            ["fps", result["fps"]],
            ["nb_frames", result["nb_frames"]],
            ["duration_s", result["duration_s"]],
            ["container", result["container"]],
            ["audio_codec", result["audio_codec"]],
            ["error", result["error"] or "-"],
        ])
        self.console.set_text(f"ffprobe on {result['path']}\n"
                              f"{len(result['streams'])} stream(s) reported")

    def refresh(self) -> None:
        spec = video.container_spec()
        _fill_table(self.container_table, [], [
            ["Container", spec["name"]],
            ["Classification", spec["classification"]],
            ["Marker", spec["marker"]],
            ["Crypto", spec["crypto"]],
            ["Key derivation", spec["key_derivation"]],
            ["Integrity", spec["integrity"]],
            ["Compatibility", spec["compatibility"]],
            ["Reference", spec["reference"]],
            ["Note", spec["note"]],
        ])
