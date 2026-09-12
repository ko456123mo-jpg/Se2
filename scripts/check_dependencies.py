#!/usr/bin/env python3
"""Dependency checker: prints the measured tool/library matrix and exits non-zero
only when a *required* dependency is missing (none are required-missing in a clean
Kali build; optional tools degrade gracefully and are reported honestly).

Usage: python scripts/check_dependencies.py
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PYTHON_LIBS = {
    "PySide6": "GUI framework",
    "numpy": "numerics (audio/video/entropy)",
    "PIL": "image loading (Pillow)",
    "cryptography": "AES-256-GCM + PBKDF2",
    "scapy": "network laboratory",
}


def main() -> int:
    from app.services.tool_health import health

    rows = health.summary()["rows"]
    missing_required: list[str] = []
    print("Python libraries")
    print("-" * 70)
    for name, purpose in PYTHON_LIBS.items():
        try:
            mod = importlib.import_module(name)
            print(f"  [OK]        {name:<12} {getattr(mod, '__version__', '?'):<12} {purpose}")
        except Exception:  # noqa: BLE001
            print(f"  [MISSING]   {name:<12} {'':<12} {purpose}")
            missing_required.append(name)

    print("\nExternal tools (measured - optional tools degrade gracefully)")
    print("-" * 70)
    width = max(len(r["name"]) for r in rows)
    for row in rows:
        tag = "OK      " if row["available"] else "missing "
        print(f"  [{tag}] {row['name'].ljust(width)} {row['classification']:<12} "
              f"{row['install'] or ''}")

    print("-" * 70)
    if missing_required:
        print(f"RESULT: MISSING REQUIRED PYTHON LIBS: {', '.join(missing_required)}")
        print("Run: sudo apt install -y python3-pip && pip install -r requirements.txt")
        return 1
    print("RESULT: all required dependencies present. Optional tools that are missing "
          "will be reported as UNAVAILABLE (never faked) inside the app.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
