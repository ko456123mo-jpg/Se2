"""Executable-carrier steganography (overlay + slack) - hide/extract/detect."""
from __future__ import annotations

import pytest

from app.core.exceptions import (CapacityError, CorruptedCarrier,
                                 KeyOrPasswordError, ValidationError)
from app.malware import pe as pe_parser
from app.modules.malware import service as malware
from app.steganography import pe_stego

pytest.importorskip("cryptography")


@pytest.fixture()
def pe_carrier(tmp_path):
    from scripts.seed_samples import build_synthetic_pe

    carrier = tmp_path / "training.exe"
    carrier.write_bytes(build_synthetic_pe())
    return carrier


@pytest.fixture()
def secret(tmp_path):
    payload = tmp_path / "secret.txt"
    payload.write_bytes(b"EXEC-STEGO-UNIT-PAYLOAD-0123456789")
    return payload


def test_carrier_is_parseable_pe_with_slack(pe_carrier):
    report = pe_parser.parse(pe_carrier)
    assert report.is_pe
    regions = pe_stego.slack_regions(pe_carrier)
    assert regions and regions[0].slack_len >= 512


def test_overlay_roundtrip(pe_carrier, secret, tmp_path):
    out = tmp_path / "overlay_out.exe"
    result = pe_stego.hide(pe_carrier, secret, out, "UnitKey1", "overlay")
    assert result.output_bytes > result.carrier_bytes
    extracted = pe_stego.extract(out, "UnitKey1")
    assert extracted.payload == secret.read_bytes()
    assert extracted.original_name == "secret.txt"
    assert extracted.technique == "overlay"
    # the carrier part is byte-identical to the original
    carrier_len = result.carrier_bytes
    assert out.read_bytes()[:carrier_len] == pe_carrier.read_bytes()


def test_slack_roundtrip_same_file_size(pe_carrier, secret, tmp_path):
    out = tmp_path / "slack_out.exe"
    result = pe_stego.hide(pe_carrier, secret, out, "UnitKey1", "slack")
    assert result.size_unchanged
    assert out.stat().st_size == pe_carrier.stat().st_size
    extracted = pe_stego.extract(out, "UnitKey1")
    assert extracted.payload == secret.read_bytes()
    assert extracted.technique == "slack"
    # the PE structure still parses after the hide
    assert pe_parser.parse(out).is_pe


def test_wrong_key_fails(pe_carrier, secret, tmp_path):
    out = tmp_path / "stego.exe"
    pe_stego.hide(pe_carrier, secret, out, "UnitKey1", "overlay")
    with pytest.raises(KeyOrPasswordError):
        pe_stego.extract(out, "Wrong1")


def test_scan_detects_both_techniques(pe_carrier, secret, tmp_path):
    overlay_out = tmp_path / "o.exe"
    slack_out = tmp_path / "s.exe"
    pe_stego.hide(pe_carrier, secret, overlay_out, "UnitKey1", "overlay")
    pe_stego.hide(pe_carrier, secret, slack_out, "UnitKey1", "slack")
    scan_overlay = pe_stego.scan(overlay_out)
    scan_slack = pe_stego.scan(slack_out)
    scan_clean = pe_stego.scan(pe_carrier)
    assert scan_overlay["has_stego_overlay"]
    assert scan_slack["slack_blob"] is not None
    assert not scan_clean["has_stego_overlay"] and scan_clean["slack_blob"] is None


def test_no_stacking_and_capacity(pe_carrier, secret, tmp_path):
    out = tmp_path / "once.exe"
    pe_stego.hide(pe_carrier, secret, out, "UnitKey1", "overlay")
    with pytest.raises(ValidationError):
        pe_stego.hide(out, secret, tmp_path / "twice.exe", "UnitKey1", "overlay")
    big = tmp_path / "big.bin"
    big.write_bytes(b"X" * 5000)
    with pytest.raises(CapacityError):
        pe_stego.hide(pe_carrier, big, tmp_path / "cap.exe", "UnitKey1", "slack")


def test_extract_without_blob_raises(tmp_path):
    plain = tmp_path / "plain.txt"
    plain.write_bytes("nothing hidden here".encode())
    with pytest.raises(CorruptedCarrier):
        pe_stego.extract(plain, "UnitKey1")


def test_service_hide_extract_scan(pe_carrier, secret, tmp_path):
    out = tmp_path / "svc.exe"
    hidden = malware.executable_hide(pe_carrier, secret, out, "UnitKey1",
                                     "slack", case_id=None)
    assert hidden["size_unchanged"] and hidden["technique"] == "slack"
    extracted = malware.executable_extract(out, tmp_path / "recovered",
                                           "UnitKey1")
    assert extracted["payload_bytes"] == secret.stat().st_size
    from app.modules.hashing.service import hash_file

    assert extracted["sha256"] == hash_file(secret).sha256
    scanned = malware.executable_scan(out)
    assert scanned["slack_blob"] is not None


def test_static_analysis_flags_hidden_payload(pe_carrier, secret, tmp_path):
    out = tmp_path / "flagged.exe"
    pe_stego.hide(pe_carrier, secret, out, "UnitKey1", "slack")
    report = malware.static_analysis(out)
    families = " ".join(report["indicators"])
    assert "Executable stego" in families
    assert isinstance(report["executable_stego"], dict)
