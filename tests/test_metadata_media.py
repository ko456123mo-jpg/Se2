"""Metadata read/strip across image, audio and video carriers (never mutates source)."""
from __future__ import annotations

from app.modules.hashing import service as hashing
from app.modules.metadata import service as metadata


def test_metadata_read_image(samples):
    snap = metadata.read(samples["image_jpg"])
    assert snap.entries is not None  # may be empty; must not raise


def test_metadata_read_audio(samples):
    snap = metadata.read(samples["audio_wav"])
    assert isinstance(snap.source, str) and snap.source


def test_metadata_read_video(samples):
    snap = metadata.read(samples["video_mp4"])
    assert isinstance(snap.source, str) and snap.source


def test_strip_on_copy_preserves_original(samples, tmp_path):
    original_sha = hashing.hash_file(samples["image_jpg"]).sha256
    stripped = tmp_path / "stripped.jpg"
    metadata.strip(samples["image_jpg"], stripped)
    # Source bytes untouched.
    assert hashing.hash_file(samples["image_jpg"]).sha256 == original_sha
    assert stripped.exists()
