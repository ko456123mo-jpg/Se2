"""Key-derived carrier ordering for the binary LSB engines.

The pure-Python Fisher-Yates shuffle in :mod:`app.steganography.bitstream` is
fine for text documents, but images, audio and video carriers contain millions
of embeddable slots.  Those engines use this numpy-backed generator instead -
same idea (deterministic, key-seeded, no replacement), C-speed.
"""
from __future__ import annotations

import hashlib

import numpy as np


def key_seed(key: str, salt: str) -> int:
    """Derive a stable 64-bit seed from a user key."""
    digest = hashlib.sha256(salt.encode("utf-8") + key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def permutation(n: int, key: str, salt: str) -> np.ndarray:
    """Deterministic key-derived permutation of ``range(n)``."""
    if n <= 0:
        return np.empty(0, dtype=np.int64)
    rng = np.random.default_rng(key_seed(key, salt))
    return rng.permutation(n)


def pn_sequence(length: int, key: str, salt: str) -> np.ndarray:
    """Pseudo-noise +-1 sequence used by the spread-spectrum engines."""
    rng = np.random.default_rng(key_seed(key, salt) ^ 0x5DEECE66D)
    bits = rng.integers(0, 2, size=length, dtype=np.int8)
    return (bits.astype(np.float64) * 2.0) - 1.0
