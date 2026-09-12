"""View registry: nav id -> factory. Adding a view = adding one entry."""
from __future__ import annotations

from app.gui.views.about_view import AboutView
from app.gui.views.audio_view import AudioView
from app.gui.views.cases_view import CasesView
from app.gui.views.dashboard_view import DashboardView
from app.gui.views.evidence_view import EvidenceView
from app.gui.views.extraction_view import ExtractionView
from app.gui.views.external_tools_view import ExternalToolsView
from app.gui.views.findings_view import FindingsView
from app.gui.views.forensics_view import ForensicsView
from app.gui.views.hashing_view import HashingView
from app.gui.views.image_view import ImageView
from app.gui.views.logs_view import LogsView
from app.gui.views.malware_view import MalwareView
from app.gui.views.metadata_view import MetadataView
from app.gui.views.network_view import NetworkView
from app.gui.views.reports_view import ReportsView
from app.gui.views.settings_view import SettingsView
from app.gui.views.text_view import TextView
from app.gui.views.toolhealth_view import ToolHealthView
from app.gui.views.video_view import VideoView

VIEW_FACTORIES = {
    "dashboard": DashboardView,
    "toolhealth": ToolHealthView,
    "about": AboutView,
    "cases": CasesView,
    "evidence": EvidenceView,
    "findings": FindingsView,
    "logs": LogsView,
    "reports": ReportsView,
    "metadata": MetadataView,
    "forensics": ForensicsView,
    "hashing": HashingView,
    "extraction": ExtractionView,
    "externaltools": ExternalToolsView,
    "text": TextView,
    "image": ImageView,
    "audio": AudioView,
    "video": VideoView,
    "network": NetworkView,
    "malware": MalwareView,
    "settings": SettingsView,
}
