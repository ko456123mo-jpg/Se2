"""Network steganography view: authorized-lab only, anomaly-aware."""
from __future__ import annotations

from PySide6.QtWidgets import (QComboBox, QFileDialog, QFormLayout, QFrame,
                               QHBoxLayout, QLineEdit, QPushButton, QSpinBox,
                               QSplitter, QVBoxLayout)

from app.gui.views.base import BaseView
from app.gui.widgets import (ConsoleView, SectionHeader, StatusChip, build_table,
                             _fill_table)
from app.modules.network import service as network


class NetworkView(BaseView):
    title = "Network Steganography"
    icon = "network"

    def __init__(self, mw):
        super().__init__(mw)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 12)
        layout.addWidget(SectionHeader(
            "Network Steganography", "Authorized laboratory only (loopback / RFC 1918). "
                                     "An anomaly in a header field is an indicator - never "
                                     "proof of hidden content."))

        lab_frame = QFrame()
        lab_frame.setObjectName("panel")
        lab_layout = QVBoxLayout(lab_frame)
        lab_row = QHBoxLayout()
        self.lab_status = StatusChip("lab status unknown", "warn")
        lab_row.addWidget(self.lab_status)
        self.elevated_chip = StatusChip("privileges unknown", "warn")
        lab_row.addWidget(self.elevated_chip)
        lab_row.addStretch(1)
        lab_layout.addLayout(lab_row)
        self.lab_note = QLineEdit()
        self.lab_note.setReadOnly(True)
        lab_layout.addWidget(self.lab_note)
        layout.addWidget(lab_frame)

        form = QFrame()
        form.setObjectName("panel")
        form_layout = QFormLayout(form)
        self.payload = QLineEdit()
        self.payload.setPlaceholderText("Payload to hide in IPv4 Identification values")
        self.dst = QLineEdit("127.0.0.1")
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(53000)
        self.transport = QComboBox()
        self.transport.addItems(["ipv4_id", "udp_payload"])
        self.iface = QLineEdit("lo")
        self.packets = QSpinBox()
        self.packets.setRange(1, 4096)
        self.packets.setValue(64)
        self.timeout = QSpinBox()
        self.timeout.setRange(1, 120)
        self.timeout.setValue(10)
        self.timeout.setSuffix(" s")
        self.pcap = QLineEdit()
        self.pcap.setPlaceholderText("Captured .pcap for forensic interpretation")
        browse_pcap = QPushButton("Pcap...")
        browse_pcap.clicked.connect(self._browse_pcap)
        pcap_row = QHBoxLayout()
        pcap_row.addWidget(self.pcap, 1)
        pcap_row.addWidget(browse_pcap)
        form_layout.addRow("Payload", self.payload)
        form_layout.addRow("Destination", self.dst)
        form_layout.addRow("Port", self.port)
        form_layout.addRow("Transport", self.transport)
        form_layout.addRow("Interface", self.iface)
        form_layout.addRow("Receive limit", self.packets)
        form_layout.addRow("Receive timeout", self.timeout)
        form_layout.addRow("Capture", pcap_row)
        layout.addWidget(form)

        buttons = QHBoxLayout()
        preview = QPushButton("Preview encoding")
        preview.clicked.connect(self._preview)
        send = QPushButton("Send (lab)")
        send.setProperty("primary", "true")
        send.clicked.connect(self._send)
        receive = QPushButton("Receive (lab)")
        receive.clicked.connect(self._receive)
        analyse = QPushButton("Analyse pcap")
        analyse.clicked.connect(self._analyse)
        wireshark = QPushButton("Open in Wireshark")
        wireshark.clicked.connect(self._wireshark)
        for button in (preview, send, receive, analyse, wireshark):
            buttons.addWidget(button)
        layout.addLayout(buttons)

        splitter = QSplitter()
        self.table = build_table(["Field", "Value"], [])
        self.console = ConsoleView()
        splitter.addWidget(self.table)
        splitter.addWidget(self.console)
        splitter.setSizes([470, 680])
        layout.addWidget(splitter, 1)

    def _browse_pcap(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select capture",
                                              filter="Captures (*.pcap *.pcapng)")
        if path:
            self.pcap.setText(path)

    def _preview(self) -> None:
        payload = self.payload.text()
        if not payload:
            self.notify("Enter a payload first", "warn")
            return
        encoded = network.encode_preview(payload.encode("utf-8"))
        ids = encoded["ip_ids"]
        self.console.set_text(
            "\n".join(str(note) for note in encoded["notes"])
            + f"\n\nFirst IPv4 Identification values ({len(ids)} shown):\n"
            + ", ".join(str(value) for value in ids[:32]))
        _fill_table(self.table, [], [
            ["status", encoded["status_label"]],
            ["payload bytes", encoded["payload_bytes"]],
            ["packets required", encoded["packets"]],
            ["bits used", encoded["bits"]],
            ["crc", hex(encoded["crc"])],
            ["note", "No traffic was sent - encoding preview only"],
        ])

    def _send(self) -> None:
        payload = self.payload.text()
        if not payload:
            self.notify("Enter a payload first", "warn")
            return
        status = network.lab_status()
        if not status["authorized_lab_enabled"]:
            from app.gui import dialogs

            dialogs.error(self, "Transmission disabled",
                          "Authorized laboratory mode is OFF. Enable it in Settings "
                          "before sending any packet.")
            return
        from app.gui import dialogs

        if not dialogs.confirm(
                self, "Authorized laboratory transmission",
                f"Send {len(payload)} bytes to {self.dst.text().strip()}:"
                f"{self.port.value()} via {self.transport.currentText()}?\n\n"
                "This is restricted to loopback / RFC1918 and requires root. No traffic "
                "is ever sent to the public internet."):
            return
        self.run(network.send, self._sent, None, payload.encode("utf-8"),
                 dst=self.dst.text().strip(), dport=self.port.value(),
                 transport=self.transport.currentText(), iface=self.iface.text().strip(),
                 case_id=self.case_id())

    def _sent(self, result) -> None:
        self.console.set_text(
            f"transport : {result['transport']}\n"
            f"target    : {result['destination']}:{result['port']}\n"
            f"packets   : {result['packets']} ({result['payload_bytes']} bytes)\n"
            f"elevated  : {result['elevated']}\n"
            f"elapsed   : {result['elapsed_ms']} ms\n"
            f"error     : {result['error'] or '-'}\n"
            f"warnings  : {', '.join(result['warnings']) or '-'}\n\n"
            f"IPv4 IDs  : {', '.join(str(v) for v in result['ip_ids'][:32])}")
        _fill_table(self.table, [], [
            ["status", result["status"]],
            ["technique", result["technique"]],
            ["packets sent", result["packets"]],
            ["payload bytes", result["payload_bytes"]],
            ["elevated", result["elevated"]],
            ["elapsed ms", result["elapsed_ms"]],
        ])
        self.notify(f"Send {result['status']}: {result['packets']} packets", 
                    "ok" if result["status"] == "SUCCESS" else "warn")

    def _receive(self) -> None:
        self.notify("Receiving requires root privileges inside an authorized laboratory",
                    "info")
        self.run(network.receive, self._received, None,
                 dport=self.port.value(), count=self.packets.value(),
                 timeout=float(self.timeout.value()),
                 transport=self.transport.currentText(),
                 iface=self.iface.text().strip(), case_id=self.case_id())

    def _received(self, result) -> None:
        text = result.get("payload_text") or ""
        self.console.set_text(
            f"status   : {result['status']}\n"
            f"packets  : {result['packets']}\n"
            f"payload  : {len(result.get('payload') or b'')} bytes\n"
            f"elapsed  : {result['elapsed_ms']} ms\n"
            f"error    : {result.get('error') or '-'}\n\n"
            f"Recovered text:\n{text or '(none)'}")
        _fill_table(self.table, [], [
            ["status", result["status"]],
            ["technique", result["technique"]],
            ["packets", result["packets"]],
            ["payload bytes", len(result.get("payload") or b"")],
            ["elapsed ms", result["elapsed_ms"]],
        ])
        self.notify(f"Receive {result['status']}",
                    "ok" if result["status"] == "SUCCESS" else "warn")

    def _analyse(self) -> None:
        path = self.pcap.text().strip()
        if not path:
            self.notify("Choose a capture file first", "warn")
            return
        self.run(network.analyse_capture, self._analysed, None, path, None,
                 self.case_id())

    def _analysed(self, result) -> None:
        interpretation = result["interpretation"]
        rows = [["packets", result["packets"]],
                ["recovered payload bytes", len(result["recovered_payload"] or b"")],
                ["reassembly", str(result["recovery_info"].get("reassembled"))]]
        for group in ("id_statistics", "channel_statistics"):
            for key, value in result[group].items():
                if isinstance(value, (str, int, float, bool)):
                    rows.append([f"{group}.{key}", value])
        for key in ("observation", "indicator", "context", "correlation",
                    "assessment", "confidence"):
            rows.append([f"interpretation.{key}", interpretation[key]])
        _fill_table(self.table, [], rows)
        teaching = result["teaching"]
        if isinstance(teaching, (list, tuple)):
            teaching = "\n".join(str(item) for item in teaching)
        self.console.set_text(
            f"Observation : {interpretation['observation']}\n"
            f"Indicator   : {interpretation['indicator']}\n"
            f"Context     : {interpretation['context']}\n"
            f"Correlation : {interpretation['correlation']}\n"
            f"Assessment  : {interpretation['assessment']}\n"
            f"Confidence  : {interpretation['confidence']}\n\n"
            f"Why an anomaly is not proof:\n{teaching}")
        self.notify(f"Capture analysed: {interpretation['confidence']} confidence", "ok")

    def _wireshark(self) -> None:
        path = self.pcap.text().strip()
        if not path:
            self.notify("Choose a capture file first", "warn")
            return
        result = network.open_in_wireshark(path)
        self.console.set_text(f"{result['status']}: {result.get('path', path)}\n"
                              f"{result.get('message', '')}")
        self.notify(result["status"], "ok" if result["status"] == "LAUNCHED" else "warn")

    def refresh(self) -> None:
        status = network.lab_status()
        self.lab_status.set_text(
            f"authorized: {status['authorized_lab_enabled']} | "
            f"{status['allowed_address_space']}",
            "ok" if status["authorized_lab_enabled"] else "warn")
        self.elevated_chip.set_text(
            f"root: {status['elevated_privileges']} | scapy: "
            f"{status['scapy_available']} | tshark: {status['tshark_available']}",
            "ok" if status["elevated_privileges"] else "warn")
        self.lab_note.setText(f"{status['statement']} IPv6 module: "
                              f"{status['ipv6_module']}")
