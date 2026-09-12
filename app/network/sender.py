"""Sender / receiver for the authorized laboratory covert channel.

Two transports are provided, and the application is explicit about which one is
being used:

``ipv4_id``   - the studied covert channel.  The payload lives in the IPv4
                Identification field, the UDP payload is empty.  Requires
                elevated privileges (raw sockets), which Scapy reports clearly.
``udp_payload``- a plain UDP transport on loopback.  Not steganography: it is
                the *baseline* used in class to contrast a visible channel with
                a covert one.  Works without elevated privileges.
"""
from __future__ import annotations

import socket
import time
from dataclasses import dataclass, field
from pathlib import Path

from app.core.exceptions import AuthorizationError, NetworkLabError, ToolUnavailable
from app.core.logger import log_event
from app.core.security import is_loopback_or_private, validate_ip, validate_port
from app.network import encoder
from app.network.packets import PacketBuilder, PacketParser, require_scapy


@dataclass
class SendReport:
    transport: str
    destination: str
    port: int
    packets: int
    payload_bytes: int
    elapsed_ms: float
    ip_ids: list[int] = field(default_factory=list)
    elevated: bool = False
    warnings: list[str] = field(default_factory=list)
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error


@dataclass
class ReceiveReport:
    transport: str
    packets_captured: int
    packets_matched: int
    payload: bytes | None
    payload_text: str
    info: dict = field(default_factory=dict)
    packets: list[dict] = field(default_factory=list)
    elapsed_ms: float = 0.0
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.payload is not None


class NetworkSender:
    """Builds and transmits laboratory packets."""

    def __init__(self, dst: str = "127.0.0.1", dport: int = 53000, sport: int = 53001,
                 iface: str = "lo", ttl: int = 64, inter: float = 0.0):
        self.dst = validate_ip(dst)
        if not is_loopback_or_private(self.dst):
            raise AuthorizationError(
                f"Destination {self.dst} is outside the authorized laboratory range "
                "(loopback / RFC1918 only).")
        self.dport = validate_port(dport, "dport")
        self.sport = validate_port(sport, "sport")
        self.iface = iface
        self.ttl = ttl
        self.inter = inter
        self.builder = PacketBuilder(src="", dst=self.dst, dport=self.dport,
                                     sport=self.sport, ttl=self.ttl)

    # ------------------------------------------------------------- transports
    def send_ip_id(self, payload: bytes, *, max_packets: int = 4096) -> SendReport:
        """Transmit the payload through the IPv4 Identification field."""
        started = time.perf_counter()
        encoded = encoder.encode(payload, max_packets=max_packets)
        packets = self.builder.build(encoded.ip_ids)
        scapy = require_scapy()
        try:
            scapy.send(packets, iface=self.iface, verbose=0, inter=self.inter)
        except PermissionError as exc:
            return SendReport("ipv4_id", self.dst, self.dport, len(packets),
                              len(payload), (time.perf_counter() - started) * 1000,
                              error=("Permission denied while sending raw packets. "
                                     "Run the sender with elevated privileges "
                                     "(sudo scripts/network_lab.py send ...)."))
        except OSError as exc:
            return SendReport("ipv4_id", self.dst, self.dport, len(packets),
                              len(payload), (time.perf_counter() - started) * 1000,
                              error=f"Send failed: {exc}")
        report = SendReport("ipv4_id", self.dst, self.dport, len(packets), len(payload),
                            (time.perf_counter() - started) * 1000,
                            ip_ids=encoded.ip_ids, elevated=True)
        log_event("network", "send_ipv4_id",
                  f"{len(packets)} packets to {self.dst}:{self.dport}",
                  status="OK", tool="scapy")
        return report

    def send_udp_payload(self, payload: bytes, *, chunk: int = 1024) -> SendReport:
        """Baseline (non-covert) UDP transport on the loopback interface."""
        started = time.perf_counter()
        sent = 0
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.bind(("0.0.0.0", 0))
                for offset in range(0, len(payload), chunk):
                    sock.sendto(payload[offset:offset + chunk], (self.dst, self.dport))
                    sent += 1
        except OSError as exc:
            return SendReport("udp_payload", self.dst, self.dport, sent, len(payload),
                              (time.perf_counter() - started) * 1000,
                              error=f"UDP send failed: {exc}")
        log_event("network", "send_udp_payload",
                  f"{sent} datagrams to {self.dst}:{self.dport}", status="OK")
        return SendReport("udp_payload", self.dst, self.dport, sent, len(payload),
                          (time.perf_counter() - started) * 1000,
                          warnings=["UDP payload transport is NOT covert - the data is "
                                    "visible in the payload by design (baseline)."])


class NetworkReceiver:
    """Captures laboratory traffic and reassembles the covert channel."""

    def __init__(self, iface: str = "lo", dport: int = 53000):
        self.iface = iface
        self.dport = validate_port(dport, "dport")

    def capture(self, count: int, timeout: float = 20.0,
                bpf: str = "") -> list[dict]:
        """Sniff ``count`` packets with Scapy (needs elevated privileges)."""
        scapy = require_scapy()
        try:
            captured = scapy.sniff(iface=self.iface, count=count, timeout=timeout,
                                   filter=bpf or None, store=True)
        except PermissionError as exc:
            raise NetworkLabError(
                "Permission denied while capturing. Run with elevated privileges "
                "(sudo scripts/network_lab.py receive ...).") from exc
        except OSError as exc:
            raise NetworkLabError(f"Capture failed: {exc}") from exc
        parser = PacketParser()
        return [parser.parse_scapy_packet(pkt, i) for i, pkt in enumerate(captured)]

    def extract_from_packets(self, packets: list[dict]) -> ReceiveReport:
        """Reassemble the IPv4-ID channel from parsed packets."""
        started = time.perf_counter()
        ids = PacketParser.ip_ids(packets)
        try:
            payload, info = encoder.decode(ids)
        except Exception as exc:
            return ReceiveReport("ipv4_id", len(packets), len(ids), None, "",
                                 {"ids": len(ids)}, packets,
                                 (time.perf_counter() - started) * 1000,
                                 error=f"{type(exc).__name__}: {exc}")
        report = ReceiveReport("ipv4_id", len(packets), len(ids), payload,
                               payload.decode("utf-8", errors="replace"), info,
                               packets, (time.perf_counter() - started) * 1000)
        log_event("network", "extract_ipv4_id",
                  f"recovered {len(payload)} bytes from {len(ids)} packets",
                  status="OK")
        return report

    def listen_udp(self, count: int, timeout: float = 20.0) -> ReceiveReport:
        """Baseline UDP receiver (no elevated privileges required)."""
        started = time.perf_counter()
        chunks: list[bytes] = []
        packets: list[dict] = []
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", self.dport))
            sock.settimeout(timeout)
            deadline = time.time() + timeout
            while len(chunks) < count and time.time() < deadline:
                try:
                    data, addr = sock.recvfrom(65535)
                except socket.timeout:
                    break
                chunks.append(data)
                packets.append({"index": len(packets), "src": addr[0],
                                "dst": "", "proto": "UDP", "length": len(data),
                                "sport": addr[1], "dport": self.dport,
                                "payload_len": len(data),
                                "payload_preview": data[:32].hex()})
        payload = b"".join(chunks)
        return ReceiveReport("udp_payload", len(packets), len(packets), payload,
                             payload.decode("utf-8", errors="replace"),
                             {"datagrams": len(chunks)}, packets,
                             (time.perf_counter() - started) * 1000)


def read_pcap(path: Path) -> list[dict]:
    """Parse a capture file with Scapy (no privileges needed to read a file)."""
    p = Path(path)
    if not p.exists():
        raise NetworkLabError(f"Capture file not found: {p}")
    scapy = require_scapy()
    parser = PacketParser()
    try:
        packets = scapy.rdpcap(str(p))
    except Exception as exc:
        raise NetworkLabError(f"Cannot parse capture file: {exc}") from exc
    return [parser.parse_scapy_packet(pkt, i) for i, pkt in enumerate(packets)]
