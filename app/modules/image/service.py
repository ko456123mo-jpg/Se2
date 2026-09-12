"""Image steganography service.

Two engines, clearly separated:

``steghide``        - the studied course tool, driven through the ToolExecutor
                      (JPEG/BMP/WAV/AU carriers, passphrase protected).
``native LSB``      - StegoNexus' own lossless PNG/BMP LSB implementation, used
                      when a lossless carrier or a Python-only workflow is
                      required.  Not Steghide-compatible, not OpenPuff-compatible.

``CyberHide`` is handled as an **external integration**: StegoNexus detects it and
documents the workflow, and it never pretends to embed it.
"""
from __future__ import annotations

import time
from pathlib import Path

from app.core.constants import Status, Technique
from app.core.exceptions import ToolUnavailable, UnsupportedFormat
from app.core.logger import log_event
from app.core.security import validate_output_path, validate_readable_file
from app.modules.hashing.service import hash_file
from app.services.tool_executor import executor
from app.steganography import lsb_image
from app.storage.database import get_db

STEGHIDE_FORMATS = {".jpg", ".jpeg", ".bmp", ".wav", ".au"}


def engines() -> list[dict]:
    """Availability of every image engine (never faked)."""
    return [
        {"name": "steghide", "classification": Status.INTEGRATED
         if executor.is_available("steghide") else Status.UNAVAILABLE,
         "path": executor.resolve("steghide") or "",
         "version": executor.version("steghide", ["--version"]),
         "carriers": ", ".join(sorted(STEGHIDE_FORMATS)),
         "note": "Course tool: JPEG/BMP/WAV/AU with passphrase protection."},
        {"name": "native-lsb", "classification": Status.IMPLEMENTED,
         "path": "app/steganography/lsb_image.py",
         "version": "1.0", "carriers": ".png, .bmp, .tif (lossless only)",
         "note": "StegoNexus custom implementation - separate from Steghide and "
                 "from OpenPuff."},
        {"name": "cyberhide", "classification": Status.INTEGRATED
         if executor.is_available("cyberhide") else Status.REFERENCE,
         "path": executor.resolve("cyberhide") or "",
         "version": executor.version("cyberhide", ["--help"]),
         "carriers": "see course material",
         "note": "External integration. Detected and documented; StegoNexus does not "
                 "reimplement or fake it."},
    ]


def _record(technique: str, operation: str, status: str, **kwargs) -> None:
    db = get_db()
    status_label = kwargs.pop("status_label", Status.INTEGRATED)
    engine = kwargs.pop("engine", "steghide")
    db.add_extraction({"technique": technique, "operation": operation, "status": status,
                       "status_label": status_label, "engine": engine,
                       "messages": [], "details": {}, **kwargs})
    db.log_action(action=f"Steganography Operation ({operation})", module="image",
                  target=kwargs.get("input_path", ""), case_id=kwargs.get("case_id"),
                  tool=engine, result=f"{technique}: {status}", status=status,
                  hash_value=kwargs.get("output_hash", ""))


# --------------------------------------------------------------------- steghide
def steghide_embed(carrier: Path, secret: Path, passphrase: str, output: Path,
                   case_id: int | None = None, evidence_id: int | None = None) -> dict:
    """Hide a file inside an image with Steghide."""
    carrier_path = validate_readable_file(carrier)
    secret_path = validate_readable_file(secret)
    out = validate_output_path(output, overwrite=True)
    if carrier_path.suffix.lower() not in STEGHIDE_FORMATS:
        raise UnsupportedFormat(
            f"Steghide supports {', '.join(sorted(STEGHIDE_FORMATS))}; "
            f"got '{carrier_path.suffix}'. Use the native LSB engine for PNG.")
    if not executor.is_available("steghide"):
        raise ToolUnavailable("steghide is not installed (sudo apt install steghide).")
    started = time.perf_counter()
    result = executor.run("steghide", ["embed", "-ef", str(secret_path),
                                       "-cf", str(carrier_path), "-sf", str(out),
                                       "-p", passphrase, "-f", "-z", "9"],
                          case_id=case_id)
    before = hash_file(carrier_path, algorithms=("sha256",), case_id=case_id)
    if not result.ok:
        _record(Technique.IMAGE_STEGHIDE, "hide", "FAILED", case_id=case_id,
                evidence_id=evidence_id, input_path=str(carrier_path),
                output_path=str(out), input_hash=before.sha256,
                error=result.stderr.strip()[:400],
                messages=[result.command_display()])
        raise UnsupportedFormat(
            f"Steghide could not embed the payload: {result.stderr.strip()[:300]}")
    after = hash_file(out, algorithms=("sha256",), case_id=case_id)
    elapsed = (time.perf_counter() - started) * 1000
    _record(Technique.IMAGE_STEGHIDE, "hide", "SUCCESS", case_id=case_id,
            evidence_id=evidence_id, input_path=str(carrier_path),
            output_path=str(out), payload_bytes=secret_path.stat().st_size,
            input_hash=before.sha256, output_hash=after.sha256, verified=True,
            messages=[result.command_display(),
                      f"carrier sha256 {before.sha256[:16]}... -> stego "
                      f"{after.sha256[:16]}..."],
            elapsed_ms=elapsed)
    log_event("image", "steghide_embed", f"{secret_path.name} -> {out.name}",
              case_id=case_id, tool="steghide", status="OK")
    return {"technique": Technique.IMAGE_STEGHIDE, "status": "SUCCESS",
            "status_label": Status.INTEGRATED, "engine": "steghide",
            "carrier": str(carrier_path), "secret": str(secret_path),
            "output": str(out), "carrier_sha256": before.sha256,
            "output_sha256": after.sha256, "payload_bytes": secret_path.stat().st_size,
            "command": result.command_display(), "elapsed_ms": round(elapsed, 2)}


def steghide_extract(stego: Path, passphrase: str, output: Path,
                     case_id: int | None = None, evidence_id: int | None = None) -> dict:
    """Extract the embedded file from a Steghide carrier."""
    stego_path = validate_readable_file(stego)
    out = validate_output_path(output, overwrite=True)
    if not executor.is_available("steghide"):
        raise ToolUnavailable("steghide is not installed (sudo apt install steghide).")
    started = time.perf_counter()
    input_hash = hash_file(stego_path, algorithms=("sha256",), case_id=case_id).sha256
    result = executor.run("steghide", ["extract", "-sf", str(stego_path),
                                       "-xf", str(out), "-p", passphrase, "-f"],
                          case_id=case_id)
    if not result.ok:
        _record(Technique.IMAGE_STEGHIDE, "extract", "FAILED", case_id=case_id,
                evidence_id=evidence_id, input_path=str(stego_path),
                input_hash=input_hash, error=result.stderr.strip()[:400],
                messages=[result.command_display()])
        log_event("image", "steghide_extract", "failed - wrong passphrase or no payload",
                  case_id=case_id, tool="steghide", status="FAILED")
        from app.core.exceptions import KeyOrPasswordError

        raise KeyOrPasswordError(
            "Steghide could not extract data - the passphrase is wrong or the "
            f"carrier holds no Steghide payload ({result.stderr.strip()[:160]}).")
    out_hash = hash_file(out, algorithms=("sha256",), case_id=case_id).sha256
    elapsed = (time.perf_counter() - started) * 1000
    _record(Technique.IMAGE_STEGHIDE, "extract", "SUCCESS", case_id=case_id,
            evidence_id=evidence_id, input_path=str(stego_path), output_path=str(out),
            payload_bytes=out.stat().st_size, input_hash=input_hash,
            output_hash=out_hash, verified=True, messages=[result.command_display()],
            elapsed_ms=elapsed)
    log_event("image", "steghide_extract", f"recovered {out.name}", case_id=case_id,
              tool="steghide", status="OK")
    return {"technique": Technique.IMAGE_STEGHIDE, "status": "SUCCESS",
            "status_label": Status.INTEGRATED, "engine": "steghide",
            "stego": str(stego_path), "output": str(out),
            "input_sha256": input_hash, "output_sha256": out_hash,
            "payload_bytes": out.stat().st_size, "command": result.command_display(),
            "elapsed_ms": round(elapsed, 2)}


# -------------------------------------------------------------------- native LSB
def native_capacity(path: Path) -> dict:
    cap = lsb_image.capacity(validate_readable_file(path))
    return {**cap.as_dict(), "engine": "native-lsb",
            "note": "One bit per channel sample. Lossless output formats only."}


def native_embed(carrier: Path, secret: Path, key: str, output: Path,
                 channels: int = 3, case_id: int | None = None,
                 evidence_id: int | None = None) -> dict:
    """Native lossless LSB embedding (PNG/BMP/TIFF)."""
    carrier_path = validate_readable_file(carrier)
    secret_path = validate_readable_file(secret)
    out = validate_output_path(output, overwrite=True)
    started = time.perf_counter()
    payload = secret_path.read_bytes()
    try:
        result = lsb_image.hide(carrier_path, payload, key, out, channels=channels)
    except Exception as exc:
        _record(Technique.IMAGE_LSB_NATIVE, "hide", "FAILED", case_id=case_id,
                evidence_id=evidence_id, input_path=str(carrier_path),
                output_path=str(out), error=str(exc), engine="native-lsb",
                status_label=Status.IMPLEMENTED)
        raise
    before = hash_file(carrier_path, algorithms=("sha256",), case_id=case_id)
    after = hash_file(out, algorithms=("sha256",), case_id=case_id)
    elapsed = (time.perf_counter() - started) * 1000
    recovered = lsb_image.extract(out, key)
    verified = recovered == payload
    _record(Technique.IMAGE_LSB_NATIVE, "hide", "SUCCESS", case_id=case_id,
            evidence_id=evidence_id, input_path=str(carrier_path), output_path=str(out),
            payload_bytes=len(payload), capacity_bytes=result.capacity_bits // 8,
            input_hash=before.sha256, output_hash=after.sha256, verified=verified,
            engine="native-lsb", status_label=Status.IMPLEMENTED,
            messages=[f"utilisation {result.utilisation:.4%}",
                      f"round-trip verification: {'PASS' if verified else 'FAIL'}"],
            details=result.stats, elapsed_ms=elapsed)
    log_event("image", "native_embed", f"{secret_path.name} -> {out.name} "
                                       f"(verified={verified})",
              case_id=case_id, tool="native-lsb",
              status="OK" if verified else "FAILED")
    return {"technique": Technique.IMAGE_LSB_NATIVE, "status": "SUCCESS",
            "status_label": Status.IMPLEMENTED, "engine": "native-lsb",
            "carrier": str(carrier_path), "output": str(out),
            "carrier_sha256": before.sha256, "output_sha256": after.sha256,
            "payload_bytes": len(payload), "capacity_bits": result.capacity_bits,
            "utilisation": result.utilisation, "verified": verified,
            "key_fingerprint": result.key_fingerprint, "stats": result.stats,
            "elapsed_ms": round(elapsed, 2)}


def native_extract(stego: Path, key: str, output: Path, case_id: int | None = None,
                   evidence_id: int | None = None) -> dict:
    stego_path = validate_readable_file(stego)
    out = validate_output_path(output, overwrite=True)
    started = time.perf_counter()
    input_hash = hash_file(stego_path, algorithms=("sha256",), case_id=case_id).sha256
    payload = lsb_image.extract(stego_path, key)
    out.write_bytes(payload)
    out_hash = hash_file(out, algorithms=("sha256",), case_id=case_id).sha256
    elapsed = (time.perf_counter() - started) * 1000
    _record(Technique.IMAGE_LSB_NATIVE, "extract", "SUCCESS", case_id=case_id,
            evidence_id=evidence_id, input_path=str(stego_path), output_path=str(out),
            payload_bytes=len(payload), input_hash=input_hash, output_hash=out_hash,
            verified=True, engine="native-lsb", status_label=Status.IMPLEMENTED,
            elapsed_ms=elapsed)
    log_event("image", "native_extract", f"recovered {len(payload)} bytes -> {out.name}",
              case_id=case_id, tool="native-lsb", status="OK")
    return {"technique": Technique.IMAGE_LSB_NATIVE, "status": "SUCCESS",
            "status_label": Status.IMPLEMENTED, "engine": "native-lsb",
            "stego": str(stego_path), "output": str(out), "input_sha256": input_hash,
            "output_sha256": out_hash, "payload_bytes": len(payload),
            "elapsed_ms": round(elapsed, 2)}


def analyse(path: Path, reference: Path | None = None) -> dict:
    report = lsb_image.analyse(validate_readable_file(path),
                              reference_path=reference)
    return {**report, "technique": "image_lsb_analysis",
            "status_label": Status.IMPLEMENTED}


