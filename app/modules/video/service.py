"""Video hiding & analysis service (project rules 31-36).

Engine separation (project rule 33/36)
--------------------------------------
``video_lsb``            custom implementation, FFmpeg/FFV1 lossless pipeline.
``video_container_eof``  **Custom Academic EOF/Container Hiding Implementation**
                         (AES-256-GCM blob appended after the container end).
                         It is explicitly NOT OpenPuff-compatible.
``video_spread``         educational spread-spectrum implementation.
``openpuff``             external practical/reference tool - detected and
                         documented only; never presented as native code.
``videohide.sh``         the course shell workflow, shipped in ``scripts/``.
"""
from __future__ import annotations

import time
from pathlib import Path

from app.core.config import get_config
from app.core.constants import Status, Technique
from app.core.exceptions import ToolUnavailable
from app.core.logger import log_event
from app.core.security import validate_output_path, validate_readable_file
from app.forensic.entropy import compare as entropy_compare
from app.modules.hashing.service import hash_file
from app.services.tool_executor import executor
from app.steganography import container, video_lsb, video_spread
from app.storage.database import get_db

SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "videohide.sh"


def _record(technique: str, operation: str, status: str, **kwargs) -> None:
    db = get_db()
    status_label = kwargs.pop("status_label", Status.IMPLEMENTED)
    engine = kwargs.pop("engine", "native-python+ffmpeg")
    db.add_extraction({"technique": technique, "operation": operation, "status": status,
                       "status_label": status_label, "engine": engine,
                       "messages": [], "details": {}, **kwargs})
    db.log_action(action=f"Steganography Operation ({operation})", module="video",
                  target=kwargs.get("input_path", ""), case_id=kwargs.get("case_id"),
                  tool=engine, result=f"{technique}: {status}", status=status,
                  hash_value=kwargs.get("output_hash", ""))


def tools() -> list[dict]:
    rows = []
    for name, label, required in (("ffmpeg", "FFmpeg (lossless decode/encode)", True),
                                  ("ffprobe", "FFprobe (stream inspection)", True),
                                  ("openpuff", "OpenPuff (course reference tool)", False)):
        available = executor.is_available(name)
        rows.append({"name": name, "label": label, "available": available,
                     "required": required, "path": executor.resolve(name) or "",
                     "version": executor.version(name, ["-version"] if "ff" in name
                                                 else ["--help"]),
                     "classification": (Status.INTEGRATED if available and required
                                        else (Status.REFERENCE if name == "openpuff"
                                              else Status.UNAVAILABLE)),
                     "note": ("External practical/reference tool. StegoNexus detects "
                              "it and documents the workflow; the custom video hiding "
                              "implementation is separate and NOT OpenPuff-compatible."
                              if name == "openpuff" else
                              "Integrated through the ToolExecutor.")})
    rows.append({"name": "videohide.sh", "label": "Course shell workflow",
                 "available": SCRIPT_PATH.exists(), "required": False,
                 "path": str(SCRIPT_PATH), "version": "1.0",
                 "classification": (Status.IMPLEMENTED if SCRIPT_PATH.exists()
                                    else Status.UNAVAILABLE),
                 "note": "FFmpeg-based frame LSB workflow studied in the course, "
                         "shipped as a script and reproducible from the GUI."})
    return rows


def probe(path: Path) -> dict:
    info = video_lsb.probe(validate_readable_file(path))
    return {**info.as_dict(), "status_label": Status.INTEGRATED}


# ---------------------------------------------------------------------- video LSB
def lsb_hide(carrier: Path, secret: Path, key: str, output: Path,
             case_id: int | None = None, evidence_id: int | None = None) -> dict:
    carrier_path = validate_readable_file(carrier)
    secret_path = validate_readable_file(secret)
    out = validate_output_path(output, overwrite=True)
    if not executor.is_available("ffmpeg"):
        raise ToolUnavailable("FFmpeg is required for video LSB (sudo apt install ffmpeg).")
    started = time.perf_counter()
    payload = secret_path.read_bytes()
    try:
        result = video_lsb.hide(carrier_path, payload, key, out)
    except Exception as exc:
        _record(Technique.VIDEO_LSB, "hide", "FAILED", case_id=case_id,
                evidence_id=evidence_id, input_path=str(carrier_path),
                output_path=str(out), error=str(exc))
        raise
    before = hash_file(carrier_path, algorithms=("sha256",), case_id=case_id)
    after = hash_file(out, algorithms=("sha256",), case_id=case_id)
    elapsed = (time.perf_counter() - started) * 1000
    _record(Technique.VIDEO_LSB, "hide", "SUCCESS" if result.verified else "PARTIAL",
            case_id=case_id, evidence_id=evidence_id, input_path=str(carrier_path),
            output_path=str(out), payload_bytes=len(payload),
            capacity_bytes=result.capacity_bits // 8, input_hash=before.sha256,
            output_hash=after.sha256, verified=result.verified,
            messages=[f"round-trip verification: {'PASS' if result.verified else 'FAIL'}",
                      result.verification_error or "FFV1 lossless output",
                      f"{result.frames_used} frames, codec {result.stats['output_codec']}"],
            details=result.stats, elapsed_ms=elapsed)
    log_event("video", "lsb_hide", f"{secret_path.name} -> {out.name} "
                                   f"verified={result.verified}",
              case_id=case_id, tool="ffmpeg", status="OK" if result.verified else "PARTIAL")
    return {"technique": Technique.VIDEO_LSB, "status": "SUCCESS",
            "status_label": Status.IMPLEMENTED, "engine": "native-python+ffmpeg",
            "carrier": str(carrier_path), "output": str(out),
            "carrier_sha256": before.sha256, "output_sha256": after.sha256,
            "payload_bytes": len(payload), "capacity_bits": result.capacity_bits,
            "frames_used": result.frames_used, "utilisation": result.utilisation,
            "verified": result.verified, "verification_error": result.verification_error,
            "key_fingerprint": result.key_fingerprint, "stats": result.stats,
            "elapsed_ms": round(elapsed, 2)}


def lsb_extract(stego: Path, key: str, output: Path, case_id: int | None = None,
                evidence_id: int | None = None) -> dict:
    stego_path = validate_readable_file(stego)
    out = validate_output_path(output, overwrite=True)
    started = time.perf_counter()
    input_hash = hash_file(stego_path, algorithms=("sha256",), case_id=case_id).sha256
    payload = video_lsb.extract(stego_path, key)
    out.write_bytes(payload)
    out_hash = hash_file(out, algorithms=("sha256",), case_id=case_id).sha256
    elapsed = (time.perf_counter() - started) * 1000
    _record(Technique.VIDEO_LSB, "extract", "SUCCESS", case_id=case_id,
            evidence_id=evidence_id, input_path=str(stego_path), output_path=str(out),
            payload_bytes=len(payload), input_hash=input_hash, output_hash=out_hash,
            verified=True, elapsed_ms=elapsed)
    return {"technique": Technique.VIDEO_LSB, "status": "SUCCESS",
            "status_label": Status.IMPLEMENTED, "engine": "native-python+ffmpeg",
            "stego": str(stego_path), "output": str(out), "input_sha256": input_hash,
            "output_sha256": out_hash, "payload_bytes": len(payload),
            "elapsed_ms": round(elapsed, 2)}


# --------------------------------------------------------------- container / EOF
def container_hide(carrier: Path, secret: Path, key: str, output: Path,
                   case_id: int | None = None, evidence_id: int | None = None) -> dict:
    carrier_path = validate_readable_file(carrier)
    secret_path = validate_readable_file(secret)
    out = validate_output_path(output, overwrite=True)
    started = time.perf_counter()
    result = container.hide(carrier_path, secret_path, out, key)
    before = hash_file(carrier_path, algorithms=("sha256",), case_id=case_id)
    after = hash_file(out, algorithms=("sha256",), case_id=case_id)
    entropies = entropy_compare(carrier_path, out)
    elapsed = (time.perf_counter() - started) * 1000
    _record(Technique.VIDEO_CONTAINER, "hide", "SUCCESS", case_id=case_id,
            evidence_id=evidence_id, input_path=str(carrier_path), output_path=str(out),
            payload_bytes=result.payload_bytes, input_hash=before.sha256,
            output_hash=after.sha256, verified=True, engine="aes-256-gcm-eof",
            messages=[f"blob {result.blob_bytes} bytes appended after EOF",
                      f"carrier still opens normally ({result.carrier_bytes} bytes intact)"],
            details=result.stats, elapsed_ms=elapsed)
    return {"technique": Technique.VIDEO_CONTAINER, "status": "SUCCESS",
            "status_label": Status.IMPLEMENTED, "engine": "aes-256-gcm-eof",
            "classification": "Custom Academic EOF/Container Hiding Implementation",
            "carrier": str(carrier_path), "output": str(out),
            "carrier_sha256": before.sha256, "output_sha256": after.sha256,
            "payload_bytes": result.payload_bytes, "blob_bytes": result.blob_bytes,
            "output_bytes": result.output_bytes, "hidden_filename": result.hidden_filename,
            "entropy": entropies, "stats": result.stats, "elapsed_ms": round(elapsed, 2),
            "note": "Not OpenPuff-compatible. OpenPuff is documented separately as an "
                    "external practical tool."}


def container_extract(stego: Path, key: str, output_dir: Path,
                      case_id: int | None = None, evidence_id: int | None = None) -> dict:
    stego_path = validate_readable_file(stego)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    input_hash = hash_file(stego_path, algorithms=("sha256",), case_id=case_id).sha256
    result = container.extract(stego_path, key)
    safe_name = Path(result.original_name).name or "recovered.bin"
    out = out_dir / safe_name
    out.write_bytes(result.payload)
    out_hash = hash_file(out, algorithms=("sha256",), case_id=case_id).sha256
    elapsed = (time.perf_counter() - started) * 1000
    _record(Technique.VIDEO_CONTAINER, "extract", "SUCCESS", case_id=case_id,
            evidence_id=evidence_id, input_path=str(stego_path), output_path=str(out),
            payload_bytes=len(result.payload), input_hash=input_hash,
            output_hash=out_hash, verified=True, engine="aes-256-gcm-eof",
            messages=[f"original file name recovered: {result.original_name}",
                      f"clean carrier size {result.clean_carrier_size} bytes"],
            elapsed_ms=elapsed)
    return {"technique": Technique.VIDEO_CONTAINER, "status": "SUCCESS",
            "status_label": Status.IMPLEMENTED, "engine": "aes-256-gcm-eof",
            "stego": str(stego_path), "output": str(out),
            "original_name": result.original_name, "input_sha256": input_hash,
            "output_sha256": out_hash, "payload_bytes": len(result.payload),
            "clean_carrier_size": result.clean_carrier_size,
            "elapsed_ms": round(elapsed, 2)}


def container_detect(path: Path) -> dict:
    target = validate_readable_file(path)
    present = container.has_container(target)
    return {"path": str(target), "has_container": present,
            "status_label": Status.IMPLEMENTED,
            "assessment": ("A StegoNexus EOF container trailer is present at the end "
                           "of this file - the file is larger than its logical "
                           "content." if present else
                           "No StegoNexus EOF container trailer detected. Other "
                           "appending tools use different markers.")}


def container_strip(stego: Path, output: Path) -> dict:
    stego_path = validate_readable_file(stego)
    out = validate_output_path(output, overwrite=True)
    result = container.strip(stego_path, out)
    return {**result, "technique": Technique.VIDEO_CONTAINER, "operation": "strip",
            "status_label": Status.IMPLEMENTED,
            "output_sha256": hash_file(out, algorithms=("sha256",)).sha256}


# --------------------------------------------------------------- spread spectrum
def spread_hide(carrier: Path, secret: Path, key: str, output: Path,
                chips_per_bit: int = video_spread.DEFAULT_CHIPS,
                alpha: float = video_spread.DEFAULT_ALPHA,
                case_id: int | None = None, evidence_id: int | None = None) -> dict:
    carrier_path = validate_readable_file(carrier)
    secret_path = validate_readable_file(secret)
    out = validate_output_path(output, overwrite=True)
    started = time.perf_counter()
    payload = secret_path.read_bytes()
    try:
        result = video_spread.hide(carrier_path, payload, key, out,
                                   chips_per_bit=chips_per_bit, alpha=alpha)
    except Exception as exc:
        _record(Technique.VIDEO_SPREAD, "hide", "FAILED", case_id=case_id,
                evidence_id=evidence_id, input_path=str(carrier_path),
                output_path=str(out), error=str(exc))
        raise
    after = hash_file(out, algorithms=("sha256",), case_id=case_id)
    elapsed = (time.perf_counter() - started) * 1000
    _record(Technique.VIDEO_SPREAD, "hide", "SUCCESS" if result.verified else "PARTIAL",
            case_id=case_id, evidence_id=evidence_id, input_path=str(carrier_path),
            output_path=str(out), payload_bytes=len(payload), output_hash=after.sha256,
            verified=result.verified,
            messages=[f"process gain {result.process_gain_db} dB",
                      "blind detection" + ("" if result.verified else " NOT verified - "
                                           "use differential detection with the carrier")],
            details={"chips_per_bit": chips_per_bit, "alpha": alpha, **result.stats},
            elapsed_ms=elapsed)
    return {"technique": Technique.VIDEO_SPREAD, "status": "SUCCESS",
            "status_label": Status.IMPLEMENTED, "engine": "native-python+ffmpeg",
            "output": str(out), "output_sha256": after.sha256,
            "payload_bytes": len(payload), "bits_embedded": result.bits_embedded,
            "chips_per_bit": chips_per_bit, "alpha": alpha, "verified": result.verified,
            "process_gain_db": result.process_gain_db, "stats": result.stats,
            "elapsed_ms": round(elapsed, 2),
            "note": "Educational implementation. Blind detection needs a high alpha; "
                    "differential detection with the clean carrier is far more reliable."}


def spread_extract(stego: Path, key: str, output: Path,
                   chips_per_bit: int = video_spread.DEFAULT_CHIPS,
                   reference: Path | None = None, case_id: int | None = None,
                   evidence_id: int | None = None) -> dict:
    stego_path = validate_readable_file(stego)
    out = validate_output_path(output, overwrite=True)
    input_hash = hash_file(stego_path, algorithms=("sha256",), case_id=case_id).sha256
    payload = video_spread.extract(stego_path, key, chips_per_bit=chips_per_bit,
                                   reference_path=reference)
    out.write_bytes(payload)
    out_hash = hash_file(out, algorithms=("sha256",), case_id=case_id).sha256
    _record(Technique.VIDEO_SPREAD, "extract", "SUCCESS", case_id=case_id,
            evidence_id=evidence_id, input_path=str(stego_path), output_path=str(out),
            payload_bytes=len(payload), input_hash=input_hash, output_hash=out_hash,
            verified=True, messages=[f"differential={reference is not None}"])
    return {"technique": Technique.VIDEO_SPREAD, "status": "SUCCESS",
            "status_label": Status.IMPLEMENTED, "output": str(out),
            "payload_bytes": len(payload), "input_sha256": input_hash,
            "output_sha256": out_hash, "differential": reference is not None}


def container_spec() -> dict:
    """Facts about the shipped custom academic EOF container.

    Every value is read from the implementation, and no third-party compatibility is
    claimed - the container is deliberately StegoNexus-only.
    """
    return {"name": f"Custom Academic EOF Container (version {container.VERSION})",
            "technique": container.TECHNIQUE,
            "classification": Status.IMPLEMENTED,
            "marker": container.SNX_EOF_MARKER.decode("ascii", errors="replace"),
            "crypto": "AES-256-GCM authenticated encryption (python-cryptography)",
            "key_derivation": ("PBKDF2-HMAC-SHA256, "
                               f"{container.PBKDF2_ITERATIONS} iterations, random salt"),
            "integrity": "GCM authentication tag - tampering fails extraction",
            "compatibility": ("StegoNexus only. Intentionally NOT compatible with OpenPuff, "
                              "DeepSound or any other third-party container."),
            "reference": ("OpenPuff is documented as an external reference application; "
                          "StegoNexus does not read or write its format."),
            "note": ("The payload is appended after the intact video container, so the "
                     "carrier keeps playing normally in a standard player.")}


def script_reference() -> dict:
    """Details of the shipped ``videohide.sh`` course workflow."""
    exists = SCRIPT_PATH.exists()
    return {"path": str(SCRIPT_PATH), "exists": exists,
            "status_label": Status.IMPLEMENTED if exists else Status.UNAVAILABLE,
            "content": SCRIPT_PATH.read_text(errors="replace") if exists else "",
            "usage": "scripts/videohide.sh encode <video> <payload> <key> <out.mkv>\n"
                     "scripts/videohide.sh decode <stego.mkv> <key> <out.bin>"}


def openpuff_reference() -> dict:
    """OpenPuff status and documented workflow (external tool, never faked)."""
    available = executor.is_available("openpuff")
    return {"name": "OpenPuff", "available": available,
            "status_label": Status.INTEGRATED if available else Status.REFERENCE,
            "platform": "Windows GUI application",
            "carriers": "Image, audio, video and document carriers (see course material)",
            "stegonexus_relation": ("StegoNexus' video container hiding is a separate "
                                    "custom implementation and is NOT OpenPuff-"
                                    "compatible; the two are never mixed."),
            "workflow": ["1. Select carrier(s) and a carrier data group",
                         "2. Add the secret payload",
                         "3. Set the three keys (carrier / hidden / session)",
                         "4. Hide, then verify the output opens normally",
                         "5. To extract: reopen the tool, supply the same keys"],
            "detection_notes": ["Container size grows by the payload size",
                                "Entropy of the appended/modified region increases",
                                "Compare against a known-clean carrier with the same "
                                "encoder settings"]}
