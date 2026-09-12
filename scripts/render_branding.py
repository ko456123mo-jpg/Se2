#!/usr/bin/env python3
"""Rasterise the StegoNexus SVG branding into PNG variants.

Uses Qt's SVG renderer (already a project dependency) so no extra package is
required.  Run from the project root:

    python3 scripts/render_branding.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRANDING = ROOT / "resources" / "branding"
ICONS = ROOT / "resources" / "icons"

SIZES = {"logo": (1040, 320), "icon": (512, 512)}


def main() -> int:
    from PySide6.QtCore import QRectF, QSize
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    ICONS.mkdir(parents=True, exist_ok=True)
    written = []
    for source in sorted(BRANDING.glob("*.svg")):
        kind = "icon" if "icon" in source.name else "logo"
        width, height = SIZES[kind]
        renderer = QSvgRenderer(str(source))
        image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(0)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        renderer.render(painter, QRectF(0, 0, width, height))
        painter.end()
        target = (ICONS if kind == "icon" else BRANDING) / (source.stem + ".png")
        image.save(str(target), "PNG")
        written.append(target)
        # additional launcher icon sizes
        if kind == "icon":
            for size in (16, 32, 48, 64, 128, 256):
                scaled = image.scaled(QSize(size, size))
                out = ICONS / f"stegonexus-{size}.png"
                scaled.save(str(out), "PNG")
                written.append(out)
    print(f"rendered {len(written)} PNG file(s):")
    for path in written:
        print("  ", path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
