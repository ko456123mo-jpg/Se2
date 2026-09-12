"""Shannon entropy analysis (project rule 18).

    H(X) = - SUM p(x) * log2 p(x)        [bits per byte, 0 .. 8]

Entropy is an **indicator, never proof**.  High entropy is produced by
compression, encryption and media codecs just as much as by hidden data, and
low entropy does not exclude embedding in a structured region.  The module
therefore always returns an interpretation string and, where useful, a
per-block profile so the analyst can see *where* the entropy is high.
"""
from __future__ import annotations

import math
from collections import Counter
from pathlib import Path

from app.core.exceptions import ValidationError
from app.core.models import EntropyReport
from app.core.security import validate_readable_file

CHUNK = 1024 * 1024


def entropy_bytes(data: bytes) -> float:
    """Shannon entropy of a byte sequence, in bits per byte."""
    if not data:
        return 0.0
    counts = Counter(data)
    total = len(data)
    return -sum((n / total) * math.log2(n / total) for n in counts.values())


def entropy_file(path: Path, block_size: int = 4096,
                 max_blocks: int = 4096) -> EntropyReport:
    """Entropy of a file plus a block profile (bounded memory usage)."""
    file_path = validate_readable_file(path)
    size = file_path.stat().st_size
    if block_size <= 0:
        raise ValidationError("block_size must be positive.")

    counts: Counter[int] = Counter()
    blocks: list[dict] = []
    offset = 0
    with open(file_path, "rb") as fh:
        while True:
            data = fh.read(CHUNK)
            if not data:
                break
            counts.update(data)
            for start in range(0, len(data), block_size):
                if len(blocks) >= max_blocks:
                    break
                chunk = data[start:start + block_size]
                if len(chunk) < 16:
                    continue
                value = entropy_bytes(chunk)
                blocks.append({"offset": offset + start, "size": len(chunk),
                               "entropy": round(value, 4)})
            offset += len(data)

    total = sum(counts.values())
    entropy = -sum((n / total) * math.log2(n / total) for n in counts.values()) if total else 0.0
    values = [b["entropy"] for b in blocks]
    high = sum(1 for v in values if v >= 7.5)
    report = EntropyReport(
        path=str(file_path), size=size, entropy=round(entropy, 4),
        interpretation=interpret(entropy), blocks=blocks, block_size=block_size,
        min_block=min(values) if values else 0.0,
        max_block=max(values) if values else 0.0,
        high_entropy_ratio=round(high / len(values), 4) if values else 0.0)
    return report


def interpret(entropy: float) -> str:
    """Human-readable interpretation with the mandatory caveat."""
    if entropy >= 7.9:
        band = ("Very high (>= 7.9): consistent with compressed or encrypted data. "
                "Also produced by ordinary ZIP/JPEG/MP4 content.")
    elif entropy >= 7.0:
        band = ("High (7.0-7.9): packed, compressed or encrypted sections are "
                "plausible - so are media codecs and already-compressed carriers.")
    elif entropy >= 4.5:
        band = "Moderate (4.5-7.0): typical for executables, documents and mixed data."
    elif entropy >= 2.0:
        band = "Low (2.0-4.5): typical for text, source code and structured data."
    else:
        band = "Very low (< 2.0): sparse, highly repetitive or mostly empty data."
    return (band + " Entropy is an indicator only - it is not proof of hidden data.")


def compare(original: Path, modified: Path) -> dict:
    """Before/after entropy comparison used by the metadata and hiding modules."""
    a = entropy_file(original)
    b = entropy_file(modified)
    return {"original": {"path": a.path, "entropy": a.entropy, "size": a.size},
            "modified": {"path": b.path, "entropy": b.entropy, "size": b.size},
            "delta": round(b.entropy - a.entropy, 4),
            "size_delta": b.size - a.size,
            "note": "A large entropy increase after an operation is consistent with "
                    "added encrypted/compressed data - it is an indicator, not proof."}
