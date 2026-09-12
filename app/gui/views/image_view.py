"""Image steganography view: native LSB + Steghide, with honest classification."""
from __future__ import annotations

from PySide6.QtWidgets import (QComboBox, QFileDialog, QFrame, QHBoxLayout,
                               QLineEdit, QPushButton, QVBoxLayout)

from app.gui.views.base import BaseView
from app.gui.widgets import (ConsoleView, SectionHeader, StatusChip, build_table,
                             _fill_table)
from app.modules.image import service as image


class ImageView(BaseView):
    title = "Image Steganography"
    icon = "image"

    def __init__(self, mw):
        super().__init__(mw)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 12)
        layout.addWidget(SectionHeader(
            "Image Steganography", "Native LSB (lossless PNG/BMP) and Steghide. CyberHide is "
                                   "detected and documented as an external reference only."))

        engines_frame = QFrame()
        engines_frame.setObjectName("panel")
        engines_layout = QVBoxLayout(engines_frame)
        self.engines_table = build_table(["Engine", "Classification", "Carriers", "Note"], [])
        engines_layout.addWidget(self.engines_table)
        layout.addWidget(engines_frame)

        form = QFrame()
        form.setObjectName("panel")
        form_layout = QVBoxLayout(form)
        row1 = QHBoxLayout()
        self.engine = QComboBox()
        self.engine.addItems(["native-lsb", "steghide"])
        self.carrier = QLineEdit()
        self.carrier.setPlaceholderText("Carrier image")
        browse_carrier = QPushButton("Carrier...")
        browse_carrier.clicked.connect(lambda: self._browse(self.carrier))
        self.secret = QLineEdit()
        self.secret.setPlaceholderText("Secret file")
        browse_secret = QPushButton("Secret...")
        browse_secret.clicked.connect(lambda: self._browse(self.secret))
        row1.addWidget(self.engine)
        row1.addWidget(self.carrier, 1)
        row1.addWidget(browse_carrier)
        row1.addWidget(self.secret, 1)
        row1.addWidget(browse_secret)
        form_layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.password = QLineEdit()
        self.password.setPlaceholderText("Password / key")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.output = QLineEdit()
        self.output.setPlaceholderText("Output path")
        browse_out = QPushButton("Output...")
        browse_out.clicked.connect(self._browse_out)
        row2.addWidget(self.password, 1)
        row2.addWidget(self.output, 1)
        row2.addWidget(browse_out)
        form_layout.addLayout(row2)

        row3 = QHBoxLayout()
        hide_button = QPushButton("Hide")
        hide_button.setProperty("primary", "true")
        hide_button.clicked.connect(self._hide)
        extract_button = QPushButton("Extract")
        extract_button.clicked.connect(self._extract)
        info_button = QPushButton("Steghide info")
        info_button.clicked.connect(self._info)
        analyse_button = QPushButton("LSB analyse")
        analyse_button.clicked.connect(self._analyse)
        for button in (hide_button, extract_button, info_button, analyse_button):
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

    def _engine(self) -> str:
        return self.engine.currentText()

    def _hide(self) -> None:
        carrier = self.carrier.text().strip()
        secret = self.secret.text().strip()
        key = self.password.text()
        out = self.output.text().strip()
        if not (carrier and secret and key and out):
            self.notify("Carrier, secret, password and output are required", "warn")
            return
        if self._engine() == "steghide":
            func = image.steghide_embed
        else:
            func = image.native_embed
        self.status_chip.set_text("running", "warn")
        self._hide_dispatch(carrier, secret, key, out)

    def _hide_dispatch(self, carrier, secret, key, out) -> None:
        if self._engine() == "steghide":
            self.run(image.steghide_embed, self._hidden, None, carrier, secret, key, out,
                     self.case_id())
        else:
            self.run(image.native_embed, self._hidden, None, carrier, secret, key, out,
                     3, self.case_id())

    def _hidden(self, result) -> None:
        self.status_chip.set_text(result["status"], "ok")
        verified = result.get("verified")
        self.console.set_text(
            f"Technique : {result['technique']}\nEngine    : {result['engine']}\n"
            f"Status    : {result['status']} (label {result['status_label']})\n"
            f"Output    : {result['output']}\n"
            f"Carrier   : {result.get('carrier', result.get('carrier_sha256', ''))}\n"
            f"Payload   : {result['payload_bytes']} bytes\n"
            f"Verified  : {verified}\n"
            f"Output SHA256: {result.get('output_sha256', '')}")
        self.notify(f"Hidden {result['payload_bytes']} bytes "
                    f"(verified={verified})", "ok")

    def _extract(self) -> None:
        stego = self.carrier.text().strip()
        key = self.password.text()
        out = self.output.text().strip()
        if not (stego and key and out):
            self.notify("Stego image, password and output are required", "warn")
            return
        if self._engine() == "steghide":
            self.run(image.steghide_extract, self._extracted, None, stego, key, out,
                     self.case_id())
        else:
            self.run(image.native_extract, self._extracted, None, stego, key, out,
                     self.case_id())

    def _extracted(self, result) -> None:
        self.status_chip.set_text(result["status"], "ok")
        self.console.set_text(
            f"Extracted {result['payload_bytes']} bytes -> {result['output']}\n"
            f"Output SHA256: {result.get('output_sha256', '')}")
        self.notify(f"Extracted {result['payload_bytes']} bytes", "ok")

    def _info(self) -> None:
        from app.modules.forensics import service as forensics

        carrier = self.carrier.text().strip()
        if not carrier:
            self.notify("Choose a carrier first", "warn")
            return
        self.run(forensics.steghide_info, self._info_done, None, carrier,
                 self.password.text(), self.case_id())

    def _info_done(self, result) -> None:
        self.console.set_text(result.get("payload", {}).get("raw", result["summary"]))
        self.status_chip.set_text(result["status"], "ok")

    def _analyse(self) -> None:
        carrier = self.carrier.text().strip()
        if not carrier:
            self.notify("Choose an image first", "warn")
            return
        report = image.analyse(carrier)
        self.console.set_text(
            f"LSB ratio : {report['lsb_ratio']}\nchi-square : n/a\n"
            f"Suspicious: {report['suspicious']}\n{report['assessment']}")

    def refresh(self) -> None:
        _fill_table(self.engines_table, [], [
            [e["name"], e["classification"], e["carriers"], e["note"]]
            for e in image.engines()])
