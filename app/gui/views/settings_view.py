"""Settings view: centralised configuration with persistence."""
from __future__ import annotations

from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QFrame,
                               QHBoxLayout, QLineEdit, QPushButton, QSpinBox,
                               QVBoxLayout)

from app.gui.views.base import BaseView
from app.gui.widgets import SectionHeader
from app.modules.settings import service as settings


class SettingsView(BaseView):
    title = "Settings"
    icon = "settings"

    def __init__(self, mw):
        super().__init__(mw)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 12)
        layout.addWidget(SectionHeader("Settings", "Application configuration, stored in "
                                                   "data/stegonexus.json."))

        form_frame = QFrame()
        form_frame.setObjectName("panel")
        form = QFormLayout(form_frame)
        self.theme = QComboBox()
        self.theme.addItems(["dark", "light"])
        self.investigator = QLineEdit()
        self.timeout = QSpinBox()
        self.timeout.setRange(10, 3600)
        self.timeout.setSuffix(" s")
        self.auto_hash = QCheckBox("Hash evidence automatically on import")
        self.read_only = QCheckBox("Read-only forensic analysis by default")
        self.authorized_lab = QCheckBox("Enable authorized network laboratory mode")
        self.verbose = QCheckBox("Verbose application logging")
        form.addRow("Theme", self.theme)
        form.addRow("Default investigator", self.investigator)
        form.addRow("Tool timeout", self.timeout)
        form.addRow(self.auto_hash)
        form.addRow(self.read_only)
        form.addRow(self.authorized_lab)
        form.addRow(self.verbose)
        layout.addWidget(form_frame)

        buttons = QHBoxLayout()
        save = QPushButton("Save settings")
        save.setProperty("primary", "true")
        save.clicked.connect(self._save)
        buttons.addWidget(save)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.paths = QLineEdit()
        self.paths.setReadOnly(True)
        layout.addWidget(self.paths)
        layout.addStretch(1)
        self._load()

    def _load(self) -> None:
        current = settings.current()
        self.theme.setCurrentText(current["theme"])
        self.investigator.setText(current["investigator"])
        self.timeout.setValue(current["tool_timeout"])
        self.auto_hash.setChecked(current["auto_hash_on_import"])
        self.read_only.setChecked(current["read_only_analysis"])
        self.authorized_lab.setChecked(current["network_authorized_lab"])
        self.verbose.setChecked(current["verbose_logs"])
        self.paths.setText(f"root: {current['root']}   |   db: {current['database']}")

    def _save(self) -> None:
        settings.save(theme=self.theme.currentText(),
                      investigator=self.investigator.text().strip(),
                      tool_timeout=self.timeout.value(),
                      auto_hash_on_import=self.auto_hash.isChecked(),
                      read_only_analysis=self.read_only.isChecked(),
                      network_authorized_lab=self.authorized_lab.isChecked(),
                      verbose_logs=self.verbose.isChecked())
        if self.theme.currentText() != self.mw._theme:
            self.mw.apply_theme(self.theme.currentText())
            self.mw.theme_button.setText(
                "Light" if self.theme.currentText() == "dark" else "Dark")
        self.notify("Settings saved", "ok")
