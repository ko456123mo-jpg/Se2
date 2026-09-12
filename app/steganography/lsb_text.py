"""Text steganography: LSB substitution with a key.

Course technique: *LSB + Key* implemented natively in Python (project rule 20 -
no external ready-made application).

Algorithm
---------
1. The cover text is scanned for **eligible characters** (ASCII letters and
   digits).  Only their least significant bit is modified, so every resulting
   character is still printable text.
2. The secret is framed (magic, version, flags, key-check, length, CRC-32),
   zlib-compressed and XOR-masked with a SHA-256 counter-mode key stream
   derived from the user key.
3. The frame bits are written into the LSB of eligible characters in a
   **key-derived pseudo-random order** (Fisher-Yates shuffle seeded by the key),
   which spreads the payload across the whole document instead of clustering it
   at the beginning.
4. Extraction repeats steps 1 and 3 with the same key and verifies the
   key-check and CRC-32.  A wrong key raises ``KeyOrPasswordError``.

Known artefact / detection indicator: an LSB flip changes a character by +-1
(e.g. ``a`` -> ``b``, ``3`` -> ``2``), so a heavily embedded document shows a
measurable LSB bias.  ``analyse()`` exposes exactly that measurement.
"""
from __future__ import annotations

import math
import string
from dataclasses import dataclass, field
from pathlib import Path

from app.core.constants import SNX_TEXT_MAGIC
from app.core.exceptions import CapacityError, ValidationError
from app.core.security import validate_key
from app.steganography.bitstream import (HEADER_BITS, KeyStream, build_frame_parts,
                                         parse_frame_parts)

_BASE_ALPHABET = frozenset(string.ascii_letters + string.digits)
#: Only characters whose LSB-flipped partner is *also* a letter/digit are
#: eligible, otherwise the flipped character would leave the eligible set and
#: desynchronise extraction ('a'->'`', 'z'->'{', 'A'->'@', 'Z'->'[').
ELIGIBLE = frozenset(c for c in _BASE_ALPHABET if chr(ord(c) ^ 1) in _BASE_ALPHABET)
EXCLUDED_FOR_REVERSIBILITY = sorted(_BASE_ALPHABET - ELIGIBLE)
TECHNIQUE = "text_lsb_key"


@dataclass
class TextCapacity:
    cover_chars: int
    eligible_chars: int
    available_bits: int
    reserved_header_bits: int = 128
    usable_bits: int = 0
    usable_bytes: int = 0

    def __post_init__(self) -> None:
        self.usable_bits = max(0, self.available_bits - self.reserved_header_bits)
        self.usable_bytes = self.usable_bits // 8


@dataclass
class TextStegoResult:
    stego_text: str
    payload_bits: int
    capacity_bits: int
    utilisation: float
    key_fingerprint: str
    stats: dict = field(default_factory=dict)


@dataclass
class TextAnalysis:
    eligible_chars: int
    lsb_ones: int
    lsb_zeros: int
    bias: float
    chi_square: float
    suspicious: bool
    assessment: str
    notes: list[str] = field(default_factory=list)


def _eligible_positions(text: str) -> list[int]:
    return [i for i, ch in enumerate(text) if ch in ELIGIBLE]


def capacity(cover_text: str) -> TextCapacity:
    positions = _eligible_positions(cover_text)
    return TextCapacity(cover_chars=len(cover_text), eligible_chars=len(positions),
                        available_bits=len(positions))


def hide(cover_text: str, message: str, key: str) -> TextStegoResult:
    """Embed ``message`` into ``cover_text`` using LSB substitution + key."""
    if not isinstance(cover_text, str):
        raise ValidationError("Cover text must be a string (or loaded text file).")
    if not message:
        raise ValidationError("Secret message must not be empty.")
    validate_key(key)
    keystream = KeyStream(key, salt="stegonexus-text-v1")
    payload = message.encode("utf-8")

    positions = _eligible_positions(cover_text)
    header_bits, body_bits = build_frame_parts(payload, keystream, magic=SNX_TEXT_MAGIC)
    needed = len(header_bits) + len(body_bits)
    if needed > len(positions):
        raise CapacityError(
            f"Cover text is too small: needs {needed} embeddable characters, "
            f"carrier offers {len(positions)}. Payload is {len(payload)} bytes.",
            details={"needed_bits": needed, "available_bits": len(positions)})

    chars = list(cover_text)

    def write(pos_list: list[int], bits: list[int]) -> None:
        for pos, bit in zip(pos_list, bits):
            code = ord(chars[pos])
            chars[pos] = chr((code & 0b1111_1110) | bit)

    # header -> fixed natural positions (gives precise wrong-key detection)
    write(positions[:len(header_bits)], header_bits)
    # body -> key-derived order across the remaining positions
    rest = positions[len(header_bits):]
    order = keystream.permutation(len(rest))
    write([rest[i] for i in order[:len(body_bits)]], body_bits)

    stego = "".join(chars)
    modified = sum(1 for a, b in zip(cover_text, stego) if a != b)
    return TextStegoResult(
        stego_text=stego,
        payload_bits=needed,
        capacity_bits=len(positions),
        utilisation=round(needed / max(1, len(positions)), 4),
        key_fingerprint=keystream.fingerprint,
        stats={
            "cover_chars": len(cover_text),
            "secret_bytes": len(payload),
            "modified_chars": modified,
            "modification_ratio": round(modified / max(1, len(cover_text)), 4),
            "eligible_chars": len(positions),
            "header_bits": len(header_bits),
            "body_bits": len(body_bits),
        })


def extract(stego_text: str, key: str) -> str:
    """Recover the hidden message; raises on wrong key or missing payload."""
    validate_key(key)
    keystream = KeyStream(key, salt="stegonexus-text-v1")
    positions = _eligible_positions(stego_text)
    if not positions:
        raise ValidationError("Stego text contains no embeddable characters.")
    lsb = [ord(stego_text[pos]) & 1 for pos in positions]
    header_bits = lsb[:HEADER_BITS]
    rest = lsb[HEADER_BITS:]
    order = keystream.permutation(len(rest))
    body_bits = [rest[i] for i in order]
    parsed = parse_frame_parts(header_bits, body_bits, keystream, magic=SNX_TEXT_MAGIC)
    return parsed.payload.decode("utf-8", errors="replace")


def analyse(stego_text: str, *, threshold: float = 0.03) -> TextAnalysis:
    """Statistical LSB analysis of a text document (indicator, not proof)."""
    positions = _eligible_positions(stego_text)
    ones = sum(ord(stego_text[p]) & 1 for p in positions)
    zeros = len(positions) - ones
    total = max(1, len(positions))
    ones_ratio = ones / total
    chi = ((ones - total / 2) ** 2 + (zeros - total / 2) ** 2) / (total / 2)
    suspicious = len(positions) > 200 and abs(ones_ratio - 0.5) > threshold
    if suspicious:
        assessment = (f"LSB bias detected (ones={ones_ratio:.3f}, "
                      f"chi2={chi:.2f}). This is an *indicator* of LSB embedding, "
                      "not proof - natural text can be biased too.")
    else:
        assessment = ("No significant LSB bias. Absence of bias does not prove the "
                      "document is clean.")
    notes = [
        f"eligible characters: {len(positions)}",
        f"LSB ones/zeros: {ones}/{zeros}",
        "Compare against an unmodified reference document when available.",
    ]
    return TextAnalysis(len(positions), ones, zeros, round(ones_ratio, 4),
                        round(chi, 3), suspicious, assessment, notes)


def hide_to_file(cover_path: Path, output_path: Path, message: str, key: str) -> TextStegoResult:
    cover = Path(cover_path).read_text(encoding="utf-8", errors="replace")
    result = hide(cover, message, key)
    Path(output_path).write_text(result.stego_text, encoding="utf-8")
    return result


def extract_from_file(stego_path: Path, key: str) -> str:
    return extract(Path(stego_path).read_text(encoding="utf-8", errors="replace"), key)


def shannon_entropy_bits(text: str) -> float:
    """Character-level Shannon entropy (bits/char) - useful companion metric."""
    if not text:
        return 0.0
    counts: dict[str, int] = {}
    for ch in text:
        counts[ch] = counts.get(ch, 0) + 1
    total = len(text)
    return -sum((n / total) * math.log2(n / total) for n in counts.values())
