"""About view: branding, version, philosophy and honesty policy."""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout

from app import APP_FULL_TITLE, __version__
from app.gui.views.base import BaseView
from app.gui.widgets import SectionHeader

LOGO = None


class AboutView(BaseView):
    title = "About"
    icon = "about"

    def __init__(self, mw):
        super().__init__(mw)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 12)
        layout.addWidget(SectionHeader("About StegoNexus", APP_FULL_TITLE))

        from PySide6.QtGui import QPixmap
        from PySide6.QtCore import Qt

        from app.core.config import get_config

        logo_path = get_config().resources_dir / "branding" / "stegonexus-logo-dark.png"
        if logo_path.exists():
            logo = QLabel()
            logo.setPixmap(QPixmap(str(logo_path)).scaledToHeight(
                90, Qt.TransformationMode.SmoothTransformation))
            layout.addWidget(logo)

        body = QLabel(
            f"<b>Version:</b> {__version__}<br/>"
            f"<b>Platform:</b> Kali Linux / Debian (Python + PySide6 + SQLite)<br/><br/>"
            "<b>Philosophy:</b><br/>"
            "Hide it. Extract it. Analyze it. Verify it. Investigate it. "
            "Document it. Report it.<br/><br/>"
            "<b>Honesty policy (non-negotiable):</b><br/>"
            "&#8226; Every feature carries one status label: IMPLEMENTED, INTEGRATED, "
            "SIMULATED, REFERENCE, EXTERNAL, OPTIONAL or UNAVAILABLE.<br/>"
            "&#8226; An unavailable tool is never marked implemented.<br/>"
            "&#8226; A reference application (OpenPuff, CyberHide, DeepSound, "
            "CoagulaLight, Audacity) is never presented as native code.<br/>"
            "&#8226; No successful extraction, detection or hash comparison is reported "
            "without an actual execution.<br/>"
            "&#8226; An anomaly is an indicator - never proof.")
        body.setWordWrap(True)
        body.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(body)
        layout.addStretch(1)
