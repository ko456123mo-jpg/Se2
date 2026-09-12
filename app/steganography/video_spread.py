"""Educational spread-spectrum embedding for video frames.

Classification: ``Status.IMPLEMENTED`` for the *educational, lossless* path only.
Each payload bit is spread over ``chips_per_bit`` pixel slots of the first frame
with a key-derived +-1 pseudo-noise sequence and a small amplitude; extraction
correlates the same sequence.  This demonstrates the spreading principle inside a
video container, and it survives only lossless pipelines (FFV1/PNG) - it is not a
production robust-video-watermarking scheme, and StegoNexus does not claim one.
"""
from __future__ import annotations

import shutil
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

from app.core.exceptions import CapacityError, CorruptedCarrier, IntegrityError, KeyOrPasswordError
from app.core.security import validate_key
from app.steganography.ordering import pn_sequence
from app.steganography.video_lsb import _decode_frames, _encode_frames, probe

MAGIC = b"SNXV"
HEADER_BITS = 80
TECHNIQUE = "video_spread_spectrum"
SALT = "stegonexus-video-ss-v1"
DEFAULT_CHIPS = 2048
#: measured on the project test carrier: blind detection verified at alpha>=16
#: (PSNR 26.9 dB). Differential detection (reference video supplied) is reliable
#: from alpha=4, so it is the recommended forensic path.
DEFAULT_ALPHA = 16.0


@dataclass
class VideoSpreadResult:
    output_path: str
    payload_bytes: int
    bits_embedded: int
    chips_per_bit: int
    alpha: float
    frames_total: int
    process_gain_db: float
    verified: bool
    stats: dict = field(default_factory=dict)




def _build_frame(payload: bytes) -> tuple[list[int], bytes]:
    body = zlib.compress(payload, 6)
    crc = zlib.crc32(payload) & 0xFFFFFFFF
    header = MAGIC + struct.pack(">H", len(body)) + struct.pack(">I", crc)
    return ([(byte >> s) & 1 for byte in header for s in range(7, -1, -1)], body)


def _bits(data: bytes) -> list[int]:
    return [(b >> s) & 1 for b in data for s in range(7, -1, -1)]


def _unbits(bits: list[int]) -> bytes:
    out = bytearray()
    for i in range(0, len(bits) - len(bits) % 8, 8):
        byte = 0
        for bit in bits[i:i + 8]:
            byte = (byte << 1) | bit
        out.append(byte)
    return bytes(out)


def capacity(video: Path, chips_per_bit: int = DEFAULT_CHIPS) -> dict:
    info = probe(video)
    if not info.available:
        raise CorruptedCarrier(f"Cannot probe video: {info.error}")
    windows = (info.width * info.height * 3) // chips_per_bit
    return {"path": str(video), "width": info.width, "height": info.height,
            "chips_per_bit": chips_per_bit, "windows": windows,
            "usable_bits": max(0, windows - HEADER_BITS),
            "usable_bytes": max(0, windows - HEADER_BITS) // 8}


def hide(carrier_video: Path, payload: bytes, key: str, output_path: Path, *,
         chips_per_bit: int = DEFAULT_CHIPS, alpha: float = DEFAULT_ALPHA,
         work_dir: Path | None = None, verify: bool = True) -> VideoSpreadResult:
    validate_key(key)
    if not payload:
        raise CorruptedCarrier("Payload is empty.")
    chips = int(chips_per_bit)
    out = Path(output_path)
    info = probe(carrier_video)
    if not info.available:
        raise CorruptedCarrier(f"Cannot probe video: {info.error}")

    base_work = Path(work_dir) if work_dir else out.parent / f".snx_ss_{out.stem}"
    frame_dir = base_work / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    _decode_frames(carrier_video, frame_dir)
    frames = sorted(frame_dir.glob("frame_*.png"))
    if not frames:
        raise CorruptedCarrier("No frames decoded.")

    header_bits, body = _build_frame(payload)
    body_bits = _bits(body)
    frame_bits = header_bits + body_bits

    total_slots = sum(int(np.array(Image.open(f).convert("RGB")).size) for f in frames)
    windows_total = total_slots // chips
    if windows_total < len(frame_bits):
        raise CapacityError(
            f"Video offers {windows_total} spreading windows of {chips} slots; "
            f"{len(frame_bits)} are needed. Use a longer/larger video or fewer chips.")
    pn = pn_sequence(chips, key, SALT)

    # windows are numbered globally, frame by frame, so extraction can replay
    # exactly the same order
    window_index = 0
    used = 0
    for frame_path in frames:
        if window_index >= len(frame_bits):
            break
        array = np.array(Image.open(frame_path).convert("RGB"))
        view = array.reshape(-1)
        n_windows = view.size // chips
        for local in range(n_windows):
            if window_index >= len(frame_bits):
                break
            bit = frame_bits[window_index]
            chip_slice = slice(local * chips, (local + 1) * chips)
            original = view[chip_slice].astype(np.int16)
            modified = np.clip(original + (pn * alpha * (2 * bit - 1)).astype(np.int16),
                               0, 255).astype(np.uint8)
            view[chip_slice] = modified
            used += chips
            window_index += 1
        Image.fromarray(array, "RGB").save(frame_path)

    _encode_frames(frame_dir, out, info.fps, carrier_video,
                   has_audio=bool(info.audio_codec))
    shutil.rmtree(base_work, ignore_errors=True)

    result = VideoSpreadResult(
        output_path=str(out), payload_bytes=len(payload), bits_embedded=len(frame_bits),
        chips_per_bit=chips, alpha=alpha, frames_total=len(frames),
        process_gain_db=round(float(10 * np.log10(chips)), 2), verified=False,
        stats={"width": info.width, "height": info.height, "slots_used": int(used),
               "windows_total": int(windows_total), "output_codec": "ffv1"})
    if verify:
        try:
            result.verified = extract(out, key, chips_per_bit=chips) == payload
        except Exception as exc:
            result.stats["verification_error"] = f"{type(exc).__name__}: {exc}"
    return result


def extract(stego_video: Path, key: str, *, chips_per_bit: int = DEFAULT_CHIPS,
            work_dir: Path | None = None, reference_path: Path | None = None) -> bytes:
    """Correlate the chip sequence to recover the payload.

    ``reference_path`` enables *differential* detection: the clean carrier is
    decoded too and subtracted, which removes the image content and makes the
    detection reliable even at very low embedding amplitudes.
    """
    validate_key(key)
    chips = int(chips_per_bit)
    stego = Path(stego_video)
    base_work = Path(work_dir) if work_dir else stego.parent / f".snx_ssread_{stego.stem}"
    frame_dir = base_work / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    try:
        _decode_frames(stego, frame_dir)
        frames = sorted(frame_dir.glob("frame_*.png"))
        if not frames:
            raise CorruptedCarrier("No frames decoded from stego video.")
        pn = pn_sequence(chips, key, SALT)
        ref_frames: list[Path] = []
        ref_dir = None
        if reference_path is not None:
            ref_dir = base_work / "ref"
            ref_dir.mkdir(parents=True, exist_ok=True)
            _decode_frames(Path(reference_path), ref_dir)
            ref_frames = sorted(ref_dir.glob("frame_*.png"))
        bits: list[int] = []
        for index, frame_path in enumerate(frames):
            slots = np.array(Image.open(frame_path).convert("RGB")).reshape(-1)
            if ref_frames and index < len(ref_frames):
                ref = np.array(Image.open(ref_frames[index]).convert("RGB")).reshape(-1)
                n = min(slots.size, ref.size)
                slots = (slots[:n].astype(np.int16) - ref[:n].astype(np.int16)).astype(np.float64)
            n_windows = slots.size // chips
            if n_windows == 0:
                continue
            matrix = slots[:n_windows * chips].reshape(n_windows, chips).astype(np.float64)
            # remove the local mean: image DC leakage would otherwise dominate
            # the correlation and flip bits
            matrix = matrix - matrix.mean(axis=1, keepdims=True)
            correlations = matrix @ pn / chips
            bits.extend(1 if c >= 0 else 0 for c in correlations)
        if len(bits) < HEADER_BITS + 1:
            raise CorruptedCarrier("Video too small to hold a spread-spectrum header.")
        if _unbits(bits[:32]) != MAGIC:
            raise CorruptedCarrier(
                "No spread-spectrum video payload detected (magic mismatch). "
                "Check chips_per_bit and the key.")
        length = int.from_bytes(_unbits(bits[32:48]), "big")
        crc = struct.unpack(">I", _unbits(bits[48:80]))[0]
        body_bits = bits[HEADER_BITS:HEADER_BITS + length * 8]
        if len(body_bits) < length * 8:
            raise CorruptedCarrier("Truncated spread-spectrum payload.")
        try:
            payload = zlib.decompress(_unbits(body_bits))
        except zlib.error as exc:
            raise KeyOrPasswordError(
                "Decompression failed - wrong key/password or chips_per_bit.") from exc
        if (zlib.crc32(payload) & 0xFFFFFFFF) != crc:
            raise IntegrityError("CRC-32 mismatch in video spread-spectrum payload.")
        return payload
    finally:
        shutil.rmtree(base_work, ignore_errors=True)
