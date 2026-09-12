"""Custom academic EOF / container hiding implementation.

Concept studied in the course material ("container hiding" / overlay data): a
secret blob is **appended after the logical end of the carrier file**.  Media
players, image viewers and many parsers stop at the structural end of the
container and therefore never show the extra bytes, while the file still opens
normally.

``StegoNexus implementation`` - this is *not* OpenPuff and it is **not**
OpenPuff-compatible.  OpenPuff is a Windows GUI tool; StegoNexus only detects
its presence and documents the workflow (see ``app/modules/video``).

Blob layout (little ceremony, all big-endian)::

    carrier bytes ...
    +-- SNXEOF0001 marker (10 B)
    +-- version (1 B)
    +-- salt (16 B)                      PBKDF2 salt
    +-- name_len (2 B) + original name (UTF-8)
    +-- AES-256-GCM ciphertext + 16 B tag
    +-- blob_len (8 B) + SNXEOF0001 marker (10 B)      <-- trailer

The trailer is what makes extraction fast: the reader seeks to the end, checks
the marker, and reads exactly one blob.
"""
from __future__ import annotations

import os
import struct
from dataclasses import dataclass, field
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

from app.core.constants import SNX_EOF_MARKER
from app.core.exceptions import CorruptedCarrier, IntegrityError, KeyOrPasswordError, ValidationError
from app.core.security import validate_key

TECHNIQUE = "video_container_eof"
TRAILER = struct.pack(">Q", 0)  # placeholder, filled at write time
VERSION = 1
TRAILER_LEN = 8 + len(SNX_EOF_MARKER)
PBKDF2_ITERATIONS = 200_000


@dataclass
class ContainerResult:
    output_path: str
    carrier_bytes: int
    payload_bytes: int
    blob_bytes: int
    output_bytes: int
    hidden_filename: str
    engine: str = "stegonexus-aes-gcm-eof"
    stats: dict = field(default_factory=dict)


@dataclass
class ContainerExtract:
    payload: bytes
    original_name: str
    blob_bytes: int
    clean_carrier_size: int
    engine: str = "stegonexus-aes-gcm-eof"


def _derive_key(key: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                     iterations=PBKDF2_ITERATIONS)
    return kdf.derive(key.encode("utf-8"))


def has_container(path: Path) -> bool:
    """True when the file ends with a StegoNexus EOF container trailer."""
    p = Path(path)
    size = p.stat().st_size
    if size < TRAILER_LEN:
        return False
    with open(p, "rb") as fh:
        fh.seek(size - TRAILER_LEN)
        trailer = fh.read(TRAILER_LEN)
    return trailer.endswith(SNX_EOF_MARKER)


def hide(carrier_path: Path, payload_path: Path, output_path: Path,
         key: str) -> ContainerResult:
    """Append an encrypted container after the carrier data."""
    validate_key(key)
    carrier = Path(carrier_path).read_bytes()
    secret = Path(payload_path).read_bytes()
    if not secret:
        raise ValidationError("Secret file is empty.")
    name = Path(payload_path).name.encode("utf-8")
    if len(name) > 65535:
        raise ValidationError("Secret file name is too long to store.")

    salt = os.urandom(16)
    nonce = os.urandom(12)
    ciphertext = AESGCM(_derive_key(key, salt)).encrypt(nonce, secret, SNX_EOF_MARKER)
    blob = (SNX_EOF_MARKER + bytes([VERSION]) + salt + nonce
            + struct.pack(">H", len(name)) + name + ciphertext)
    trailer = struct.pack(">Q", len(blob)) + SNX_EOF_MARKER

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as fh:
        fh.write(carrier)
        fh.write(blob)
        fh.write(trailer)
    return ContainerResult(
        output_path=str(out), carrier_bytes=len(carrier), payload_bytes=len(secret),
        blob_bytes=len(blob), output_bytes=len(carrier) + len(blob) + TRAILER_LEN,
        hidden_filename=Path(payload_path).name,
        stats={"salt": salt.hex(), "pbkdf2_iterations": PBKDF2_ITERATIONS,
               "cipher": "AES-256-GCM", "trailer_bytes": TRAILER_LEN})


def extract(stego_path: Path, key: str) -> ContainerExtract:
    """Read and decrypt the appended container."""
    validate_key(key)
    p = Path(stego_path)
    size = p.stat().st_size
    if not has_container(p):
        raise CorruptedCarrier(
            "No StegoNexus EOF container trailer found at the end of this file.")
    with open(p, "rb") as fh:
        fh.seek(size - TRAILER_LEN)
        blob_len = struct.unpack(">Q", fh.read(8))[0]
        if blob_len <= 0 or blob_len + TRAILER_LEN > size:
            raise CorruptedCarrier("Container trailer declares an impossible size.")
        fh.seek(size - TRAILER_LEN - blob_len)
        blob = fh.read(blob_len)
    if not blob.startswith(SNX_EOF_MARKER):
        raise CorruptedCarrier("Container start marker is missing or corrupted.")
    version = blob[10]
    if version != VERSION:
        raise CorruptedCarrier(f"Unsupported container version {version}.")
    offset = 11
    salt = blob[offset:offset + 16]; offset += 16
    nonce = blob[offset:offset + 12]; offset += 12
    name_len = struct.unpack(">H", blob[offset:offset + 2])[0]; offset += 2
    name = blob[offset:offset + name_len].decode("utf-8", errors="replace")
    offset += name_len
    ciphertext = blob[offset:]
    try:
        payload = AESGCM(_derive_key(key, salt)).decrypt(nonce, ciphertext, SNX_EOF_MARKER)
    except Exception as exc:  # InvalidTag
        raise KeyOrPasswordError(
            "Decryption failed - wrong key/password, or the container was "
            "tampered with (AES-GCM authentication failed).") from exc
    return ContainerExtract(payload=payload, original_name=name, blob_bytes=blob_len,
                            clean_carrier_size=size - blob_len - TRAILER_LEN)


def strip(stego_path: Path, output_path: Path) -> dict:
    """Remove the hidden container, restoring the carrier bytes only."""
    if not has_container(stego_path):
        raise CorruptedCarrier("Nothing to strip - no container trailer found.")
    size = Path(stego_path).stat().st_size
    with open(stego_path, "rb") as fh:
        fh.seek(size - TRAILER_LEN)
        blob_len = struct.unpack(">Q", fh.read(8))[0]
        fh.seek(0)
        clean = fh.read(size - blob_len - TRAILER_LEN)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(clean)
    return {"output": str(out), "clean_bytes": len(clean), "removed_bytes": size - len(clean)}
