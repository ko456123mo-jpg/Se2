"""Audio LSB steganography for PCM WAV carriers (native implementation).

The least significant bit of each 16-bit PCM sample is replaced by one payload
bit.  One LSB step is 1/32768 of full scale - far below the audible threshold,
which is exactly why the technique is studied in the course material.

The engine only reads/writes PCM WAV directly.  Other formats (MP3, FLAC, OGG)
are converted to a 16-bit PCM WAV working copy with FFmpeg first - see
:func:`prepare_wav` and ``AudioService``.
"""
from __future__ import annotations

import wave
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from app.core.constants import SNX_BINARY_MAGIC
from app.core.exceptions import CapacityError, UnsupportedFormat, ValidationError
from app.core.security import validate_key
from app.services.tool_executor import executor
from app.steganography import ordering
from app.steganography.bitstream import (HEADER_BITS, KeyStream, build_frame_parts,
                                         parse_frame_parts)

TECHNIQUE = "audio_lsb"
SALT = "stegonexus-audio-lsb-v1"
SUPPORTED_WIDTHS = (1, 2)  # 8-bit and 16-bit PCM handled natively


@dataclass
class AudioInfo:
    path: str
    channels: int
    sample_width: int
    frame_rate: int
    frames: int
    duration_s: float
    samples: int
    format_ok: bool
    note: str = ""

    def as_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class AudioStegoResult:
    output_path: str
    payload_bytes: int
    payload_bits: int
    capacity_bits: int
    utilisation: float
    key_fingerprint: str
    stats: dict = field(default_factory=dict)


def info(path: Path) -> AudioInfo:
    p = Path(path)
    try:
        with wave.open(str(p), "rb") as wav:
            channels = wav.getnchannels()
            width = wav.getsampwidth()
            rate = wav.getframerate()
            frames = wav.getnframes()
    except (wave.Error, EOFError) as exc:
        raise UnsupportedFormat(
            f"Not a readable PCM WAV file: {p} ({exc}). "
            "Convert it with FFmpeg first.") from exc
    ok = width in SUPPORTED_WIDTHS
    return AudioInfo(path=str(p), channels=channels, sample_width=width,
                     frame_rate=rate, frames=frames,
                     duration_s=round(frames / max(1, rate), 4),
                     samples=frames * channels, format_ok=ok,
                     note="" if ok else f"sample width {width} bytes unsupported "
                                        "by the native engine")


def capacity(path: Path) -> dict:
    inf = info(path)
    if not inf.format_ok:
        raise UnsupportedFormat(inf.note or "Unsupported PCM width.")
    usable = max(0, inf.samples - HEADER_BITS)
    return {"path": inf.path, "samples": inf.samples, "available_bits": inf.samples,
            "usable_bits": usable, "usable_bytes": usable // 8,
            "duration_s": inf.duration_s, "frame_rate": inf.frame_rate}


def _read_samples(path: Path) -> tuple[np.ndarray, "wave.Wave_read"]:
    with wave.open(str(path), "rb") as wav:
        params = wav.getparams()
        raw = wav.readframes(wav.getnframes())
    if params.sampwidth == 2:
        samples = np.frombuffer(raw, dtype="<i2")
    elif params.sampwidth == 1:
        # 8-bit PCM is unsigned, offset 128
        samples = (np.frombuffer(raw, dtype=np.uint8).astype(np.int16) - 128)
    else:
        raise UnsupportedFormat(
            f"Sample width {params.sampwidth} is not supported natively. "
            "Convert the carrier to 16-bit PCM WAV with FFmpeg.")
    return samples, params


def _write_samples(path: Path, samples: np.ndarray, params) -> None:
    if params.sampwidth == 2:
        data = samples.astype("<i2").tobytes()
    else:
        data = (samples.astype(np.int16) + 128).astype(np.uint8).tobytes()
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(params.nchannels)
        wav.setsampwidth(params.sampwidth)
        wav.setframerate(params.framerate)
        wav.writeframes(data)


def hide(carrier_path: Path, payload: bytes, key: str, output_path: Path) -> AudioStegoResult:
    """Embed ``payload`` into the LSB plane of a PCM WAV carrier."""
    if not payload:
        raise ValidationError("Payload is empty.")
    validate_key(key)
    samples, params = _read_samples(carrier_path)
    n = int(samples.size)
    keystream = KeyStream(key, salt=SALT)
    header_bits, body_bits = build_frame_parts(payload, keystream, magic=SNX_BINARY_MAGIC)
    needed = len(header_bits) + len(body_bits)
    if needed > n:
        raise CapacityError(
            f"Audio carrier too small: needs {needed} samples, carrier has {n}. "
            f"Payload is {len(payload)} bytes.",
            details={"needed_bits": needed, "available_bits": n})

    out = samples.copy()
    out[:len(header_bits)] = (out[:len(header_bits)] & ~np.int16(1)) | np.asarray(
        header_bits, dtype=np.int16)
    rest = out[len(header_bits):]
    order = ordering.permutation(int(rest.size), key, SALT)
    chosen = order[:len(body_bits)]
    rest[chosen] = (rest[chosen] & ~np.int16(1)) | np.asarray(body_bits, dtype=np.int16)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    _write_samples(Path(output_path), out, params)
    return AudioStegoResult(
        output_path=str(output_path), payload_bytes=len(payload), payload_bits=needed,
        capacity_bits=n, utilisation=round(needed / max(1, n), 6),
        key_fingerprint=keystream.fingerprint,
        stats={"samples": n, "channels": params.nchannels,
               "frame_rate": params.framerate, "duration_s": round(
                   params.nframes / max(1, params.framerate), 3),
               "samples_modified": int(np.count_nonzero(out != samples))})


def extract(stego_path: Path, key: str) -> bytes:
    """Recover the payload embedded by :func:`hide`."""
    validate_key(key)
    samples, _ = _read_samples(stego_path)
    header_bits = (samples[:HEADER_BITS] & 1).astype(np.int64).tolist()
    rest = samples[HEADER_BITS:]
    order = ordering.permutation(int(rest.size), key, SALT)
    body_bits = (rest[order] & 1).astype(np.int64).tolist()
    keystream = KeyStream(key, salt=SALT)
    parsed = parse_frame_parts(header_bits, body_bits, keystream, magic=SNX_BINARY_MAGIC)
    return parsed.payload


def prepare_wav(source: Path, output: Path) -> dict:
    """Convert any audio file to 16-bit stereo/mono PCM WAV using FFmpeg."""
    result = executor.run("ffmpeg", ["-y", "-i", str(source), "-acodec", "pcm_s16le",
                                     str(output)], raise_on_error=False)
    if not result.ok:
        raise UnsupportedFormat(
            f"FFmpeg could not convert {source} to PCM WAV: "
            f"{result.error or result.stderr.strip()[:300]}")
    return {"output": str(output), "command": result.command_display(),
            "returncode": result.returncode}


def snr_db(original: Path, stego: Path) -> float:
    """Signal-to-noise ratio between carrier and stego file (quality metric)."""
    a, _ = _read_samples(original)
    b, _ = _read_samples(stego)
    n = min(a.size, b.size)
    a = a[:n].astype(np.float64)
    b = b[:n].astype(np.float64)
    noise = b - a
    signal_power = float(np.mean(a ** 2))
    noise_power = float(np.mean(noise ** 2))
    if noise_power == 0:
        return float("inf")
    if signal_power == 0:
        return 0.0
    return float(10 * np.log10(signal_power / noise_power))
