"""Educational Direct-Sequence Spread-Spectrum (DSSS) embedding for AUDIO (WAV).

Classification: ``Status.IMPLEMENTED`` for the educational, lossless (16-bit PCM
WAV) path.  Each payload bit is spread over ``chips_per_bit`` key-derived +-1
pseudo-noise chips, and each chip is repeated across ``span`` consecutive audio
samples and added at a small amplitude ``alpha``.  Extraction correlates the same
PN sequence:

* with the original carrier supplied as ``reference`` the host audio is cancelled
  first (differential detection - very robust);
* otherwise a blind / non-coherent detector is used (process gain ~= chips*span).

This demonstrates the spreading principle on a real audio signal.  It survives
only lossless PCM pipelines; StegoNexus does not claim a production robust
audio-watermarking scheme.
"""
from __future__ import annotations

import struct
import wave
import zlib
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from app.core.exceptions import (CapacityError, CorruptedCarrier, IntegrityError,
                                 UnsupportedFormat)
from app.core.security import validate_key
from app.steganography.ordering import pn_sequence

MAGIC = b"SNXA"
HEADER_BITS = 80            # MAGIC(4) + body_len(2) + crc(4) = 10 bytes = 80 bits
SALT = "stegonexus-audio-ss-v1"
TECHNIQUE = "audio_spread_spectrum"
DEFAULT_CHIPS = 512         # PN chips per payload bit
DEFAULT_SPAN = 4            # samples per chip (extra processing gain)
DEFAULT_ALPHA = 900.0       # +-900 out of 32767 (~2.7% of full scale)


@dataclass
class AudioSpreadResult:
    output_path: str
    payload_bytes: int
    bits_embedded: int
    chips_per_bit: int
    span: int
    alpha: float
    samples_total: int
    process_gain_db: float
    snr_db: float
    verified: bool
    stats: dict = field(default_factory=dict)


@dataclass
class AudioExtractResult:
    payload: bytes
    differential: bool
    mean_correlation: float
    assessment: str


# --------------------------------------------------------------------- WAV I/O
def _read_wav(path: Path) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    with wave.open(str(path), "rb") as w:
        nch = w.getnchannels()
        sw = w.getsampwidth()
        fr = w.getframerate()
        nf = w.getnframes()
        raw = w.readframes(nf)
    if sw != 2:
        raise UnsupportedFormat(
            f"audio spread-spectrum needs 16-bit PCM WAV (got {sw * 8}-bit). "
            "Convert first: ffmpeg -i in -c:a pcm_s16le out.wav")
    samples = np.frombuffer(raw, dtype="<i2").astype(np.float64)
    return samples, (nch, sw, fr, nf)


def _write_wav(path: Path, samples: np.ndarray, params) -> None:
    nch, sw, fr, _nf = params
    clipped = np.clip(np.round(samples), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(nch)
        w.setsampwidth(sw)
        w.setframerate(fr)
        w.writeframes(clipped.tobytes())


# ------------------------------------------------------------------- framing
def _frame(payload: bytes) -> tuple[list[int], bytes]:
    body = zlib.compress(payload, 6)
    crc = zlib.crc32(payload) & 0xFFFFFFFF
    header = MAGIC + struct.pack(">H", len(body)) + struct.pack(">I", crc)
    header_bits = [(b >> s) & 1 for b in header for s in range(7, -1, -1)]
    return header_bits, body


def _bits(data: bytes) -> list[int]:
    return [(b >> s) & 1 for b in data for s in range(7, -1, -1)]


def _unbits(bits: list[int]) -> bytes:
    out = bytearray()
    for i in range(0, len(bits) - len(bits) % 8, 8):
        byte = 0
        for b in bits[i:i + 8]:
            byte = (byte << 1) | b
        out.append(byte)
    return bytes(out)


def capacity(path: Path, chips_per_bit: int = DEFAULT_CHIPS,
             span: int = DEFAULT_SPAN, **_ignored) -> dict:
    samples, _ = _read_wav(Path(path))
    region = chips_per_bit * span
    windows = len(samples) // region if region else 0
    return {"path": str(path), "samples": int(len(samples)),
            "chips_per_bit": chips_per_bit, "span": span, "windows": int(windows),
            "usable_bits": max(0, int(windows) - HEADER_BITS),
            "usable_bytes": max(0, int(windows) - HEADER_BITS) // 8}


# --------------------------------------------------------------------- engine
def hide(carrier: Path, payload: bytes, out: Path, key: str, *,
         chips_per_bit: int = DEFAULT_CHIPS, span: int = DEFAULT_SPAN,
         alpha: float = DEFAULT_ALPHA) -> AudioSpreadResult:
    validate_key(key)
    samples, params = _read_wav(Path(carrier))
    header_bits, body = _frame(payload)
    bits = header_bits + _bits(body)
    region = chips_per_bit * span
    needed = len(bits) * region
    if needed > len(samples):
        raise CapacityError(
            f"carrier too short: {len(bits)} bits need {needed} samples "
            f"(chips={chips_per_bit} x span={span}), carrier has {len(samples)}. "
            "Use a longer carrier or a smaller payload.")
    host = samples.copy()
    pn = pn_sequence(len(bits) * chips_per_bit, key, SALT)
    symbols = np.array([1.0 if b else -1.0 for b in bits], dtype=np.float64)
    chip_vals = symbols[:, None] * pn.reshape(len(bits), chips_per_bit) * alpha
    add = np.repeat(chip_vals, span, axis=1).reshape(-1)
    samples[:add.size] += add
    _write_wav(Path(out), samples, params)
    diff = samples - host
    process_gain = 10.0 * float(np.log10(max(1.0, chips_per_bit * span)))
    host_power = float(np.sum(host ** 2)) or 1.0
    snr = 10.0 * float(np.log10(float(np.sum(diff ** 2)) / host_power))
    return AudioSpreadResult(str(out), len(payload), len(bits), chips_per_bit, span,
                             alpha, int(len(samples)), round(process_gain, 2),
                             round(snr, 2), False,
                             {"body_bytes": len(body), "samples_used": int(add.size)})


def _detect(sig: np.ndarray, nbits: int, chips_per_bit: int, span: int,
            key: str) -> tuple[list[int], float]:
    region = chips_per_bit * span
    pn = pn_sequence(nbits * chips_per_bit, key, SALT).reshape(nbits, chips_per_bit)
    block = sig[:nbits * region].reshape(nbits, chips_per_bit, span)
    chip_sums = block.sum(axis=2)                 # (nbits, chips)
    corr = (chip_sums * pn).sum(axis=1)           # (nbits,)
    bits = (corr > 0).astype(int).tolist()
    return bits, float(np.mean(np.abs(corr))) if corr.size else 0.0


def extract(stego: Path, key: str, *, chips_per_bit: int = DEFAULT_CHIPS,
            span: int = DEFAULT_SPAN, reference_path: Path | None = None,
            **_ignored) -> AudioExtractResult:
    validate_key(key)
    samples, _ = _read_wav(Path(stego))
    differential = False
    sig = samples
    if reference_path is not None:
        try:
            ref, _ = _read_wav(Path(reference_path))
            if ref.size == samples.size:
                sig = samples - ref
                differential = True
        except Exception:
            differential = False
    region = chips_per_bit * span
    if samples.size < HEADER_BITS * region:
        raise CorruptedCarrier("carrier too short to hold a spread-spectrum header.")
    hbits, _mc = _detect(sig, HEADER_BITS, chips_per_bit, span, key)
    header = _unbits(hbits)
    if header[:4] != MAGIC:
        raise CorruptedCarrier(
            "audio spread-spectrum header not found (wrong key, or not a "
            "StegoNexus audio-SS file).")
    body_len = struct.unpack(">H", header[4:6])[0]
    crc_expect = struct.unpack(">I", header[6:10])[0]
    nbits = HEADER_BITS + body_len * 8
    if nbits * region > sig.size:
        raise CorruptedCarrier("declared payload exceeds carrier length (corrupted).")
    allbits, mc = _detect(sig, nbits, chips_per_bit, span, key)
    body = _unbits(allbits[HEADER_BITS:])
    try:
        payload = zlib.decompress(body)
    except zlib.error as exc:
        raise IntegrityError(f"payload decompression failed (wrong key?): {exc}") from exc
    if (zlib.crc32(payload) & 0xFFFFFFFF) != crc_expect:
        raise IntegrityError("CRC mismatch - wrong key or corrupted carrier.")
    assessment = ("differential detection (host cancelled)" if differential
                  else "blind non-coherent detection")
    return AudioExtractResult(payload, differential, round(mc, 3), assessment)
