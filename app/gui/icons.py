"""Vector icons rendered from inline SVG so they tint cleanly in both themes."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_CACHE: dict[str, QIcon] = {}

# Simple 24x24 stroke icons; '{c}' is replaced by the tint colour.
_ICONS: dict[str, str] = {
    "dashboard": '<rect x="3" y="3" width="8" height="8" rx="2"/><rect x="13" y="3" width="8" height="5" rx="2"/><rect x="13" y="10" width="8" height="11" rx="2"/><rect x="3" y="13" width="8" height="8" rx="2"/>',
    "case": '<path d="M3 8h18v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/><path d="M3 8l2-4h6l2 3h8"/>',
    "evidence": '<path d="M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7Z"/>',
    "metadata": '<path d="M4 4h16v16H4Z"/><path d="M8 9h8M8 13h8M8 17h5"/>',
    "forensics": '<circle cx="10" cy="10" r="6"/><path d="M14.5 14.5 21 21"/>',
    "hash": '<path d="M9 3v18M15 3v18M4 9h16M4 15h16"/>',
    "text": '<path d="M5 4h14M12 4v16M8 20h8"/>',
    "image": '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="M3 17l5-5 4 4 3-3 6 6"/>',
    "audio": '<path d="M4 10v4h4l5 5V5L8 10Z"/><path d="M16 9a4 4 0 0 1 0 6M18.5 6.5a8 8 0 0 1 0 11"/>',
    "video": '<rect x="3" y="5" width="13" height="14" rx="2"/><path d="M16 10l5-3v10l-5-3"/>',
    "network": '<circle cx="5" cy="12" r="2.5"/><circle cx="19" cy="6" r="2.5"/><circle cx="19" cy="18" r="2.5"/><path d="M7 11l9-4M7 13l9 4"/>',
    "malware": '<path d="M12 3a4 4 0 0 1 4 4v6a4 4 0 0 1-8 0V7a4 4 0 0 1 4-4Z"/><path d="M8 8H4M8 12H5M8 16l-3 2M16 8h4M16 12h3M16 16l3 2M12 3V1"/>',
    "extract": '<path d="M12 3v10M8 9l4 4 4-4"/><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/>',
    "findings": '<path d="M12 3l2.5 6 6.5.5-5 4.5 1.5 6.5L12 17l-5.5 3.5L8 14 3 9.5 9.5 9Z"/>',
    "logs": '<path d="M5 3h14v18H5Z"/><path d="M9 8h6M9 12h6M9 16h4"/>',
    "reports": '<path d="M6 3h9l4 4v14H6Z"/><path d="M15 3v4h4M10 13l2 2 4-4"/>',
    "health": '<path d="M3 12h4l2-6 4 12 2-6h6"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.5 4.5l2 2M17.5 17.5l2 2M19.5 4.5l-2 2M6.5 17.5l-2 2"/>',
    "about": '<circle cx="12" cy="12" r="9"/><path d="M12 10v6M12 7v.5"/>',
}

_STROKED = {k: False for k in _ICONS}


def _svg(name: str, colour: str) -> str:
    body = _ICONS.get(name, _ICONS["dashboard"])
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
            f'<g fill="none" stroke="{colour}" stroke-width="1.9" '
            f'stroke-linecap="round" stroke-linejoin="round">{body}</g></svg>')


def icon(name: str, colour: str, size: int = 18) -> QIcon:
    key = f"{name}:{colour}:{size}"
    if key in _CACHE:
        return _CACHE[key]
    renderer = QSvgRenderer(_svg(name, colour).encode())
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter)
    painter.end()
    # PySide6 6.11 rejects QIcon(QImage) for a painted image; QPixmap.fromImage works
    # and keeps the anti-aliased stroke intact.
    pixmap = QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(1.0)
    qicon = QIcon(pixmap)
    _CACHE[key] = qicon
    return qicon


def icon_size() -> QSize:
    return QSize(18, 18)
