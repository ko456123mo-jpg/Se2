"""Steganography primitives: bit streams, key derivation, payload framing.

Everything here is pure Python + hashlib, deterministic and unit-testable.
The same framing is reused by the text, image, audio and video LSB engines so
an investigator sees one consistent payload format.
"""
from __future__ import annotations

import hashlib
import hmac
import struct
import zlib
from typing import Iterator, Sequence

from app.core.constants import SNX_BINARY_MAGIC, SNX_TEXT_MAGIC
from app.core.exceptions import CorruptedCarrier, IntegrityError, KeyOrPasswordError

VERSION = 1

# header layout (bits): magic 32 | version 8 | flags 8 | keycheck 16 | length 32 | crc32 32
HEADER_BITS = 128
HEADER_BYTES = HEADER_BITS // 8

FLAG_COMPRESSED = 0x01
FLAG_UTF8 = 0x02


# ------------------------------------------------------------------ bit helpers
def bytes_to_bits(data: bytes) -> list[int]:
    """MSB-first bit list."""
    out: list[int] = []
    for byte in data:
        for shift in range(7, -1, -1):
            out.append((byte >> shift) & 1)
    return out


def bits_to_bytes(bits: Sequence[int]) -> bytes:
    if len(bits) % 8:
        raise IntegrityError(
            f"Bit stream length {len(bits)} is not a multiple of 8.")
    out = bytearray()
    for i in range(0, len(bits), 8):
        byte = 0
        for bit in bits[i:i + 8]:
            byte = (byte << 1) | (bit & 1)
        out.append(byte)
    return bytes(out)


def int_to_bits(value: int, width: int) -> list[int]:
    if value < 0 or value >= (1 << width):
        raise ValueError(f"value {value} does not fit in {width} bits")
    return [(value >> shift) & 1 for shift in range(width - 1, -1, -1)]


def bits_to_int(bits: Sequence[int]) -> int:
    value = 0
    for bit in bits:
        value = (value << 1) | (bit & 1)
    return value


# ------------------------------------------------------------------- key stream
class KeyStream:
    """Deterministic key-stream generator.

    * ``bits(n)``       - SHA-256 counter-mode keystream, used to *encrypt* payload
      bits so that a wrong key never silently decodes to plausible data.
    * ``permutation(n)``- key-derived pseudo-random ordering, used to decide *where*
      the bits are placed (spreads the payload over the whole carrier).
    * ``check``         - 16-bit HMAC-SHA256 digest prefix stored in the header and
      used as the wrong-key detector.
    """

    def __init__(self, key: str, salt: str = "stegonexus-v1"):
        if not key:
            raise KeyOrPasswordError("A key/password is required.")
        self.key = key.encode("utf-8")
        self.salt = salt.encode("utf-8")

    # -- primitives
    def _block(self, counter: int) -> bytes:
        return hashlib.sha256(self.salt + self.key + struct.pack(">Q", counter)).digest()

    def bits(self, count: int) -> list[int]:
        out: list[int] = []
        counter = 0
        while len(out) < count:
            out.extend(bytes_to_bits(self._block(counter)))
            counter += 1
        return out[:count]

    def mask(self, bits: Sequence[int]) -> list[int]:
        """XOR the bit list with the keystream (self-inverse)."""
        stream = self.bits(len(bits))
        return [b ^ s for b, s in zip(bits, stream)]

    def permutation(self, count: int) -> list[int]:
        """Key-derived Fisher-Yates shuffle of ``range(count)``."""
        order = list(range(count))
        if count <= 1:
            return order
        # consume 2 bytes of keystream per swap, from a lazily produced stream
        stream = self._byte_stream()
        for i in range(count - 1, 0, -1):
            j = next(stream) % (i + 1)
            order[i], order[j] = order[j], order[i]
        return order

    def _byte_stream(self) -> Iterator[int]:
        counter = 0
        while True:
            block = hashlib.sha256(b"perm" + self.salt + self.key
                                   + struct.pack(">Q", counter)).digest()
            yield from block
            counter += 1

    @property
    def check(self) -> int:
        digest = hmac.new(self.key, b"keycheck" + self.salt, hashlib.sha256).digest()
        return struct.unpack(">H", digest[:2])[0]

    @property
    def fingerprint(self) -> str:
        """Non-reversible identifier of the key, safe to log/store."""
        return hmac.new(self.key, b"fingerprint", hashlib.sha256).hexdigest()[:16]


# --------------------------------------------------------------------- framing
def build_frame_parts(payload: bytes, keystream: KeyStream,
                      magic: bytes = SNX_BINARY_MAGIC,
                      compress: bool = True) -> tuple[list[int], list[int]]:
    """Return ``(header_bits, body_bits)``.

    The header is written **in the clear and at fixed carrier positions** so an
    investigator (and the extractor) can distinguish three situations cleanly:

    * no payload at all              -> magic mismatch  -> ``CorruptedCarrier``
    * payload present, wrong key     -> key-check fails -> ``KeyOrPasswordError``
    * payload present, right key     -> CRC verified    -> success

    The body is XOR-masked with the key stream and is placed in a key-derived
    order by the engine.
    """
    flags = 0
    body = payload
    if compress and len(payload) > 32:
        compressed = zlib.compress(payload, 6)
        if len(compressed) < len(payload):
            body = compressed
            flags |= FLAG_COMPRESSED
    try:
        payload.decode("utf-8")
        flags |= FLAG_UTF8
    except UnicodeDecodeError:
        pass

    crc = zlib.crc32(payload) & 0xFFFFFFFF
    header = (magic + bytes([VERSION, flags])
              + struct.pack(">H", keystream.check)
              + struct.pack(">I", len(body))
              + struct.pack(">I", crc))
    return bytes_to_bits(header), keystream.mask(bytes_to_bits(body))


def build_frame(payload: bytes, keystream: KeyStream, magic: bytes = SNX_BINARY_MAGIC,
                compress: bool = True) -> list[int]:
    """Concatenated ``header + body`` bit stream (single-block carriers)."""
    header_bits, body_bits = build_frame_parts(payload, keystream, magic, compress)
    return header_bits + body_bits


def frame_size_bits(payload: bytes, keystream: KeyStream,
                    magic: bytes = SNX_BINARY_MAGIC) -> int:
    """Number of carrier bits a payload will consume (for capacity checks)."""
    return len(build_frame(payload, keystream, magic=magic, compress=True))


class ParsedFrame:
    __slots__ = ("payload", "flags", "magic", "length", "crc", "header_bits")

    def __init__(self, payload: bytes, flags: int, magic: bytes, length: int,
                 crc: int, header_bits: int):
        self.payload = payload
        self.flags = flags
        self.magic = magic
        self.length = length
        self.crc = crc
        self.header_bits = header_bits


def parse_frame_parts(header_bits: Sequence[int], body_bits: Sequence[int],
                      keystream: KeyStream, magic: bytes = SNX_BINARY_MAGIC) -> ParsedFrame:
    """Decode a split frame (header at fixed positions, body in key order)."""
    if len(header_bits) < HEADER_BITS:
        raise CorruptedCarrier(
            f"Only {len(header_bits)} header bits available; {HEADER_BITS} required. "
            "Carrier does not contain a complete StegoNexus header.")
    header = bits_to_bytes(header_bits[:HEADER_BITS])
    got_magic = header[:4]
    if got_magic != magic:
        allowed = {SNX_BINARY_MAGIC, SNX_TEXT_MAGIC}
        if got_magic in allowed:
            raise CorruptedCarrier(
                "Payload magic does not match the selected technique "
                f"(found {got_magic!r}, expected {magic!r}).")
        raise CorruptedCarrier(
            "No valid StegoNexus payload header found in this carrier.")
    version, flags = header[4], header[5]
    if version != VERSION:
        raise CorruptedCarrier(f"Unsupported payload version {version}.")
    keycheck = struct.unpack(">H", header[6:8])[0]
    length = struct.unpack(">I", header[8:12])[0]
    crc = struct.unpack(">I", header[12:16])[0]
    if keycheck != keystream.check:
        raise KeyOrPasswordError(
            "Key/password does not match the one used to hide this data "
            "(payload header is present and valid).")
    body_bits = list(body_bits[:length * 8])
    if len(body_bits) < length * 8:
        raise CorruptedCarrier(
            f"Truncated payload: header declares {length} bytes, "
            f"carrier holds {len(body_bits) // 8}.")
    body = bits_to_bytes(keystream.mask(body_bits))
    payload = zlib.decompress(body) if flags & FLAG_COMPRESSED else body
    if (zlib.crc32(payload) & 0xFFFFFFFF) != crc:
        raise IntegrityError("CRC-32 mismatch - the payload is corrupted.")
    return ParsedFrame(payload=payload, flags=flags, magic=magic, length=length,
                       crc=crc, header_bits=HEADER_BITS)


def parse_frame(bits: Sequence[int], keystream: KeyStream,
                magic: bytes = SNX_BINARY_MAGIC) -> ParsedFrame:
    """Decode a concatenated frame produced by :func:`build_frame`."""
    if len(bits) < HEADER_BITS:
        raise CorruptedCarrier(
            f"Payload too short ({len(bits)} bits) to contain a StegoNexus header.")
    header = bits_to_bytes(bits[:HEADER_BITS])
    got_magic = header[:4]
    if got_magic != magic:
        allowed = {SNX_BINARY_MAGIC, SNX_TEXT_MAGIC}
        if got_magic in allowed:
            raise CorruptedCarrier(
                "Payload magic does not match the selected technique "
                f"(found {got_magic!r}, expected {magic!r}).")
        raise CorruptedCarrier(
            "No valid StegoNexus payload header found in this carrier.")
    version, flags = header[4], header[5]
    if version != VERSION:
        raise CorruptedCarrier(f"Unsupported payload version {version}.")
    keycheck = struct.unpack(">H", header[6:8])[0]
    length = struct.unpack(">I", header[8:12])[0]
    crc = struct.unpack(">I", header[12:16])[0]
    if keycheck != keystream.check:
        raise KeyOrPasswordError(
            "Key/password does not match the one used to hide this data.")
    body_bits = bits[HEADER_BITS:HEADER_BITS + length * 8]
    if len(body_bits) < length * 8:
        raise CorruptedCarrier(
            f"Truncated payload: header declares {length} bytes, "
            f"carrier holds {len(body_bits) // 8}.")
    body = bits_to_bytes(keystream.mask(body_bits))
    payload = zlib.decompress(body) if flags & FLAG_COMPRESSED else body
    if (zlib.crc32(payload) & 0xFFFFFFFF) != crc:
        raise IntegrityError("CRC-32 mismatch - the payload is corrupted.")
    return ParsedFrame(payload=payload, flags=flags, magic=magic, length=length,
                       crc=crc, header_bits=HEADER_BITS)


def text_payload_bytes(message: str) -> tuple[bytes, bool]:
    """Encode a text message; returns (bytes, utf8_flag)."""
    try:
        return message.encode("utf-8"), True
    except UnicodeEncodeError:  # pragma: no cover - utf-8 always encodes
        return message.encode("utf-8", errors="replace"), True


def decode_payload_text(payload: bytes) -> str:
    return payload.decode("utf-8", errors="replace")
