"""StegoNexus main window: sidebar navigation, header, status bar, toasts."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (QApplication, QComboBox, QFrame, QHBoxLayout, QLabel,
                               QMainWindow, QPushButton, QStackedWidget, QStatusBar,
                               QToolBar, QVBoxLayout, QWidget)

from app import APP_FULL_TITLE, __version__
from app.core.config import get_config
from app.core.logger import log_event
from app.gui import icons as iconlib
from app.gui.themes import palette, qt_palette, stylesheet
from app.services.tool_health import health
from app.storage.database import get_db

NAV_GROUPS = [
    ("Overview", [("dashboard", "Dashboard", "dashboard"),
                  ("toolhealth", "Tool Health", "health"),
                  ("about", "About", "about")]),
    ("Investigation", [("cases", "Cases", "case"),
                       ("evidence", "Evidence", "evidence"),
                       ("findings", "Findings", "findings"),
                       ("logs", "Investigation Logs", "logs"),
                       ("reports", "Reports", "reports")]),
    ("Analysis", [("metadata", "Metadata", "metadata"),
                  ("forensics", "Forensics", "forensics"),
                  ("hashing", "Hashing", "hash"),
                  ("extraction", "Extraction Center", "extract")]),
    ("Steganography", [("text", "Text", "text"),
                       ("image", "Image", "image"),
                       ("audio", "Audio", "audio"),
                       ("video", "Video", "video")]),
    ("Advanced", [("network", "Network", "network"),
                  ("malware", "Malware Analysis", "malware"),
                  ("externaltools", "External Tools", "extract")]),
    ("System", [("settings", "Settings", "settings")]),
]

LOGO_PATH = get_config().resources_dir / "branding" / "stegonexus-logo-dark.png"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_FULL_TITLE)
        self.resize(1380, 880)
        self.current_case = None
        self._views = {}
        self._nav_buttons = {}
        self._theme = get_config().theme
        self.apply_theme(self._theme)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_sidebar(), 0)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        right.addWidget(self._build_header(), 0)
        self.stack = QStackedWidget()
        right.addWidget(self.stack, 1)
        root.addLayout(right, 1)

        self._build_statusbar()
        self._register_views()
        self._populate_case_selector()
        self.navigate("dashboard")

        self._toast = None
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self._hide_toast)

        log_event("gui", "startup", f"StegoNexus v{__version__} main window ready",
                  status="OK")

    # ------------------------------------------------------------------ chrome
    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(216)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 12, 10, 12)
        layout.setSpacing(2)

        brand = QLabel("StegoNexus")
        brand.setObjectName("h2")
        layout.addWidget(brand)
        sub = QLabel("Unified Hiding, Extraction & Forensics")
        sub.setObjectName("muted")
        sub.setWordWrap(True)
        layout.addWidget(sub)
        layout.addSpacing(10)

        for group_name, entries in NAV_GROUPS:
            glabel = QLabel(group_name.upper())
            glabel.setObjectName("muted")
            layout.addWidget(glabel)
            for view_id, label, icon_name in entries:
                button = QPushButton(f"  {label}")
                button.setProperty("nav", "true")
                button.setIcon(self._nav_icon(icon_name))
                button.setIconSize(iconlib.icon_size())
                button.clicked.connect(lambda _=False, vid=view_id: self.navigate(vid))
                self._nav_buttons[view_id] = button
                layout.addWidget(button)
            layout.addSpacing(6)
        layout.addStretch(1)
        ver = QLabel(f"v{__version__}")
        ver.setObjectName("muted")
        layout.addWidget(ver)
        return sidebar

    def _nav_icon(self, name: str):
        return iconlib.icon(name, palette(self._theme)["accent"])

    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(56)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(14, 6, 14, 6)

        if LOGO_PATH.exists():
            logo = QLabel()
            pixmap = QPixmap(str(LOGO_PATH))
            logo.setPixmap(pixmap.scaledToHeight(36, Qt.TransformationMode.SmoothTransformation))
            layout.addWidget(logo)
        layout.addSpacing(6)
        self.title_label = QLabel("Dashboard")
        self.title_label.setObjectName("h2")
        layout.addWidget(self.title_label)
        layout.addStretch(1)

        layout.addWidget(QLabel("Active case:"))
        self.case_selector = QComboBox()
        self.case_selector.setMinimumWidth(220)
        self.case_selector.currentIndexChanged.connect(self._on_case_selected)
        layout.addWidget(self.case_selector)

        new_case = QPushButton("+ New Case")
        new_case.setProperty("primary", "true")
        new_case.clicked.connect(self._request_new_case)
        layout.addWidget(new_case)

        self.theme_button = QPushButton("Light" if self._theme == "dark" else "Dark")
        self.theme_button.setFixedWidth(70)
        self.theme_button.clicked.connect(self._toggle_theme)
        layout.addWidget(self.theme_button)
        return header

    def _build_statusbar(self) -> None:
        bar = QStatusBar()
        self.setStatusBar(bar)
        self.status_message = QLabel("Ready")
        bar.addWidget(self.status_message, 1)
        summary = health.summary()
        self.status_tools = QLabel(
            f"Tools {summary['available']}/{summary['total']} available")
        bar.addPermanentWidget(self.status_tools)

    # ---------------------------------------------------------------- navigation
    def _register_views(self) -> None:
        from app.gui.views import registry

        for view_id, factory in registry.VIEW_FACTORIES.items():
            view = factory(self)
            self._views[view_id] = view
            self.stack.addWidget(view)

    def navigate(self, view_id: str) -> None:
        view = self._views.get(view_id)
        if not view:
            return
        self.stack.setCurrentWidget(view)
        self.title_label.setText(view.title)
        for vid, button in self._nav_buttons.items():
            button.setProperty("active", "true" if vid == view_id else "false")
            button.style().unpolish(button)
            button.style().polish(button)
        try:
            view.refresh()
        except Exception as exc:  # noqa: BLE001 - views must never crash navigation
            self.notify(f"Could not load {view.title}: {exc}", "error")

    def current_view(self):
        return self.stack.currentWidget()

    def current_view_id(self) -> str:
        for view_id, view in self._views.items():
            if view is self.stack.currentWidget():
                return view_id
        return ""

    def refresh(self) -> None:
        """Reload everything that reflects database or tool state."""
        try:
            summary = health.summary()
            self.status_tools.setText(
                f"Tools {summary['available']}/{summary['total']} available")
        except Exception:  # noqa: BLE001 - a health probe must never break the UI
            pass
        self._populate_case_selector()
        view = self.stack.currentWidget()
        if view is not None:
            try:
                view.refresh()
            except Exception as exc:  # noqa: BLE001
                self.notify(f"Could not refresh {getattr(view, 'title', 'view')}: {exc}",
                            "error")

    # ---------------------------------------------------------------- cases
    def _populate_case_selector(self) -> None:
        self.case_selector.blockSignals(True)
        self.case_selector.clear()
        cases = get_db().list_cases()
        if cases:
            for case in cases:
                self.case_selector.addItem(
                    f"#{case['id']} {case['number']} - {case['title']}", case["id"])
        else:
            self.case_selector.addItem("(no case yet)")
        self.case_selector.blockSignals(False)
        if cases:
            self.set_current_case(cases[0])

    def _on_case_selected(self, index: int) -> None:
        case_id = self.case_selector.itemData(index)
        if case_id is None:
            self.current_case = None
            return
        self.set_current_case(get_db().get_case(case_id))

    def set_current_case(self, case) -> None:
        self.current_case = case
        if case:
            self.status_message.setText(f"Active case: {case['number']}")
        for view in self._views.values():
            try:
                view.refresh()
            except Exception:  # noqa: BLE001
                pass

    def _request_new_case(self) -> None:
        from app.gui.dialogs import CaseDialog

        dialog = CaseDialog(self)
        if dialog.exec():
            from app.modules.cases import service as cases

            data = dialog.values()
            case = cases.create(data["title"], data.get("description", ""),
                                data.get("investigator", ""), data.get("tags", ""))
            self._populate_case_selector()
            self.case_selector.setCurrentIndex(
                self.case_selector.findData(case["id"]))
            self.notify(f"Case {case['number']} created", "ok")

    # ---------------------------------------------------------------- theming
    def apply_theme(self, theme: str) -> None:
        self._theme = theme
        self.setStyleSheet(stylesheet(theme))
        app = QApplication.instance()
        if app is not None:
            app.setPalette(qt_palette(theme))
        get_config().theme = theme

    def _toggle_theme(self) -> None:
        new_theme = "light" if self._theme == "dark" else "dark"
        self.apply_theme(new_theme)
        self.theme_button.setText("Light" if new_theme == "dark" else "Dark")
        for view_id, button in self._nav_buttons.items():
            button.setIcon(self._nav_icon(
                next(icon for _, entries in NAV_GROUPS
                     for vid, _, icon in entries if vid == view_id)))
        get_config().save()
        view_id = self.current_view_id()
        if view_id:
            self.navigate(view_id)

    # ---------------------------------------------------------------- toasts
    def set_busy(self, busy: bool) -> None:
        self.status_message.setText("Working..." if busy else "Ready")

    def notify(self, message: str, level: str = "info") -> None:
        colour = {"ok": "#34d399", "error": "#f87171", "warn": "#fbbf24"}.get(
            level, palette(self._theme)["text"])
        self.status_message.setText(message)
        self.status_message.setStyleSheet(f"color:{colour}; font-weight:600;")
        self._show_toast(message, colour)
        log_event("gui", "notify", message, status=level)

    def _show_toast(self, message: str, colour: str) -> None:
        if self._toast is not None:
            self._toast.setParent(None)
        self._toast = QLabel(message, self)
        self._toast.setWordWrap(True)
        self._toast.setMaximumWidth(420)
        self._toast.setStyleSheet(
            f"background:{palette(self._theme)['panel']}; border:1px solid {colour};"
            f" border-left:4px solid {colour}; border-radius:8px; padding:10px;"
            f" color:{palette(self._theme)['text']};")
        self._toast.adjustSize()
        self._toast.move(self.width() - self._toast.width() - 16, 64)
        self._toast.show()
        self._toast.raise_()
        self._toast_timer.start(4000)

    def _hide_toast(self) -> None:
        if self._toast is not None:
            self._toast.hide()
