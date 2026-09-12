"""Network hiding / covert-channel laboratory service (project rules 37-44).

Hard restriction: authorized laboratory use only (loopback / RFC1918).  The
service refuses any other destination before a single packet is constructed.
"""
from __future__ import annotations

import time
from pathlib import Path

from app.core.config import get_config
from app.core.constants import Status
from app.core.exceptions import AuthorizationError, NetworkLabError
from app.core.logger import log_event
from app.core.security import validate_readable_file
from app.modules.hashing.service import hash_file
from app.network import encoder, interpreter
from app.network.packets import CaptureFilter
from app.network.sender import NetworkReceiver, NetworkSender, read_pcap
from app.storage.database import get_db

IPV6_STATUS = {
    "status_label": Status.OPTIONAL,
    "classification": "Advanced / research module",
    "statement": ("IPv6 extension-header steganography is documented as an advanced "
                  "research topic. StegoNexus does NOT claim production-grade support: "
                  "no fully tested IPv6 extension-header implementation is included, "
                  "and the module is labelled OPTIONAL."),
    "documented_fields": ["Hop-by-Hop Options", "Destination Options",
                          "Routing Header (Type 0/2/3)", "Fragment Header "
                          "(identification field)"],
    "notes": ["Scapy supports building IPv6 extension headers, but embedding and "
              "recovery were not verified end-to-end in this project.",
              "Report any IPv6 finding as 'research / unverified'."]}


def _record(operation: str, status: str, **kwargs) -> None:
    db = get_db()
    db.add_extraction({"technique": kwargs.pop("technique", "network_ipv4_id"),
                       "operation": operation, "status": status,
                       "status_label": kwargs.pop("status_label", Status.IMPLEMENTED),
                       "engine": kwargs.pop("engine", "scapy"),
                       "messages": [], "details": {}, **kwargs})
    db.log_action(action=f"Network Operation ({operation})", module="network",
                  target=kwargs.get("input_path", ""), case_id=kwargs.get("case_id"),
                  tool="scapy", result=f"{operation}: {status}", status=status)


def lab_status() -> dict:
    """Laboratory readiness: scapy, privileges, authorization switch."""
    import os

    from app.network.packets import scapy_available

    cfg = get_config()
    return {"scapy_available": scapy_available(),
            "tshark_available": __import__("shutil").which("tshark") is not None,
            "wireshark_available": __import__("shutil").which("wireshark") is not None,
            "elevated_privileges": os.geteuid() == 0 if hasattr(os, "geteuid") else False,
            "authorized_lab_enabled": cfg.network_authorized_lab,
            "allowed_address_space": "loopback / RFC1918 only",
            "ipv6_module": IPV6_STATUS,
            "statement": "Restricted to authorized laboratory / localhost / controlled "
                         "test environments."}


def encode_preview(payload: bytes) -> dict:
    """Show how a payload maps into IPv4 Identification values (no traffic sent)."""
    encoded = encoder.encode(payload)
    return {"payload_bytes": len(payload), "packets": encoded.packet_count,
            "bits": encoded.bits_used, "crc": encoded.crc,
            "ip_ids": encoded.ip_ids[:64], "notes": encoded.notes,
            "status_label": Status.IMPLEMENTED}


def send(payload: bytes, *, dst: str = "127.0.0.1", dport: int = 53000,
         transport: str = "ipv4_id", iface: str = "lo",
         case_id: int | None = None) -> dict:
    """Transmit a laboratory payload (loopback/private only)."""
    cfg = get_config()
    if not cfg.network_authorized_lab:
        raise AuthorizationError(
            "Network transmission is disabled. Enable 'Authorized laboratory mode' "
            "in Settings before sending any packet.")
    sender = NetworkSender(dst=dst, dport=dport, iface=iface)
    if transport == "ipv4_id":
        report = sender.send_ip_id(payload)
    elif transport == "udp_payload":
        report = sender.send_udp_payload(payload)
    else:
        raise NetworkLabError(f"Unknown transport: {transport}")
    status = "SUCCESS" if report.ok else "FAILED"
    _record("send", status, case_id=case_id, engine=f"scapy-{transport}",
            input_path="<memory payload>", payload_bytes=len(payload),
            error=report.error,
            messages=[f"{report.packets} packets to {report.destination}:{report.port}",
                      *(report.warnings or [])],
            details={"transport": report.transport, "ip_ids": report.ip_ids[:64],
                     "elapsed_ms": report.elapsed_ms})
    log_event("network", f"send_{transport}", f"{report.packets} packets -> "
                                              f"{report.destination}",
              case_id=case_id, status=status, tool="scapy")
    return {"technique": "network_ipv4_id" if transport == "ipv4_id" else "network_udp",
            "operation": "send", "status": status,
            "status_label": Status.IMPLEMENTED, "transport": transport,
            "destination": report.destination, "port": report.port,
            "packets": report.packets, "payload_bytes": report.payload_bytes,
            "ip_ids": report.ip_ids[:64], "elevated": report.elevated,
            "warnings": report.warnings, "error": report.error,
            "elapsed_ms": round(report.elapsed_ms, 2)}


def receive(*, dport: int = 53000, count: int = 64, timeout: float = 15.0,
            transport: str = "ipv4_id", iface: str = "lo", bpf: str = "",
            case_id: int | None = None) -> dict:
    """Capture laboratory traffic and reassemble the covert channel."""
    receiver = NetworkReceiver(iface=iface, dport=dport)
    if transport == "udp_payload":
        report = receiver.listen_udp(count=count, timeout=timeout)
        payload = report.payload or b""
        status = "SUCCESS" if payload else "EMPTY"
        _record("receive", status, case_id=case_id, engine="udp-socket",
                payload_bytes=len(payload), error=report.error,
                messages=[f"{report.packets_captured} datagrams captured"],
                details={"transport": "udp_payload"})
        return {"technique": "network_udp", "operation": "receive", "status": status,
                "status_label": Status.IMPLEMENTED, "payload": payload,
                "payload_text": report.payload_text, "packets": report.packets,
                "elapsed_ms": round(report.elapsed_ms, 2)}
    packets = receiver.capture(count=count, timeout=timeout, bpf=bpf)
    report = receiver.extract_from_packets(packets)
    status = "SUCCESS" if report.ok else "NO_PAYLOAD"
    _record("receive", status, case_id=case_id, engine="scapy-sniff",
            payload_bytes=len(report.payload or b""), error=report.error,
            messages=[f"{report.packets_captured} packets captured, "
                      f"{report.packets_matched} with IPv4 ids"],
            details={"transport": "ipv4_id", "info": report.info})
    log_event("network", "receive_ipv4_id",
              f"{report.packets_captured} packets, payload="
              f"{'yes' if report.ok else 'no'}", case_id=case_id,
              status=status, tool="scapy")
    return {"technique": "network_ipv4_id", "operation": "receive", "status": status,
            "status_label": Status.IMPLEMENTED, "payload": report.payload,
            "payload_text": report.payload_text, "packets": report.packets,
            "info": report.info, "error": report.error,
            "elapsed_ms": round(report.elapsed_ms, 2)}


def analyse_capture(path: Path, filt: CaptureFilter | None = None,
                    case_id: int | None = None, evidence_id: int | None = None) -> dict:
    """Import a capture file and run the forensic interpretation chain."""
    target = validate_readable_file(path)
    hash_file(target, algorithms=("sha256",), case_id=case_id,
              evidence_id=evidence_id)
    packets = read_pcap(target)
    if filt is not None:
        packets = [p for p in packets if filt.matches(p)]
    ids = [p["ip_id"] for p in packets if p.get("ip_id") is not None]
    analysis = interpreter.interpret(packets, ids)
    payload = None
    try:
        payload, info = encoder.decode(ids)
    except Exception as exc:
        info = {"reassembled": False, "reason": f"{type(exc).__name__}: {exc}"}
    result = {
        "path": str(target), "packets": len(packets), "packet_list": packets[:500],
        "id_statistics": interpreter.id_field_statistics(ids),
        "channel_statistics": interpreter.channel_statistics(packets),
        "interpretation": {"observation": analysis.observation,
                           "indicator": analysis.indicator,
                           "context": analysis.context,
                           "correlation": analysis.correlation,
                           "assessment": analysis.assessment,
                           "confidence": analysis.confidence},
        "recovered_payload": payload,
        "recovery_info": info,
        "teaching": interpreter.explain_why_anomaly_is_not_proof(),
        "status_label": Status.IMPLEMENTED,
    }
    db = get_db()
    db.add_analysis({"case_id": case_id, "evidence_id": evidence_id, "kind": "network",
                     "path": str(target), "tool": "scapy",
                     "status": "OK" if packets else "EMPTY",
                     "summary": f"{len(packets)} packets; {analysis.confidence} "
                                f"confidence",
                     "payload": {"ids": len(ids),
                                 "assessment": analysis.assessment,
                                 "recovered_bytes": len(payload or b"")}})
    db.log_action(action="Network Capture Analysed", module="network",
                  target=str(target), case_id=case_id, evidence_id=evidence_id,
                  tool="scapy", result=analysis.assessment[:400],
                  status="OK" if packets else "EMPTY")
    return result


def open_in_wireshark(path: Path) -> dict:
    """Launch Wireshark on a capture when it is installed."""
    import shutil
    import subprocess

    target = validate_readable_file(path)
    binary = shutil.which("wireshark")
    if not binary:
        from app.core.exceptions import ToolUnavailable

        raise ToolUnavailable(
            "Wireshark is not installed (sudo apt install wireshark). TShark "
            f"{'is' if shutil.which('tshark') else 'is not'} available for "
            "command-line capture analysis.")
    subprocess.Popen([binary, str(target)], stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)
    return {"status": "LAUNCHED", "path": str(target),
            "status_label": Status.INTEGRATED}


def ipv6_status() -> dict:
    return dict(IPV6_STATUS)
