"""Video LSB steganography over lossless FFV1 frames (FFmpeg workflow).

Course workflow: LSB modification across video frames, then a **lossless**
re-encode (FFV1 in a Matroska container) so the modified least significant bits
survive.  Any lossy re-encode (H.264 default settings, MJPEG, ...) destroys the
payload - which is why the engine refuses to produce lossy output.

Pipeline
--------
``ffprobe`` (stream facts) -> ``ffmpeg`` decode to PNG frames (rgb24, lossless)
-> per-frame LSB embedding (header in frame 0, body spread over all frames in a
key-derived order) -> ``ffmpeg`` re-encode with FFV1 -> automatic round-trip
verification by re-extraction.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

from app.core.constants import SNX_BINARY_MAGIC
from app.core.exceptions import CapacityError, CorruptedCarrier, ToolUnavailable, UnsupportedFormat
from app.core.security import validate_key
from app.services.tool_executor import executor
from app.steganography import ordering
from app.steganography.bitstream import HEADER_BITS, KeyStream, build_frame_parts, parse_frame_parts

TECHNIQUE = "video_lsb"
SALT = "stegonexus-video-lsb-v1"
FRAME_PATTERN = "frame_%08d.png"


@dataclass
class VideoInfo:
    path: str
    available: bool
    duration_s: float = 0.0
    fps: float = 0.0
    width: int = 0
    height: int = 0
    codec: str = ""
    pix_fmt: str = ""
    nb_frames: int = 0
    audio_codec: str = ""
    container: str = ""
    streams: list[dict] = field(default_factory=list)
    raw: dict = field(default_factory=dict)
    error: str = ""

    def as_dict(self) -> dict:
        d = self.__dict__.copy()
        d.pop("raw", None)
        return d


@dataclass
class VideoStegoResult:
    output_path: str
    payload_bytes: int
    payload_bits: int
    capacity_bits: int
    frames_used: int
    utilisation: float
    key_fingerprint: str
    verified: bool
    verification_error: str = ""
    stats: dict = field(default_factory=dict)


# --------------------------------------------------------------------- ffprobe
def probe(path: Path) -> VideoInfo:
    """Structured media facts from ``ffprobe`` (never guessed)."""
    result = executor.run("ffprobe", [
        "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path)])
    if not result.available:
        raise ToolUnavailable("ffprobe is not installed (sudo apt install ffmpeg).")
    if not result.ok:
        return VideoInfo(path=str(path), available=False,
                         error=result.stderr.strip()[:400] or "ffprobe failed")
    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        return VideoInfo(path=str(path), available=False, error=f"bad ffprobe JSON: {exc}")

    streams = data.get("streams", [])
    fmt = data.get("format", {})
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio = next((s for s in streams if s.get("codec_type") == "audio"), {})
    fps = 0.0
    rate = video.get("r_frame_rate", "0/1")
    try:
        num, den = (rate.split("/") + ["1"])[:2]
        fps = float(num) / float(den) if float(den) else 0.0
    except (ValueError, ZeroDivisionError):
        fps = 0.0
    nb_frames = int(video.get("nb_frames") or 0)
    duration = float(fmt.get("duration") or video.get("duration") or 0.0)
    if not nb_frames and duration and fps:
        nb_frames = int(round(duration * fps))
    return VideoInfo(
        path=str(path), available=True,
        duration_s=float(fmt.get("duration") or video.get("duration") or 0.0),
        fps=round(fps, 4), width=int(video.get("width") or 0),
        height=int(video.get("height") or 0), codec=video.get("codec_name", ""),
        pix_fmt=video.get("pix_fmt", ""), nb_frames=nb_frames,
        audio_codec=audio.get("codec_name", ""),
        container=fmt.get("format_name", ""), streams=streams, raw=data)


# ------------------------------------------------------------------ frame I/O
def _decode_frames(video: Path, work_dir: Path) -> tuple[Path, int]:
    work_dir.mkdir(parents=True, exist_ok=True)
    result = executor.run("ffmpeg", [
        "-y", "-i", str(video), "-pix_fmt", "rgb24",
        str(work_dir / FRAME_PATTERN)], raise_on_error=False)
    if not result.ok:
        raise UnsupportedFormat(
            f"FFmpeg could not decode frames from {video}: "
            f"{result.error or result.stderr.strip()[-300:]}")
    frames = sorted(work_dir.glob("frame_*.png"))
    if not frames:
        raise UnsupportedFormat("FFmpeg produced no frames.")
    return work_dir, len(frames)


def _encode_frames(work_dir: Path, output: Path, fps: float,
                   audio_source: Path | None, has_audio: bool = False) -> None:
    # input options first, output options (codec/pix_fmt) only after ALL inputs
    args = ["-y", "-framerate", f"{fps or 25}", "-i", str(work_dir / FRAME_PATTERN)]
    if has_audio and audio_source is not None and Path(audio_source).exists():
        args += ["-i", str(audio_source), "-map", "0:v:0", "-map", "1:a:0?",
                 "-c:a", "flac", "-shortest"]
    args += ["-c:v", "ffv1", "-level", "3", "-pix_fmt", "rgb24", str(output)]
    result = executor.run("ffmpeg", args, raise_on_error=False)
    if not result.ok:
        raise UnsupportedFormat(
            f"FFmpeg could not write the FFV1 output: "
            f"{result.error or result.stderr.strip()[-300:]}")


def _frame_slots(frame_path: Path) -> np.ndarray:
    array = np.array(Image.open(frame_path).convert("RGB"))
    return array.reshape(-1)


# ---------------------------------------------------------------------- engine
def hide(carrier_video: Path, payload: bytes, key: str, output_path: Path,
         work_dir: Path | None = None, keep_frames: bool = False,
         verify: bool = True) -> VideoStegoResult:
    """Embed ``payload`` into the LSB plane of every frame, output FFV1/MKV."""
    validate_key(key)
    if not payload:
        raise CorruptedCarrier("Payload is empty.")
    out = Path(output_path)
    if out.suffix.lower() not in (".mkv", ".avi", ".nut"):
        raise UnsupportedFormat(
            f"Video LSB output must be a lossless container (.mkv/.avi/.nut); "
            f"requested '{out.suffix}'. Lossy codecs destroy LSB data.")
    info = probe(carrier_video)
    if not info.available:
        raise UnsupportedFormat(f"Cannot analyse video: {info.error}")

    base_work = Path(work_dir) if work_dir else out.parent / f".snx_frames_{out.stem}"
    frame_dir = base_work / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    _decode_frames(carrier_video, frame_dir)
    frames = sorted(frame_dir.glob("frame_*.png"))

    keystream = KeyStream(key, salt=SALT)
    header_bits, body_bits = build_frame_parts(payload, keystream, magic=SNX_BINARY_MAGIC)

    total_slots = sum(int(_frame_slots(f).size) for f in frames)
    if len(header_bits) + len(body_bits) > total_slots:
        raise CapacityError(
            f"Video too small: needs {len(header_bits) + len(body_bits)} LSB slots, "
            f"{len(frames)} frames offer {total_slots}.")

    # frame 0 carries the header in its first natural slots
    first = np.array(Image.open(frames[0]).convert("RGB"))
    flat = first.reshape(-1)
    flat[:len(header_bits)] = (flat[:len(header_bits)] & 0xFE) | np.asarray(
        header_bits, dtype=flat.dtype)
    Image.fromarray(first, "RGB").save(frames[0])

    remaining = list(body_bits)
    for index, frame_path in enumerate(frames):
        if not remaining:
            break
        array = np.array(Image.open(frame_path).convert("RGB"))
        slots = array.reshape(-1)
        start = len(header_bits) if index == 0 else 0
        available = int(slots.size) - start
        if available <= 0:
            continue
        take = min(available, len(remaining))
        order = ordering.permutation(available, f"{key}|frame{index}", SALT)
        positions = start + order[:take]
        chunk = np.asarray(remaining[:take], dtype=slots.dtype)
        slots[positions] = (slots[positions] & 0xFE) | chunk
        remaining = remaining[take:]
        Image.fromarray(array, "RGB").save(frame_path)

    out.parent.mkdir(parents=True, exist_ok=True)
    _encode_frames(frame_dir, out, info.fps, carrier_video,
                   has_audio=bool(info.audio_codec))
    if not keep_frames:
        shutil.rmtree(base_work, ignore_errors=True)

    used = len(header_bits) + len(body_bits)
    result = VideoStegoResult(
        output_path=str(out), payload_bytes=len(payload), payload_bits=used,
        capacity_bits=total_slots, frames_used=len(frames),
        utilisation=round(used / max(1, total_slots), 8),
        key_fingerprint=keystream.fingerprint, verified=False,
        stats={"width": info.width, "height": info.height, "fps": info.fps,
               "source_codec": info.codec, "output_codec": "ffv1",
               "container": out.suffix.lower().lstrip("."),
               "frames": len(frames), "duration_s": info.duration_s})

    if verify:
        try:
            recovered = extract(out, key)
            result.verified = recovered == payload
            if not result.verified:
                result.verification_error = "Round-trip verification failed."
        except Exception as exc:  # pragma: no cover - verification is best effort
            result.verification_error = f"{type(exc).__name__}: {exc}"
    return result


def extract(stego_video: Path, key: str, work_dir: Path | None = None) -> bytes:
    """Recover the payload from an FFV1 stego video."""
    validate_key(key)
    stego = Path(stego_video)
    base_work = Path(work_dir) if work_dir else stego.parent / f".snx_read_{stego.stem}"
    frame_dir = base_work / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    try:
        _decode_frames(stego, frame_dir)
        frames = sorted(frame_dir.glob("frame_*.png"))
        if not frames:
            raise CorruptedCarrier("No frames could be decoded from the video.")
        keystream = KeyStream(key, salt=SALT)

        first = _frame_slots(frames[0])
        header_bits = (first[:HEADER_BITS] & 1).astype(np.int64).tolist()
        body_bits: list[int] = []
        for index, frame_path in enumerate(frames):
            slots = _frame_slots(frame_path)
            start = len(header_bits) if index == 0 else 0
            available = int(slots.size) - start
            if available <= 0:
                continue
            order = ordering.permutation(available, f"{key}|frame{index}", SALT)
            body_bits.extend((slots[start + order] & 1).astype(np.int64).tolist())
        parsed = parse_frame_parts(header_bits, body_bits, keystream,
                                   magic=SNX_BINARY_MAGIC)
        return parsed.payload
    finally:
        shutil.rmtree(base_work, ignore_errors=True)
