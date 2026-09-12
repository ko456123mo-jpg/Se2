"""Text steganography service (LSB + key, native Python)."""
from __future__ import annotations

import time
from pathlib import Path

from app.core.constants import Status, Technique
from app.core.exceptions import StegoNexusError
from app.core.logger import log_event
from app.core.security import validate_key
from app.modules.hashing.service import hash_file
from app.steganography import lsb_text
from app.storage.database import get_db


def _record(technique: str, operation: str, status: str, **kwargs) -> int:
    db = get_db()
    record = {"technique": technique, "operation": operation, "status": status,
              "status_label": kwargs.pop("status_label", Status.IMPLEMENTED),
              "engine": kwargs.pop("engine", "native-python"), "messages": [],
              "details": {}, **kwargs}
    row = db.add_extraction(record)
    db.log_action(action=f"Steganography Operation ({operation})", module="text",
                  target=record.get("input_path", ""), case_id=record.get("case_id"),
                  result=f"{technique}: {status}", status=status,
                  hash_value=record.get("output_hash", ""))
    return row


def capacity(cover_text: str) -> dict:
    cap = lsb_text.capacity(cover_text)
    return {"cover_chars": cap.cover_chars, "eligible_chars": cap.eligible_chars,
            "available_bits": cap.available_bits, "usable_bits": cap.usable_bits,
            "usable_bytes": cap.usable_bytes,
            "excluded_characters": "".join(lsb_text.EXCLUDED_FOR_REVERSIBILITY),
            "note": "One bit per eligible character; 128 bits are reserved for the "
                    "payload header."}


def hide(cover_text: str, message: str, key: str, output_path: Path | None = None,
         case_id: int | None = None, evidence_id: int | None = None) -> dict:
    started = time.perf_counter()
    validate_key(key)
    try:
        result = lsb_text.hide(cover_text, message, key)
    except StegoNexusError as exc:
        _record(Technique.TEXT_LSB_KEY, "hide", "FAILED", case_id=case_id,
                evidence_id=evidence_id, error=str(exc), capacity_bytes=0,
                input_path="<text>", output_path="")
        raise
    out = ""
    out_hash = ""
    if output_path:
        Path(output_path).write_text(result.stego_text, encoding="utf-8")
        out = str(output_path)
        out_hash = hash_file(Path(out), algorithms=("sha256",), case_id=case_id).sha256
    elapsed = (time.perf_counter() - started) * 1000
    _record(Technique.TEXT_LSB_KEY, "hide", "SUCCESS", case_id=case_id,
            evidence_id=evidence_id, input_path="<cover text>", output_path=out,
            payload_bytes=result.stats["secret_bytes"],
            capacity_bytes=result.capacity_bits // 8, output_hash=out_hash,
            messages=[f"utilisation {result.utilisation:.2%}",
                      f"modified {result.stats['modified_chars']} characters"],
            details=result.stats, elapsed_ms=elapsed)
    log_event("text", "hide", f"{result.stats['secret_bytes']} bytes hidden "
                              f"({result.utilisation:.2%} utilisation)",
              case_id=case_id, status="OK")
    return {"technique": Technique.TEXT_LSB_KEY, "status": "SUCCESS",
            "status_label": Status.IMPLEMENTED, "engine": "native-python",
            "stego_text": result.stego_text, "output_path": out,
            "output_sha256": out_hash, "payload_bits": result.payload_bits,
            "capacity_bits": result.capacity_bits, "utilisation": result.utilisation,
            "key_fingerprint": result.key_fingerprint, "stats": result.stats,
            "elapsed_ms": round(elapsed, 2)}


def extract(stego_text: str, key: str, output_path: Path | None = None,
            case_id: int | None = None, evidence_id: int | None = None) -> dict:
    started = time.perf_counter()
    validate_key(key)
    try:
        message = lsb_text.extract(stego_text, key)
    except StegoNexusError as exc:
        _record(Technique.TEXT_LSB_KEY, "extract", "FAILED", case_id=case_id,
                evidence_id=evidence_id, input_path="<stego text>", error=str(exc),
                status_label=Status.IMPLEMENTED)
        log_event("text", "extract", f"failed: {exc}", case_id=case_id,
                  status="FAILED")
        raise
    out = ""
    out_hash = ""
    if output_path:
        Path(output_path).write_text(message, encoding="utf-8")
        out = str(output_path)
        out_hash = hash_file(Path(out), algorithms=("sha256",), case_id=case_id).sha256
    elapsed = (time.perf_counter() - started) * 1000
    _record(Technique.TEXT_LSB_KEY, "extract", "SUCCESS", case_id=case_id,
            evidence_id=evidence_id, input_path="<stego text>", output_path=out,
            payload_bytes=len(message.encode()), output_hash=out_hash, verified=True,
            messages=[f"{len(message)} characters recovered"], elapsed_ms=elapsed)
    log_event("text", "extract", f"recovered {len(message)} characters",
              case_id=case_id, status="OK")
    return {"technique": Technique.TEXT_LSB_KEY, "status": "SUCCESS",
            "status_label": Status.IMPLEMENTED, "engine": "native-python",
            "message": message, "output_path": out, "output_sha256": out_hash,
            "elapsed_ms": round(elapsed, 2)}


def analyse(stego_text: str) -> dict:
    report = lsb_text.analyse(stego_text)
    return {"technique": Technique.TEXT_LSB_KEY, "status": "OK",
            "status_label": Status.IMPLEMENTED, "eligible_chars": report.eligible_chars,
            "lsb_ones": report.lsb_ones, "lsb_zeros": report.lsb_zeros,
            "bias": report.bias, "chi_square": report.chi_square,
            "suspicious": report.suspicious, "assessment": report.assessment,
            "notes": report.notes,
            "shannon_entropy": round(lsb_text.shannon_entropy_bits(stego_text), 4)}


def load_text(path: Path) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")
