"""Shared view base class.

Every view gets helpers for async execution, notifications, tables and access to
the application's shared state (current case, config, database).
"""
from __future__ import annotations

from PySide6.QtWidgets import QWidget

from app.gui.workers import Runner


class BaseView(QWidget):
    #: navigation metadata overridden by subclasses
    title = "View"
    icon = "dashboard"

    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.runner = Runner

    # ------------------------------------------------------------ shared state
    @property
    def current_case(self):
        return self.mw.current_case

    def case_id(self):
        return self.mw.current_case["id"] if self.mw.current_case else None

    # ---------------------------------------------------------------- helpers
    def notify(self, message: str, level: str = "info") -> None:
        self.mw.notify(message, level)

    def run(self, fn, on_done, on_error=None, *args, **kwargs):
        self.mw.set_busy(True)
        return self.runner.run(fn, on_done=self._wrap(on_done),
                               on_error=self._wrap_error(on_error), *args, **kwargs)

    def _wrap(self, on_done):
        def handler(result):
            self.mw.set_busy(False)
            if on_done:
                on_done(result)
        return handler

    def _wrap_error(self, on_error):
        def handler(type_name: str, message: str):
            self.mw.set_busy(False)
            if on_error:
                on_error(type_name, message)
            else:
                self.notify(f"Operation failed: {message}", "error")
        return handler

    # ------------------------------------------------------------- overridable
    def refresh(self) -> None:
        """Reload data for this view. Subclasses override."""
