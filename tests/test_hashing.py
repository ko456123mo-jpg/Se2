"""Hashing service: known vectors + before/after verification."""
from __future__ import annotations

from app.modules.hashing import service as hashing


def test_known_vectors():
    digests = hashing.hash_bytes(b"abc")
    assert digests["md5"] == "900150983cd24fb0d6963f7d28e17f72"
    assert digests["sha256"] == ("ba7816bf8f01cfea414140de5dae2223"
                                 "b00361a396177a9cb410ff61f20015ad")
    assert set(digests) == {"md5", "sha1", "sha256", "sha512"}


def test_hash_file_and_verify(tmp_path):
    target = tmp_path / "a.bin"
    target.write_bytes(b"stegonexus integrity sample")
    result = hashing.hash_file(target)
    assert result.sha256 == hashing.hash_bytes(b"stegonexus integrity sample")["sha256"]

    same = tmp_path / "b.bin"
    same.write_bytes(b"stegonexus integrity sample")
    assert hashing.verify(target, same)["match"] is True

    different = tmp_path / "c.bin"
    different.write_bytes(b"tampered")
    assert hashing.verify(target, different)["match"] is False
