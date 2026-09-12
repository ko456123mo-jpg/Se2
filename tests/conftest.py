"""Shared pytest fixtures: isolated config root + seeded benign samples.

The suite never touches the real ``data/`` tree - ``reset_config_for_tests`` points the
process-wide config at a throwaway directory, and ``seed_samples.seed`` recreates the
synthetic sample set inside it.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_TMP = Path(tempfile.mkdtemp(prefix="stegonexus-tests-"))

from app.core.config import reset_config_for_tests  # noqa: E402

reset_config_for_tests(_TMP)

import pytest  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
import seed_samples  # noqa: E402


@pytest.fixture(scope="session")
def samples() -> dict:
    return seed_samples.seed()


@pytest.fixture(scope="session")
def cfg():
    from app.core.config import get_config

    return get_config()
