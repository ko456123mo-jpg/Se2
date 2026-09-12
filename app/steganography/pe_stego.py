"""Executable-carrier steganography (malware/virus hiding topic) - native.

Course topic: hiding data inside **executables** (malware / virus carriers).
Real families do this constantly - appended overlay payloads, padding slack
abuse, resource stashes - so the defensive analysis side must be able to
**demonstrate, detect and reverse** it in a laboratory.

``StegoNexus implementation`` - two native, purely static techniques:

1. ``overlay`` - the blob is appended **after the last PE section**
   (the overlay region).  Parsers/loaders that trust the section table never
   display those bytes, while the file still "looks" normal in Explorer.
   This mirrors the classic packer-installer payload pattern.
2. ``slack`` - the blob is written into the **padding (slack space) between
   a section's VirtualSize and its SizeOfRawData**.  The output file keeps
   **exactly the same size** as the carrier - a deliberate forensic talking
   point: size alone proves nothing, which is why we ship a scanner.

Both techniques wrap the payload in the same AES-256-GCM container used by
the video EOF engine (PBKDF2-SHA256, 200k iterations).  Nothing is executed:
this module only reads/writes bytes on **copies** - the original carrier and
the specimen are never modified and never run.

Blob layout (big-endian)::

    SNXPEST001 marker (10 B)
    version (1 B)
    blob_len (4 B)                       everything after this field
    salt (16 B)                          PBKDF2 salt
    nonce (12 B)                         AES-GCM nonce
    name_len (2 B) + name (UTF-8)        original secret file name
    AES-256-GCM ciphertext + 16 B tag

Overlay mode appends ``blob + trailer`` where ``trailer = blob_len (8 B) +
marker``.  Slack mode writes the blob at the exact start of the chosen
section's padding and zero-fills the remainder of that padding.
"""
from __future__ import annotations

import os
import struct
from dataclasses import dataclass, field
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

from app.core.constants import SNX_PE_MARKER
from app.core.exceptions import (CapacityError, CorruptedCarrier, IntegrityError,
                                 KeyOrPasswordError, ValidationError)
from app.core.security import validate_key
from app.malware import pe

TECHNIQUE_OVERLAY = "overlay"
TECHNIQUE_SLACK = "slack"
TECHNIQUES = (TECHNIQUE_OVERLAY, TECHNIQUE_SLACK)
VERSION = 1
HEADER_LEN = 10 + 1 + 4 + 16 + 12 + 2          # marker..name_len, name extra
PBKDF2_ITERATIONS = 200_000
TRAILER_LEN = 8 + len(SNX_PE_MARKER)


@dataclass
class ExecStegoResult:
    output_path: str
    technique: str
    carrier_bytes: int
    output_bytes: int
    payload_bytes: int
    blob_bytes: int
    hidden_filename: str
    size_unchanged: bool
    section: str = ""
    engine: str = "stegonexus-aes-gcm-pe"
    stats: dict = field(default_factory=dict)


@dataclass
class ExecStegoExtract:
    payload: bytes
    original_name: str
    technique: str
    blob_bytes: int
    section: str = ""
    engine: str = "stegonexus-aes-gcm-pe"


@dataclass
class SlackRegion:
    section: str
    slack_offset: int
    slack_len: int

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def _derive_key(key: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                     iterations=PBKDF2_ITERATIONS)
    return kdf.derive(key.encode("utf-8"))


def _build_blob(secret: bytes, name: str, key: str) -> bytes:
    if not secret:
        raise ValidationError("Secret file is empty.")
    name_bytes = name.encode("utf-8")
    if len(name_bytes) > 65535:
        raise ValidationError("Secret file name is too long to store.")
    salt = os.urandom(16)
    nonce = os.urandom(12)
    ciphertext = AESGCM(_derive_key(key, salt)).encrypt(nonce, secret, SNX_PE_MARKER)
    blob_len = 16 + 12 + 2 + len(name_bytes) + len(ciphertext)  # after blob_len
    blob = (SNX_PE_MARKER + bytes([VERSION]) + struct.pack(">I", blob_len)
            + salt + nonce + struct.pack(">H", len(name_bytes)) + name_bytes
            + ciphertext)
    return blob


def _parse_blob(blob: bytes, key: str, technique: str, section: str = "") -> ExecStegoExtract:
    if not blob.startswith(SNX_PE_MARKER):
        raise CorruptedCarrier("Executable stego marker is missing or corrupted.")
    version = blob[10]
    if version != VERSION:
        raise CorruptedCarrier(f"Unsupported executable-stego version {version}.")
    offset = 11
    (blob_len,) = struct.unpack_from(">I", blob, offset)
    offset += 4
    if blob_len <= 0 or blob_len != len(blob) - 15:
        raise CorruptedCarrier("Executable stego blob declares an impossible size.")
    salt = blob[offset:offset + 16]; offset += 16
    nonce = blob[offset:offset + 12]; offset += 12
    (name_len,) = struct.unpack_from(">H", blob, offset); offset += 2
    name = blob[offset:offset + name_len].decode("utf-8", errors="replace")
    offset += name_len
    ciphertext = blob[offset:]
    try:
        payload = AESGCM(_derive_key(key, salt)).decrypt(nonce, ciphertext, SNX_PE_MARKER)
    except Exception as exc:  # InvalidTag
        raise KeyOrPasswordError(
            "Decryption failed - wrong key, or the hidden blob was tampered with "
            "(AES-GCM authentication failed).") from exc
    return ExecStegoExtract(payload=payload, original_name=name, technique=technique,
                            blob_bytes=len(blob), section=section)


# --------------------------------------------------------------------------- geometry

def overlay_start(path: Path) -> int:
    """First byte after the last PE section; file size when not a PE."""
    p = Path(path)
    report = pe.parse(p)
    if not report.is_pe or not report.sections:
        return p.stat().st_size
    return max(s.raw_offset + s.raw_size for s in report.sections)


def slack_regions(path: Path) -> list[SlackRegion]:
    """Padding (VirtualSize .. SizeOfRawData) of every PE section."""
    report = pe.parse(Path(path))
    regions: list[SlackRegion] = []
    if not report.is_pe:
        return regions
    for s in report.sections:
        used = min(s.virtual_size, s.raw_size) if s.virtual_size else s.raw_size
        slack = s.raw_size - used
        if slack > 0:
            regions.append(SlackRegion(section=s.name,
                                       slack_offset=s.raw_offset + used,
                                       slack_len=slack))
    return regions


def has_overlay(path: Path) -> bool:
    """True when the file ends with a StegoNexus executable-stego trailer."""
    p = Path(path)
    size = p.stat().st_size
    if size < TRAILER_LEN:
        return False
    with open(p, "rb") as fh:
        fh.seek(size - TRAILER_LEN)
        trailer = fh.read(TRAILER_LEN)
    return trailer.endswith(SNX_PE_MARKER)


def _find_slack_blob(path: Path) -> tuple[SlackRegion, bytes] | None:
    p = Path(path)
    with open(p, "rb") as fh:
        for region in slack_regions(p):
            if region.slack_len < HEADER_LEN:
                continue
            fh.seek(region.slack_offset)
            head = fh.read(HEADER_LEN)
            if head.startswith(SNX_PE_MARKER):
                (blob_len,) = struct.unpack_from(">I", head, 11)
                if blob_len <= 0 or blob_len > region.slack_len - 15:
                    continue
                fh.seek(region.slack_offset)
                return region, fh.read(15 + blob_len)
    return None


# --------------------------------------------------------------------------- hide/extract

def hide(carrier_path: Path, payload_path: Path, output_path: Path, key: str,
         technique: str = TECHNIQUE_OVERLAY) -> ExecStegoResult:
    """Hide ``payload_path`` inside a **copy** of the executable carrier."""
    validate_key(key)
    if technique not in TECHNIQUES:
        raise ValidationError(f"Unknown technique '{technique}' - use one of {TECHNIQUES}.")
    carrier = Path(carrier_path)
    secret = Path(payload_path).read_bytes()
    data = carrier.read_bytes()
    blob = _build_blob(secret, Path(payload_path).name, key)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if technique == TECHNIQUE_OVERLAY:
        start = overlay_start(carrier)
        if has_overlay(carrier):
            raise ValidationError(
                "This carrier already ends with a StegoNexus executable-stego "
                "trailer. Hide into a clean carrier instead of stacking blobs.")
        if start < len(data):
            raise ValidationError(
                f"Carrier already carries {len(data) - start} bytes of overlay "
                "data; refusing to overwrite unknown content.")
        with open(out, "wb") as fh:
            fh.write(data)
            fh.write(blob)
            fh.write(struct.pack(">Q", len(blob)) + SNX_PE_MARKER)
        return ExecStegoResult(
            output_path=str(out), technique=TECHNIQUE_OVERLAY,
            carrier_bytes=len(data), output_bytes=len(data) + len(blob) + TRAILER_LEN,
            payload_bytes=len(secret), blob_bytes=len(blob),
            hidden_filename=Path(payload_path).name, size_unchanged=False,
            stats={"cipher": "AES-256-GCM", "pbkdf2_iterations": PBKDF2_ITERATIONS,
                   "trailer_bytes": TRAILER_LEN})

    # ---- slack technique ---------------------------------------------------
    hit = _find_slack_blob(carrier)
    if hit:
        raise ValidationError(
            f"Section '{hit[0].section}' already contains a StegoNexus slack blob.")
    regions = slack_regions(carrier)
    if not regions:
        raise CapacityError(
            "Carrier has no section padding (slack) to hide in. Use the "
            "'overlay' technique or a carrier built with padded sections.")
    region = regions[-1]                      # last padded section (classic spot)
    capacity = region.slack_len - len(blob)
    if capacity < 0:
        raise CapacityError(
            f"Payload needs {len(blob)} bytes but section '{region.section}' "
            f"only has {region.slack_len} bytes of slack. Choose a smaller "
            "secret or the 'overlay' technique.")
    mutable = bytearray(data)
    slack_end = region.slack_offset + region.slack_len
    mutable[region.slack_offset:slack_end] = blob + b"\x00" * capacity
    with open(out, "wb") as fh:
        fh.write(mutable)
    return ExecStegoResult(
        output_path=str(out), technique=TECHNIQUE_SLACK,
        carrier_bytes=len(data), output_bytes=len(mutable),
        payload_bytes=len(secret), blob_bytes=len(blob),
        hidden_filename=Path(payload_path).name,
        size_unchanged=len(mutable) == len(data), section=region.section,
        stats={"cipher": "AES-256-GCM", "pbkdf2_iterations": PBKDF2_ITERATIONS,
               "slack_bytes": region.slack_len, "unused_slack": capacity})


def extract(stego_path: Path, key: str) -> ExecStegoExtract:
    """Recover the hidden payload (tries the overlay trailer, then slack)."""
    validate_key(key)
    p = Path(stego_path)
    if has_overlay(p):
        size = p.stat().st_size
        with open(p, "rb") as fh:
            fh.seek(size - TRAILER_LEN)
            (blob_len,) = struct.unpack(">Q", fh.read(8))
            if blob_len <= 0 or blob_len + TRAILER_LEN > size:
                raise CorruptedCarrier("Trailer declares an impossible size.")
            fh.seek(size - TRAILER_LEN - blob_len)
            blob = fh.read(blob_len)
        return _parse_blob(blob, key, TECHNIQUE_OVERLAY, section="<overlay>")
    hit = _find_slack_blob(p)
    if hit:
        region, blob = hit
        return _parse_blob(blob, key, TECHNIQUE_SLACK, section=region.section)
    raise CorruptedCarrier(
        "No executable-stego blob found (no overlay trailer, no slack marker).")


def strip_overlay(stego_path: Path, output_path: Path) -> dict:
    """Remove an overlay blob, restoring the carrier bytes only."""
    if not has_overlay(stego_path):
        raise CorruptedCarrier("Nothing to strip - no overlay trailer found.")
    size = Path(stego_path).stat().st_size
    with open(stego_path, "rb") as fh:
        fh.seek(size - TRAILER_LEN)
        (blob_len,) = struct.unpack(">Q", fh.read(8))
        fh.seek(0)
        clean = fh.read(size - blob_len - TRAILER_LEN)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(clean)
    return {"output": str(out), "clean_bytes": len(clean),
            "removed_bytes": size - len(clean)}


def scan(path: Path) -> dict:
    """Defensive detection: overlay presence + slack capacities + markers."""
    p = Path(path)
    report = pe.parse(p)
    regions = [r.as_dict() for r in slack_regions(p)]
    hit = _find_slack_blob(p)
    size = p.stat().st_size
    start = overlay_start(p)
    return {
        "path": str(p), "is_pe": report.is_pe, "file_size": size,
        "overlay_start": start,
        "overlay_bytes": max(0, size - start),
        "has_stego_overlay": has_overlay(p),
        "slack_regions": regions,
        "total_slack": sum(r["slack_len"] for r in regions),
        "slack_blob": {"section": hit[0].section, "bytes": len(hit[1])} if hit else None,
        "note": ("Static byte inspection on the file only - the specimen is "
                 "never opened, parsed by the OS, or executed."),
    }
