"""Packet construction and parsing (Scapy), with strict laboratory gating."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.exceptions import AuthorizationError, ValidationError
from app.core.security import is_loopback_or_private, validate_ip, validate_port
from app.network.encoder import CHUNK_MASK


def require_authorized_lab(address: str) -> str:
    """Refuse to build covert traffic for anything but lab/loopback addresses."""
    ip = validate_ip(address)
    if not is_loopback_or_private(ip):
        raise AuthorizationError(
            f"Destination {ip} is not a loopback/private laboratory address. "
            "StegoNexus only constructs covert-channel packets for authorized "
            "laboratory environments.")
    return ip


def scapy_available() -> bool:
    try:
        import scapy.all  # noqa: F401
    except Exception:
        return False
    return True


def require_scapy():
    if not scapy_available():
        raise ValidationError(
            "Scapy is not installed. Install it with 'pip install scapy' "
            "(or 'sudo apt install python3-scapy').")
    import scapy.all as scapy

    return scapy


@dataclass
class BuiltPacket:
    index: int
    ip_id: int
    payload_chunk: int
    parity_bit: int
    summary: str
    hexdump: str = ""


class PacketBuilder:
    """Builds the controlled laboratory packets for the IPv4-ID channel."""

    def __init__(self, src: str, dst: str, dport: int, sport: int = 53000,
                 ttl: int = 64, enforce_lab: bool = True):
        self.dst = require_authorized_lab(dst) if enforce_lab else validate_ip(dst)
        self.src = validate_ip(src) if src else ""
        self.dport = validate_port(dport, "dport")
        self.sport = validate_port(sport, "sport")
        self.ttl = ttl

    def build(self, ip_ids: list[int], payload_mode: str = "empty") -> list[Any]:
        """Return a list of Scapy packets carrying ``ip_ids``."""
        scapy = require_scapy()
        packets = []
        for index, ip_id in enumerate(ip_ids):
            if not 0 <= ip_id <= 0xFFFF:
                raise ValidationError(f"IP id {ip_id} out of range at index {index}.")
            ip_kwargs: dict[str, Any] = {"dst": self.dst, "id": ip_id, "ttl": self.ttl}
            if self.src:
                ip_kwargs["src"] = self.src
            udp = scapy.UDP(sport=self.sport, dport=self.dport)
            if payload_mode == "marker":
                raw = scapy.Raw(load=b"SNXLAB")
            else:
                raw = scapy.Raw(load=b"")
            packets.append(scapy.IP(**ip_kwargs) / udp / raw)
        return packets

    def describe(self, ip_ids: list[int]) -> list[BuiltPacket]:
        out = []
        for index, ip_id in enumerate(ip_ids):
            chunk = ip_id & CHUNK_MASK
            parity = (ip_id >> 15) & 1
            out.append(BuiltPacket(
                index=index, ip_id=ip_id, payload_chunk=chunk, parity_bit=parity,
                summary=(f"#{index} IP.id={ip_id} (0x{ip_id:04x}) "
                         f"parity={parity} chunk=0b{chunk:015b}"),
                hexdump=f"{ip_id:016b}"))
        return out


class PacketParser:
    """Extracts the covert channel and the header facts from captured packets."""

    @staticmethod
    def parse_scapy_packet(packet: Any, index: int) -> dict:
        from app.core.models import NetworkPacketInfo

        ip = packet.getlayer("IP") if hasattr(packet, "getlayer") else None
        udp = packet.getlayer("UDP") if hasattr(packet, "getlayer") else None
        raw = packet.getlayer("Raw") if hasattr(packet, "getlayer") else None
        payload = bytes(raw.load) if raw is not None and hasattr(raw, "load") else b""
        ts = float(getattr(packet, "time", 0) or 0)
        import datetime

        stamp = datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S.%f")[:-3] if ts else ""
        return NetworkPacketInfo(
            index=index, timestamp=stamp,
            src=getattr(ip, "src", "") or "", dst=getattr(ip, "dst", "") or "",
            proto="UDP" if udp is not None else ("ICMP" if packet.haslayer("ICMP") else "IP"),
            length=len(packet), sport=getattr(udp, "sport", None),
            dport=getattr(udp, "dport", None), ip_id=getattr(ip, "id", None),
            ttl=getattr(ip, "ttl", None), payload_len=len(payload),
            payload_preview=payload[:32].hex(),
        ).__dict__

    @staticmethod
    def ip_ids(packets: list[dict]) -> list[int]:
        return [p["ip_id"] for p in packets if p.get("ip_id") is not None]


@dataclass
class CaptureFilter:
    src: str = ""
    dst: str = ""
    dport: int = 0
    proto: str = ""

    def bpf(self) -> str:
        parts = []
        if self.proto.lower() in ("udp", "tcp"):
            parts.append(self.proto.lower())
        if self.src:
            parts.append(f"src host {self.src}")
        if self.dst:
            parts.append(f"dst host {self.dst}")
        if self.dport:
            parts.append(f"port {self.dport}")
        return " and ".join(parts)

    def matches(self, packet: dict) -> bool:
        if self.src and packet.get("src") != self.src:
            return False
        if self.dst and packet.get("dst") != self.dst:
            return False
        if self.dport and packet.get("dport") != self.dport:
            return False
        if self.proto and packet.get("proto", "").lower() != self.proto.lower():
            return False
        return True


@dataclass
class ChannelStats:
    packets: int = 0
    unique_ids: int = 0
    id_entropy_bits: float = 0.0
    incrementing_pairs: int = 0
    repeated_pairs: int = 0
    zero_payload_packets: int = 0
    notes: list[str] = field(default_factory=list)
