#!/usr/bin/env python3
"""Capture numbered, real per-view screenshots into a target directory.

Runs in its own process (fresh QApplication). Usage:
    QT_QPA_PLATFORM=offscreen python scripts/capture_numbered_screenshots.py <out_dir>
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QThreadPool  # noqa: E402
from app.gui.app import build_app  # noqa: E402

VIEW_SHOTS = [
    ("dashboard", "dashboard"), ("toolhealth", "tool_health"), ("cases", "cases"),
    ("evidence", "evidence"), ("findings", "findings"), ("logs", "logs"),
    ("reports", "reports"), ("metadata", "metadata"), ("forensics", "forensics"),
    ("hashing", "hashing"), ("extraction", "extraction"), ("text", "text"),
    ("image", "image"), ("audio", "audio"), ("video", "video"),
    ("network", "network"), ("malware", "malware"), ("externaltools", "external_tools"),
    ("settings", "settings"), ("about", "about"),
]


def main() -> int:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    app, window = build_app([])
    window.resize(1440, 900)
    window.show()
    for idx, (nav, name) in enumerate(VIEW_SHOTS, start=1):
        window.navigate(nav)
        QThreadPool.globalInstance().waitForDone(15000)
        for _ in range(4):
            app.processEvents()
        window.grab().save(str(out / f"{idx:02d}_{name}.png"))
    for suffix, nav in (("21_extraction_after", "extraction"),
                        ("22_logs_after", "logs"), ("23_reports_after", "reports")):
        window.navigate(nav)
        QThreadPool.globalInstance().waitForDone(15000)
        for _ in range(4):
            app.processEvents()
        window.grab().save(str(out / f"{suffix}.png"))
    print(f"captured {len(VIEW_SHOTS) + 3} screenshots into {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
