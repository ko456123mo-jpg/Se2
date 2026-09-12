"""Verification tests for the three SYNTHETIC training cases (A/B/C).

These exercise the same fixture builders the seeder uses, against the isolated test
config, and assert the *measured* outcomes (hash match, SNR, interpretation confidence).
"""
from __future__ import annotations

import seed_case_fixtures as fixtures


def test_case_a_image_and_metadata(samples):
    result = fixtures.case_a(samples)
    assert result["added_tags"] >= 1
    assert result["payload"] > 0
    assert result["verified"] is True


def test_case_b_audio_lsb(samples):
    result = fixtures.case_b(samples)
    assert result["snr_db"] > 60
    assert result["verified"] is True


def test_case_c_network_and_malware(samples):
    result = fixtures.case_c(samples)
    assert result["net_confidence"] in ("High", "Medium")
    assert isinstance(result["mal_indicators"], int)


def test_case_d_executable_stego(samples):
    result = fixtures.case_d(samples)
    assert result["verified"] is True
    assert result["slack_detected"] is True
    assert result["static_flag"] is True
