"""Covert-channel payload encoding for the network laboratory.

Frame layout (all big-endian)::

    SNXNET1 (7 B) | version (1 B) | total_chunks (2 B) | length (4 B)
    | crc32 (4 B) | payload | zero padding to a 15-bit boundary

The frame is then split into 15-bit chunks.  Each chunk travels in the lower
15 bits of an IPv4 ``Identification`` field; bit 15 carries a parity flag over
the chunk index so that loss or reordering is detectable at the receiver.
"""
from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass, field

from app.core.constants import IPV4_ID_MAX, IPV4_ID_MIN, SNX_NET_MAGIC
from app.core.exceptions import CapacityError, CorruptedCarrier, IntegrityError, ValidationError

VERSION = 1
HEADER = SNX_NET_MAGIC + bytes([VERSION])  # 8 bytes
HEADER_LEN = len(HEADER)
CHUNK_BITS = 15
CHUNK_MASK = (1 << CHUNK_BITS) - 1


@dataclass
class EncodedPayload:
    chunks: list[int]                 # 15-bit payload chunks, in transmission order
    ip_ids: list[int]                 # IPv4 Identification values actually sent
    payload_bytes: int
    packet_count: int
    crc: int
    key_fingerprint: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def bits_used(self) -> int:
        return self.packet_count * CHUNK_BITS


def _parity(index: int) -> int:
    """Even parity over the binary representation of the chunk index."""
    return bin(index).count("1") & 1


def encode(payload: bytes, *, max_packets: int = 4096) -> EncodedPayload:
    """Split ``payload`` into IPv4 Identification field values."""
    if not payload:
        raise ValidationError("Payload is empty - nothing to encode.")
    crc = zlib.crc32(payload) & 0xFFFFFFFF
    body_bits = [(byte >> shift) & 1 for byte in payload for shift in range(7, -1, -1)]
    if len(body_bits) % CHUNK_BITS:
        body_bits += [0] * (CHUNK_BITS - len(body_bits) % CHUNK_BITS)
    # the header has a fixed size, so the packet count can be computed before
    # the header itself is written
    header_len_bits = (len(SNX_NET_MAGIC) + 1 + 2 + 4 + 4) * 8
    n_chunks = -(-(header_len_bits + len(body_bits)) // CHUNK_BITS)  # ceil
    if n_chunks > 0xFFFF:
        raise CapacityError(f"Payload needs {n_chunks} packets (> 65535).")
    if n_chunks > max_packets:
        raise CapacityError(
            f"Payload needs {n_chunks} packets; the laboratory limit is "
            f"{max_packets}. Reduce the payload or raise max_packets explicitly.")

    header = (SNX_NET_MAGIC + bytes([VERSION]) + struct.pack(">H", n_chunks)
              + struct.pack(">I", len(payload)) + struct.pack(">I", crc))
    bits = [(byte >> shift) & 1 for byte in header
            for shift in range(7, -1, -1)] + body_bits
    bits = bits[:n_chunks * CHUNK_BITS]
    if len(bits) < n_chunks * CHUNK_BITS:
        bits += [0] * (n_chunks * CHUNK_BITS - len(bits))

    chunks = []
    for start in range(0, len(bits), CHUNK_BITS):
        value = 0
        for bit in bits[start:start + CHUNK_BITS]:
            value = (value << 1) | bit
        chunks.append(value)
    # NOTE: id == 0 is a legal IPv4 Identification value and is used as-is.
    # Remapping it would silently corrupt payload bits.
    ip_ids = [((_parity(index) << CHUNK_BITS) | chunk) & 0xFFFF
              for index, chunk in enumerate(chunks)]
    return EncodedPayload(chunks=chunks, ip_ids=ip_ids, payload_bytes=len(payload),
                          packet_count=len(chunks), crc=crc,
                          notes=["Each packet carries 15 payload bits in IP.id",
                                 "Bit 15 holds an even-parity flag over the chunk index",
                                 "Empty UDP payload - the covert channel is the header",
                                 "IP.id == 0 is transmitted as 0 (no remapping)"])


def decode(ip_ids: list[int]) -> tuple[bytes, dict]:
    """Reassemble a payload from captured IPv4 Identification values."""
    if not ip_ids:
        raise CorruptedCarrier("No packets supplied for decoding.")
    parity_errors: list[int] = []
    bits: list[int] = []
    for index, ip_id in enumerate(ip_ids):
        if not 0 <= ip_id <= 0xFFFF:
            raise ValidationError(f"IP id {ip_id} is out of range.")
        expected = _parity(index)
        got = (ip_id >> CHUNK_BITS) & 1
        if got != expected:
            parity_errors.append(index)
        chunk = ip_id & CHUNK_MASK
        for shift in range(CHUNK_BITS - 1, -1, -1):
            bits.append((chunk >> shift) & 1)
    raw = bytearray()
    for start in range(0, len(bits) - len(bits) % 8, 8):
        byte = 0
        for bit in bits[start:start + 8]:
            byte = (byte << 1) | bit
        raw.append(byte)
    raw = bytes(raw)
    if raw[:7] != SNX_NET_MAGIC:
        raise CorruptedCarrier(
            "StegoNexus network magic not found - these packets do not carry a "
            "StegoNexus covert payload (or packets were lost/reordered).")
    version = raw[7]
    if version != VERSION:
        raise CorruptedCarrier(f"Unsupported network payload version {version}.")
    total_chunks = struct.unpack(">H", raw[8:10])[0]
    length = struct.unpack(">I", raw[10:14])[0]
    crc = struct.unpack(">I", raw[14:18])[0]
    payload = raw[18:18 + length]
    if len(payload) != length:
        raise IntegrityError(
            f"Payload truncated: header declares {length} bytes, "
            f"{len(payload)} recovered.")
    if (zlib.crc32(payload) & 0xFFFFFFFF) != crc:
        raise IntegrityError(
            "CRC-32 mismatch - the reassembled payload is incomplete or damaged "
            f"({len(parity_errors)} parity errors, expected {total_chunks} packets, "
            f"received {len(ip_ids)}).")
    info = {"packets": len(ip_ids), "expected_packets": total_chunks,
            "parity_errors": parity_errors, "payload_bytes": len(payload), "crc": crc}
    return payload, info
