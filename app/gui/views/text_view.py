"""Text steganography view (LSB + key)."""
from __future__ import annotations

from PySide6.QtWidgets import (QFileDialog, QFrame, QHBoxLayout, QLineEdit,
                               QPlainTextEdit, QPushButton, QSplitter, QVBoxLayout)

from app.gui.views.base import BaseView
from app.gui.widgets import SectionHeader, build_table, _fill_table
from app.modules.text import service as text


class TextView(BaseView):
    title = "Text Steganography"
    icon = "text"

    def __init__(self, mw):
        super().__init__(mw)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 12)
        layout.addWidget(SectionHeader(
            "Text Steganography", "Native LSB + Key. The payload is compressed, CRC-checked "
                                  "and key-masked, then spread over a key-derived order of "
                                  "characters."))

        splitter = QSplitter()
        left = QFrame()
        left.setObjectName("panel")
        left_layout = QVBoxLayout(left)
        self.cover = QPlainTextEdit()
        self.cover.setPlaceholderText("Cover text (or load a file)")
        load_cover = QPushButton("Load cover file")
        load_cover.clicked.connect(self._load_cover)
        left_layout.addWidget(load_cover)
        left_layout.addWidget(self.cover, 1)
        self.secret = QPlainTextEdit()
        self.secret.setPlaceholderText("Secret message")
        self.secret.setMaximumHeight(90)
        left_layout.addWidget(self.secret)
        key_row = QHBoxLayout()
        self.key = QLineEdit()
        self.key.setPlaceholderText("Key / password")
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        key_row.addWidget(self.key, 1)
        left_layout.addLayout(key_row)

        actions = QHBoxLayout()
        capacity = QPushButton("Capacity")
        capacity.clicked.connect(self._capacity)
        encode = QPushButton("Encode")
        encode.setProperty("primary", "true")
        encode.clicked.connect(self._encode)
        decode = QPushButton("Decode")
        decode.clicked.connect(self._decode)
        analyse = QPushButton("Analyse")
        analyse.clicked.connect(self._analyse)
        for button in (capacity, encode, decode, analyse):
            actions.addWidget(button)
        left_layout.addLayout(actions)
        splitter.addWidget(left)

        right = QFrame()
        right.setObjectName("panel")
        right_layout = QVBoxLayout(right)
        self.stego = QPlainTextEdit()
        self.stego.setReadOnly(True)
        self.stego.setPlaceholderText("Stego text / extracted message")
        right_layout.addWidget(self.stego, 1)
        self.info_table = build_table(["Metric", "Value"], [])
        right_layout.addWidget(self.info_table)
        splitter.addWidget(right)
        splitter.setSizes([600, 560])
        layout.addWidget(splitter, 1)

    def _load_cover(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load cover text")
        if path:
            self.cover.setPlainText(text.load_text(path))

    def _capacity(self) -> None:
        cover = self.cover.toPlainText()
        if not cover:
            self.notify("Enter or load cover text first", "warn")
            return
        cap = text.capacity(cover)
        _fill_table(self.info_table, [], [
            ["Cover characters", cap["cover_chars"]],
            ["Eligible characters", cap["eligible_chars"]],
            ["Usable bytes", cap["usable_bytes"]],
            ["Excluded for reversibility", cap["excluded_characters"]],
        ])

    def _encode(self) -> None:
        cover = self.cover.toPlainText()
        message = self.secret.toPlainText()
        key = self.key.text()
        if not cover or not message or not key:
            self.notify("Cover, secret and key are all required", "warn")
            return
        self.run(text.hide, self._encoded, None, cover, message, key, None,
                 self.case_id())

    def _encoded(self, result) -> None:
        self.stego.setPlainText(result["stego_text"])
        _fill_table(self.info_table, [], [
            ["Status", result["status"]],
            ["Payload bits", result["payload_bits"]],
            ["Capacity bits", result["capacity_bits"]],
            ["Utilisation", f"{result['utilisation']:.2%}"],
            ["Modified chars", result["stats"]["modified_chars"]],
            ["Key fingerprint", result["key_fingerprint"]],
        ])
        self.notify(f"Encoded {result['stats']['secret_bytes']} bytes "
                    f"({result['utilisation']:.2%} utilisation)", "ok")

    def _decode(self) -> None:
        stego = self.stego.toPlainText() or self.cover.toPlainText()
        key = self.key.text()
        if not stego or not key:
            self.notify("Stego text and key are required", "warn")
            return
        self.run(text.extract, self._decoded, None, stego, key, None, self.case_id())

    def _decoded(self, result) -> None:
        self.stego.setPlainText(result["message"])
        self.notify(f"Extracted {len(result['message'])} characters", "ok")

    def _analyse(self) -> None:
        stego = self.stego.toPlainText() or self.cover.toPlainText()
        if not stego:
            self.notify("Nothing to analyse", "warn")
            return
        report = text.analyse(stego)
        _fill_table(self.info_table, [], [
            ["LSB bias", report["bias"]],
            ["Chi-square", report["chi_square"]],
            ["Suspicious", report["suspicious"]],
            ["Shannon entropy", report["shannon_entropy"]],
            ["Assessment", report["assessment"][:120]],
        ])
