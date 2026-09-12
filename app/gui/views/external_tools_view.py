"""External Tools Matrix: honest status + documented external workflows.

This page never pretends a third-party tool is integrated. It reports each course tool's
real availability, explains how to run it externally, and lets the investigator attach the
external result (screenshot / extracted file) to the active case as derived evidence.
"""
from __future__ import annotations

from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QPushButton, QSplitter,
                               QVBoxLayout)

from app.gui.views.base import BaseView
from app.gui.widgets import (ConsoleView, SectionHeader, build_table, _fill_table)
from app.services.tool_health import health

# Step-by-step external workflows for tools StegoNexus documents but does not re-implement.
WORKFLOWS = {
    "cyberhide": ["1. On a Windows host, open CyberHide and choose a BMP carrier.",
                  "2. Embed the payload with a password and save the stego BMP.",
                  "3. Bring the stego BMP back and use Image > Steghide/LSB analysis, or "
                  "record its SHA-256 and attach it as derived evidence."],
    "deepsound": ["1. On Windows, open DeepSound and add a WAV carrier + secret file.",
                  "2. Encode (optionally with a password) to produce a stego WAV.",
                  "3. Verify by decoding; attach the resulting WAV + SHA-256 to the case."],
    "coagula": ["1. On Windows, draw/write the secret as a spectrogram image in CoagulaLight.",
               "2. Render the image to a WAV audio file.",
               "3. Analyse the WAV spectrum in Audacity/StegoNexus; attach the artefact."],
    "openpuff": ["1. On Windows, open OpenPuff and select carrier + payload + password.",
                 "2. Hide using its transform-domain engines; note the container format.",
                 "3. Remember StegoNexus does NOT read OpenPuff containers; document the "
                 "result and hashes externally."],
    "audacity": ["1. Install Audacity (sudo apt install audacity).",
                 "2. Open a WAV and view waveform / spectrogram (Analyze > Plot Spectrum).",
                 "3. Use it to visually inspect LSB/phase/spread artefacts; StegoNexus can "
                 "launch it on a working copy."],
    "wireshark": ["1. Install Wireshark (sudo apt install wireshark).",
                  "2. Open a .pcap captured in the authorized lab.",
                  "3. Inspect IPv4 Identification fields; correlate with StegoNexus's "
                  "interpreter (indicator, not proof)."],
}


class ExternalToolsView(BaseView):
    title = "External Tools"
    icon = "extract"

    def __init__(self, mw):
        super().__init__(mw)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 12)
        layout.addWidget(SectionHeader(
            "External Tools Matrix", "Course tools that StegoNexus detects and documents "
                                     "but does not re-implement. Statuses are measured; "
                                     "nothing here is faked."))

        self.table = build_table(
            ["Tool", "Status", "OS", "Function", "Install / Note"], [])
        layout.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        check = QPushButton("Check availability")
        check.clicked.connect(self.refresh)
        workflow = QPushButton("Show external workflow")
        workflow.clicked.connect(self._workflow)
        attach = QPushButton("Attach result to case")
        attach.clicked.connect(self._attach)
        for button in (check, workflow, attach):
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.console = ConsoleView()
        layout.addWidget(self.console, 1)
        self._rows = []

    def _external_rows(self) -> list[dict]:
        wanted = {"cyberhide", "deepsound", "coagula", "openpuff", "audacity", "wireshark"}
        return [row for row in health.summary()["rows"] if row["name"] in wanted]

    def refresh(self) -> None:
        self._rows = self._external_rows()
        os_map = {"audacity": "Linux/Win/mac", "wireshark": "Linux/Win/mac"}
        func = {"cyberhide": "Image steganography (BMP)", "deepsound": "Audio steganography (WAV)",
                "coagula": "Spectrogram image -> audio", "openpuff": "Multi-carrier steganography",
                "audacity": "Waveform/spectrogram editor", "wireshark": "Packet capture analysis"}
        _fill_table(self.table, [], [
            [row["name"], row["classification"],
             os_map.get(row["name"], "Windows (GUI)"),
             func.get(row["name"], ""), row["install"] or row["note"]]
            for row in self._rows])
        self.notify(f"{sum(1 for r in self._rows if r['available'])}/"
                    f"{len(self._rows)} external tools available", "info")

    def _workflow(self) -> None:
        selected = self._selected_name()
        if not selected:
            self.notify("Select a tool row first", "warn")
            return
        steps = WORKFLOWS.get(selected, ["No documented workflow."])
        self.console.set_text(f"External workflow for {selected}:\n" +
                              "\n".join(steps) +
                              "\n\nRun it on the appropriate host, then attach the result "
                              "(screenshot / file + SHA-256) to the case below.")

    def _attach(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Attach external result")
        if not path:
            return
        from app.modules.evidence import service as evidence

        record = evidence.register_artifact(
            self.case_id(), path, notes="external tool result attached manually")
        self.notify(f"Attached {record['name']} (sha256 {record['sha256'][:16]}...)", "ok")

    def _selected_name(self) -> str:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return ""
        return self.table.item(rows[0].row(), 0).text()
