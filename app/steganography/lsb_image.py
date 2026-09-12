"""Native image LSB steganography (lossless carriers only).

This is a StegoNexus **custom implementation** - it is *not* Steghide and it is
*not* OpenPuff compatible.  Steghide (the studied course tool) is integrated
separately in :mod:`app.modules.image.service` and is used for JPEG/BMP/WAV/AU
carriers through the ToolExecutor.

Rules implemented:

* lossless output only (PNG / BMP / TIFF) - saving LSB data as JPEG destroys it;
* header written at fixed natural slot positions, body in key-derived order;
* payload body XOR-masked with the key stream (wrong key -> explicit error);
* the source image is never modified in place.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

from app.core.constants import SNX_BINARY_MAGIC
from app.core.exceptions import CapacityError, UnsupportedFormat, ValidationError
from app.core.security import validate_key
from app.steganography import ordering
from app.steganography.bitstream import (HEADER_BITS, KeyStream, build_frame_parts,
                                         parse_frame_parts)

LOSSLESS_OUTPUT = {".png", ".bmp", ".tif", ".tiff"}
TECHNIQUE = "image_lsb_native"
SALT = "stegonexus-image-lsb-v1"


@dataclass
class ImageCapacity:
    path: str
    width: int
    height: int
    channels: int
    total_slots: int
    usable_bits: int
    usable_bytes: int
    format: str

    def as_dict(self) -> dict:
        return {
            "path": self.path, "width": self.width, "height": self.height,
            "channels": self.channels, "total_slots": self.total_slots,
            "usable_bits": self.usable_bits, "usable_bytes": self.usable_bytes,
            "format": self.format,
        }


@dataclass
class ImageStegoResult:
    output_path: str
    payload_bytes: int
    payload_bits: int
    capacity_bits: int
    utilisation: float
    key_fingerprint: str
    channels: int
    stats: dict = field(default_factory=dict)


def _open_rgb(path: Path) -> Image.Image:
    try:
        image = Image.open(path)
        image.load()
    except Exception as exc:
        raise UnsupportedFormat(f"Cannot decode image {path}: {exc}") from exc
    if image.mode not in ("RGB", "RGBA", "L"):
        image = image.convert("RGB")
    return image


def capacity(path: Path) -> ImageCapacity:
    image = _open_rgb(Path(path))
    channels = len(image.getbands())
    total = image.width * image.height * channels
    return ImageCapacity(path=str(path), width=image.width, height=image.height,
                         channels=channels, total_slots=total,
                         usable_bits=max(0, total - HEADER_BITS),
                         usable_bytes=max(0, (total - HEADER_BITS)) // 8,
                         format=image.format or "unknown")


def hide(carrier_path: Path, payload: bytes, key: str, output_path: Path,
         channels: int = 3) -> ImageStegoResult:
    """Embed ``payload`` into the LSB plane of a lossless image."""
    carrier = Path(carrier_path)
    out = Path(output_path)
    if not payload:
        raise ValidationError("Payload is empty.")
    validate_key(key)
    if out.suffix.lower() not in LOSSLESS_OUTPUT:
        raise UnsupportedFormat(
            f"LSB output must be lossless ({', '.join(sorted(LOSSLESS_OUTPUT))}); "
            f"requested '{out.suffix}'. Lossy formats destroy LSB data.")

    image = _open_rgb(carrier)
    bands = image.getbands()
    use_channels = min(channels, len(bands))
    if use_channels < 1:
        raise ValidationError("At least one channel is required.")

    array = np.array(image)
    if array.ndim == 2:
        array = array[:, :, None]
    # only touch the selected channels; leave the rest untouched
    channel_index = [bands.index(c) for c in ("R", "G", "B")[:use_channels]
                     if c in bands] or [0]
    height, width, depth = array.shape
    # ``flat`` is a *view* of ``array`` (contiguous), so writing through it
    # modifies the image we are going to save.  Fancy indexing would silently
    # return a copy, so the slot positions are computed explicitly instead.
    flat = array.reshape(-1)
    slot_map = np.arange(height * width * depth).reshape(height, width, depth)
    positions = slot_map[:, :, channel_index].reshape(-1)
    n_slots = int(positions.size)

    keystream = KeyStream(key, salt=SALT)
    header_bits, body_bits = build_frame_parts(payload, keystream, magic=SNX_BINARY_MAGIC)
    needed = len(header_bits) + len(body_bits)
    if needed > n_slots:
        raise CapacityError(
            f"Carrier too small: needs {needed} bits, image offers {n_slots} "
            f"({image.width}x{image.height}, {len(channel_index)} channels). "
            f"Payload is {len(payload)} bytes.",
            details={"needed_bits": needed, "available_bits": n_slots})

    before_lsb = flat[positions] & 1
    head_slots = positions[:len(header_bits)]
    flat[head_slots] = (flat[head_slots] & 0xFE) | np.asarray(header_bits,
                                                             dtype=flat.dtype)
    rest = positions[len(header_bits):]
    order = ordering.permutation(int(rest.size), key, SALT)
    chosen = rest[order[:len(body_bits)]]
    flat[chosen] = (flat[chosen] & 0xFE) | np.asarray(body_bits, dtype=flat.dtype)

    modified = int(np.count_nonzero(before_lsb != (flat[positions] & 1)))
    image_out = Image.fromarray(array, mode=image.mode)
    save_kwargs = {"optimize": True} if out.suffix.lower() == ".png" else {}
    image_out.save(out, **save_kwargs)

    return ImageStegoResult(
        output_path=str(out), payload_bytes=len(payload), payload_bits=needed,
        capacity_bits=n_slots, utilisation=round(needed / max(1, n_slots), 6),
        key_fingerprint=keystream.fingerprint, channels=len(channel_index),
        stats={"width": image.width, "height": image.height,
               "channels_used": channel_index, "slots_modified": modified,
               "modification_ratio": round(modified / max(1, n_slots), 6)})


def extract(stego_path: Path, key: str) -> bytes:
    """Recover the embedded payload from a native LSB stego image."""
    validate_key(key)
    image = _open_rgb(Path(stego_path))
    array = np.array(image)
    if array.ndim == 2:
        array = array[:, :, None]
    slots = array.reshape(-1)
    header_bits = (slots[:HEADER_BITS] & 1).astype(np.int64).tolist()
    rest = slots[HEADER_BITS:]  # NOTE: extraction reads every channel
    order = ordering.permutation(int(rest.size), key, SALT)
    body_bits = (rest[order] & 1).astype(np.int64).tolist()
    keystream = KeyStream(key, salt=SALT)
    parsed = parse_frame_parts(header_bits, body_bits, keystream, magic=SNX_BINARY_MAGIC)
    return parsed.payload


def analyse(stego_path: Path, *, reference_path: Path | None = None) -> dict:
    """LSB-plane statistics for a single image (indicator, not proof)."""
    image = _open_rgb(Path(stego_path))
    array = np.array(image).astype(np.int64)
    lsb = (array & 1).reshape(-1)
    ones = int(np.count_nonzero(lsb))
    total = int(lsb.size)
    ratio = ones / max(1, total)
    chi2 = ((ones - total / 2) ** 2 + ((total - ones) - total / 2) ** 2) / (total / 2)
    result: dict = {
        "path": str(stego_path), "slots": total, "lsb_ones": ones,
        "lsb_ratio": round(ratio, 5), "chi_square": round(float(chi2), 3),
        "suspicious": bool(total > 1000 and abs(ratio - 0.5) > 0.01),
        "assessment": "",
        "reference": None,
    }
    if reference_path:
        ref = np.array(_open_rgb(Path(reference_path))).astype(np.int64)
        if ref.shape == array.shape:
            diff = int(np.count_nonzero((ref & 0xFE) != (array & 0xFE)) +
                       np.count_nonzero((ref & 1) != (array & 1)))
            lsb_diff = int(np.count_nonzero((ref & 1) != (array & 1)))
            result["reference"] = {
                "path": str(reference_path),
                "differing_lsb_slots": lsb_diff,
                "differing_slots": diff,
                "lsb_change_ratio": round(lsb_diff / max(1, total), 5),
            }
        else:
            result["reference"] = {"error": "reference image has different dimensions"}
    result["assessment"] = (
        "LSB plane deviates from uniform - an *indicator* of LSB embedding. "
        "Compressed or noisy images can show the same pattern; this is not proof."
        if result["suspicious"] else
        "LSB plane is statistically close to uniform. Clean statistics do not "
        "prove the absence of steganography (e.g. Steghide uses a different method).")
    return result
