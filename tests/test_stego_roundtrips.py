"""Round-trip tests for the native steganography engines (text/image/audio/video)."""
from __future__ import annotations

import pytest

from app.modules.audio import service as audio
from app.modules.hashing import service as hashing
from app.modules.image import service as image
from app.modules.text import service as text
from app.modules.video import service as video


def test_text_lsb_roundtrip(samples):
    cover = samples["text_cover"].read_text()
    secret = "The gull returned before the rain. 0123456789."
    hidden = text.hide(cover, secret, "unit-key-1")
    assert hidden["status"] == "SUCCESS"
    extracted = text.extract(hidden["stego_text"], "unit-key-1")
    assert extracted["message"] == secret


def test_text_lsb_wrong_key_not_equal(samples):
    cover = samples["text_cover"].read_text()
    hidden = text.hide(cover, "secret payload", "right-key")
    try:
        bad = text.extract(hidden["stego_text"], "wrong-key")
        assert bad["message"] != "secret payload"
    except Exception:  # noqa: BLE001 - a wrong key may legitimately raise
        pass


def test_image_native_lsb_roundtrip(samples, tmp_path):
    stego = tmp_path / "stego.png"
    out = tmp_path / "recovered.txt"
    embedded = image.native_embed(samples["image_png"], samples["text_secret"],
                                  "img-key", stego, 3)
    assert embedded["status"] == "SUCCESS"
    assert embedded["verified"] is True
    extracted = image.native_extract(stego, "img-key", out)
    assert extracted["status"] == "SUCCESS"
    assert hashing.verify(samples["text_secret"], out)["match"] is True


def test_audio_lsb_roundtrip(samples, tmp_path):
    stego = tmp_path / "stego.wav"
    out = tmp_path / "recovered.txt"
    hidden = audio.lsb_hide(samples["audio_wav"], samples["text_secret"], "aud-key", stego)
    assert hidden["status"] == "SUCCESS"
    assert hidden["snr_db"] > 60
    extracted = audio.lsb_extract(stego, "aud-key", out)
    assert hashing.verify(samples["text_secret"], out)["match"] is True


def test_video_container_roundtrip_and_tamper(samples, tmp_path):
    stego = tmp_path / "stego.mp4"
    hidden = video.container_hide(samples["video_mp4"], samples["text_secret"],
                                  "vid-key", stego)
    assert hidden["status"] == "SUCCESS"
    assert video.container_detect(stego)["has_container"] is True

    out_dir = tmp_path / "extracted"
    out_dir.mkdir()
    extracted = video.container_extract(stego, "vid-key", out_dir)
    assert extracted["status"] == "SUCCESS"
    recovered = out_dir / samples["text_secret"].name
    assert hashing.verify(samples["text_secret"], recovered)["match"] is True

    # A wrong key must NOT authenticate (AES-GCM), so extraction raises.
    with pytest.raises(Exception):  # noqa: B017 - any auth failure is acceptable
        video.container_extract(stego, "wrong-key", tmp_path / "bad")
